"""
Base scraper abstractions for the Hunter AI job scraper module.

Provides:
- JobResult: TypedDict describing the normalized output shape.
- BaseScraper: Abstract base class that every site-specific scraper extends.

Responsibilities of BaseScraper:
  - Session management (requests.Session with custom headers).
  - Fetching pages with timeout handling and graceful HTTP/network error recovery.
  - Enforcing random delays between requests to avoid rate-limiting.
  - Coordinating pagination via the abstract `_get_next_page_url` hook.
  - Delegating parsing to the abstract `_parse_jobs` hook.
  - Normalizing raw payloads into JobResult dicts via the abstract `_normalize` hook.
  - Structured logging throughout.

Subclasses must implement:
  - `base_url` (class attribute) – the canonical search URL.
  - `_build_search_url(query, location, page)` – returns a fully-qualified URL.
  - `_parse_jobs(soup)` – returns a list of raw BS4 Tag objects.
  - `_normalize(raw)` – maps a raw Tag to a JobResult dict.
  - `_get_next_page_url(soup, current_page)` – returns next-page URL or None.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Generator, List, Optional
from urllib.parse import urljoin
import cloudscraper

import requests
from bs4 import BeautifulSoup, Tag

from .utils import build_headers, random_delay, sanitize_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public type alias
# ---------------------------------------------------------------------------

class JobResult(dict):
    """
    Typed alias for a normalized job payload.

    Keys
    ----
    title       : str  – job title
    company     : str  – company name
    location    : str  – location string
    description : str  – job description excerpt or full text
    link        : str  – canonical URL to the job posting
    """

    REQUIRED_KEYS = {"title", "company", "location", "description", "link"}
    REQUIRED_NON_EMPTY_KEYS = {"title", "company", "link"}

    @classmethod
    def create(
        cls,
        *,
        title: str,
        company: str,
        location: str,
        description: str,
        link: str,
    ) -> "JobResult":
        obj = cls(
            title=sanitize_text(title),
            company=sanitize_text(company),
            location=sanitize_text(location),
            description=sanitize_text(description),
            link=link.strip(),
        )
        return obj

    def is_valid(self) -> bool:
        """
        Return ``True`` when the normalized payload contains the minimum data
        needed to represent a job listing safely in the app.

        ``description`` and ``location`` are allowed to be blank because some
        sites omit them from the search results page.
        """
        if not self.REQUIRED_KEYS.issubset(self.keys()):
            return False

        return all(bool(sanitize_text(str(self.get(key, "")))) for key in self.REQUIRED_NON_EMPTY_KEYS)

   

# ---------------------------------------------------------------------------
# Abstract base scraper
# ---------------------------------------------------------------------------

class BaseScraper(ABC):
    """
    Abstract base class for all job site scrapers.

    Parameters
    ----------
    timeout : int
        Seconds to wait before aborting a single HTTP request (default 15).
    min_delay : float
        Minimum seconds to sleep between consecutive requests (default 1.0).
    max_delay : float
        Maximum seconds to sleep between consecutive requests (default 3.0).
    max_retries : int
        Number of times to retry a failed request (default 3).
    """

    # Subclasses should set this to the root URL of the target site.
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
                f"{self.__class__.__name__} must define a non-empty `base_url`."
            )

        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries

        self._session = cloudscraper.create_scraper()  # type: ignore[no-untyped-call]
        self._session.headers.update(build_headers())

        logger.debug(
            "%s initialised  base_url=%s  timeout=%ds",
            self.__class__.__name__,
            self.base_url,
            self.timeout,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(
        self,
        query: str,
        location: str = "",
        max_pages: int = 5,
    ) -> List[JobResult]:
        """
        Scrape job listings and return a list of normalized JobResult dicts.

        Parameters
        ----------
        query     : Search keywords, e.g. "Python Developer".
        location  : Location filter, e.g. "Remote" or "New York".
        max_pages : Maximum number of pagination pages to follow (default 5).

        Returns
        -------
        List[JobResult]
        """
        results: List[JobResult] = []

        logger.info(
            "%s  scrape started  query=%r  location=%r  max_pages=%d",
            self.__class__.__name__,
            query,
            location,
            max_pages,
        )

        for page_num, url in enumerate(
            self._paginate(query, location, max_pages), start=1
        ):
            logger.info("Fetching page %d  url=%s", page_num, url)
            soup = self._fetch_page(url)
            if soup is None:
                logger.warning("Skipping page %d – fetch returned None.", page_num)
                continue

            raw_jobs = self._parse_jobs(soup)
            logger.debug("Page %d – found %d raw job entries.", page_num, len(raw_jobs))

            for raw in raw_jobs:
                try:
                    job = self._normalize(raw)
                    if job.is_valid():
                        results.append(job)
                    else:
                        logger.debug("Skipping incomplete job entry: %s", dict(job))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to normalize job entry: %s", exc)

            if page_num < max_pages:
                random_delay(self.min_delay, self.max_delay)

        logger.info(
            "%s  scrape finished  total_results=%d",
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        GET *url* and return a parsed BeautifulSoup tree, or None on failure.

        Retries up to `max_retries` times with a short backoff on transient
        errors (connection errors, timeouts, 5xx responses).
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")

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
                # Do not retry client-side errors (4xx) except 429 (rate limit).
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

    def _paginate(
        self, query: str, location: str, max_pages: int
    ) -> Generator[str, None, None]:
        """
        Yield successive page URLs up to *max_pages*.

        Uses `_build_search_url` for the first page, then follows links
        returned by `_get_next_page_url` to discover subsequent pages.
        """
        url: Optional[str] = self._build_search_url(query, location, page=1)
        page_num = 0

        while url and page_num < max_pages:
            yield url
            page_num += 1

            if page_num >= max_pages:
                break

            # Fetch the page again only to discover the next-page URL.
            # Subclasses that cache soup may override _paginate directly.
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
        """Resolve a potentially relative URL against `base_url`."""
        if url.startswith("http"):
            return url
        return urljoin(self.base_url, url)

    # ------------------------------------------------------------------
    # Abstract interface – subclasses MUST implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def _build_search_url(self, query: str, location: str, page: int) -> str:
        """
        Return the full URL for the given search query, location and page number.

        Parameters
        ----------
        query    : Search keywords.
        location : Location filter string (may be empty).
        page     : 1-based page number.
        """

    @abstractmethod
    def _parse_jobs(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Extract raw job card elements from a parsed page.

        Parameters
        ----------
        soup : Parsed BeautifulSoup tree for one search-results page.

        Returns
        -------
        List[Tag] – one Tag per job card.
        """

    @abstractmethod
    def _normalize(self, raw: Tag) -> JobResult:
        """
        Convert a raw BS4 Tag into a normalized JobResult.

        Parameters
        ----------
        raw : A job card Tag as returned by `_parse_jobs`.

        Returns
        -------
        JobResult – may be invalid if source data is incomplete.
        """

    @abstractmethod
    def _get_next_page_url(self, soup: BeautifulSoup, current_page: int) -> Optional[str]:
        """
        Return the URL of the next page, or None if there are no more pages.

        Parameters
        ----------
        soup         : Parsed BeautifulSoup tree of the current page.
        current_page : The 1-based index of the page just fetched.
        """
