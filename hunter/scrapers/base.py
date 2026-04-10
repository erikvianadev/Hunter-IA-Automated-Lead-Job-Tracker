"""
Base scraper abstractions for the Hunter AI job scraper module.

Provides:
- BaseScraper: Abstract base class that every site-specific scraper extends.

Responsibilities of BaseScraper:
  - Session management (requests.Session with custom headers).
  - Fetching pages with timeout handling and graceful HTTP/network error recovery.
  - Enforcing random delays between requests to avoid rate-limiting.
  - Coordinating pagination via the abstract _get_next_page_url hook.
  - Delegating parsing to the abstract _parse_jobs hook.
  - Normalizing raw payloads into JobResult objects via the abstract _normalize hook.
  - Structured logging throughout.

Subclasses must implement:
  - base_url (class attribute) – the canonical search URL.
  - _build_search_url(query, location, page) – returns a fully-qualified URL.
  - _parse_jobs(soup) – returns a list of raw BS4 Tag objects.
  - _normalize(raw) – maps a raw Tag to a JobResult object.
  - _get_next_page_url(soup, current_page) – returns next-page URL or None.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Generator, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from hunter.models.dto import JobResult
from .utils import build_headers, random_delay

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for all job site scrapers.

    Parameters
    ----------
    timeout : int
        Seconds to wait before aborting a single HTTP request.
    min_delay : float
        Minimum seconds to sleep between consecutive requests.
    max_delay : float
        Maximum seconds to sleep between consecutive requests.
    max_retries : int
        Number of times to retry a failed request.
    """

    base_url: str = ""

    def __init__(
        self,
        timeout: int = 15,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        max_retries: int = 3,
    ) -> None:
        if not self.base_url:
            raise NotImplementedError(
                f"{self.__class__.__name__} must define a non-empty base_url."
            )

        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries

        self._session = requests.Session()
        self._session.headers.update(build_headers())

        logger.debug(
            "%s initialized | base_url=%s | timeout=%ds",
            self.__class__.__name__,
            self.base_url,
            self.timeout,
        )

    def scrape(
        self,
        query: str,
        location: str = "",
        max_pages: int = 5,
    ) -> List[JobResult]:
        """
        Scrape job listings and return a list of normalized JobResult objects.
        """
        results: List[JobResult] = []

        logger.info(
            "%s scrape started | query=%r | location=%r | max_pages=%d",
            self.__class__.__name__,
            query,
            location,
            max_pages,
        )

        for page_num, url in enumerate(
            self._paginate(query, location, max_pages), start=1
        ):
            logger.info("Fetching page %d | url=%s", page_num, url)

            soup = self._fetch_page(url)
            if soup is None:
                logger.warning("Skipping page %d because fetch returned None.", page_num)
                continue

            raw_jobs = self._parse_jobs(soup)
            logger.debug("Page %d returned %d raw job entries.", page_num, len(raw_jobs))

            for raw in raw_jobs:
                try:
                    job = self._normalize(raw)
                    if job.is_valid():
                        results.append(job)
                    else:
                        logger.debug("Skipping incomplete job entry: %s", job)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to normalize job entry: %s", exc)

            if page_num < max_pages:
                random_delay(self.min_delay, self.max_delay)

        logger.info(
            "%s scrape finished | total_results=%d",
            self.__class__.__name__,
            len(results),
        )
        return results

    def close(self) -> None:
        """Release the underlying requests session."""
        self._session.close()
        logger.debug("%s session closed.", self.__class__.__name__)

    def __enter__(self) -> "BaseScraper":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _fetch_response(self, url: str) -> Optional[requests.Response]:
        """
        GET url and return the raw HTTP response, or None on failure.
        Retries transient failures using exponential backoff.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.get(url, timeout=self.timeout)
                response.raise_for_status()

                if not response.encoding:
                    response.encoding = response.apparent_encoding or "utf-8"

                return response

            except requests.exceptions.Timeout:
                logger.warning(
                    "Timeout on attempt %d/%d for %s",
                    attempt,
                    self.max_retries,
                    url,
                )

            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                logger.warning(
                    "HTTP %s on attempt %d/%d for %s",
                    status,
                    attempt,
                    self.max_retries,
                    url,
                )

                if exc.response is not None and 400 <= exc.response.status_code < 500:
                    if exc.response.status_code != 429:
                        return None

            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "Request error on attempt %d/%d for %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )

            if attempt < self.max_retries:
                backoff = 2 ** attempt
                logger.debug("Backing off %ds before retry.", backoff)
                time.sleep(backoff)

        logger.error("All %d attempts failed for %s", self.max_retries, url)
        return None

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        GET url and return a parsed BeautifulSoup tree, or None on failure.
        """
        response = self._fetch_response(url)
        if response is None:
            return None
        return BeautifulSoup(response.text, "html.parser")

    def _paginate(
        self,
        query: str,
        location: str,
        max_pages: int,
    ) -> Generator[str, None, None]:
        """
        Yield successive page URLs up to max_pages.
        """
        url: Optional[str] = self._build_search_url(query, location, page=1)
        page_num = 0

        while url and page_num < max_pages:
            yield url
            page_num += 1

            if page_num >= max_pages:
                break

            soup = self._fetch_page(url)
            if soup is None:
                break

            next_url = self._get_next_page_url(soup, page_num)
            if not next_url:
                logger.debug("No further pages found after page %d.", page_num)
                break

            url = self._resolve_url(next_url)
            random_delay(self.min_delay, self.max_delay)

    def _resolve_url(self, url: str) -> str:
        """Resolve a potentially relative URL against base_url."""
        if url.startswith("http"):
            return url
        return urljoin(self.base_url, url)

    @abstractmethod
    def _build_search_url(self, query: str, location: str, page: int) -> str:
        """
        Return the full URL for the given search query, location and page number.
        """

    @abstractmethod
    def _parse_jobs(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Extract raw job card elements from a parsed page.
        """

    @abstractmethod
    def _normalize(self, raw: Tag) -> JobResult:
        """
        Convert a raw BS4 Tag into a normalized JobResult.
        """

    @abstractmethod
    def _get_next_page_url(
        self,
        soup: BeautifulSoup,
        current_page: int,
    ) -> Optional[str]:
        """
        Return the URL of the next page, or None if there are no more pages.
        """