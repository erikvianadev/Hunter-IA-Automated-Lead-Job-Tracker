"""
Indeed scraper implemented with plain HTTP requests and BeautifulSoup.

This version keeps the existing scraper architecture intact by relying on the
BaseScraper workflow:
  - `_build_search_url` generates paginated search URLs
  - `_parse_jobs` extracts job cards from HTML
  - `_normalize` maps each raw card into `JobResult.create(...)`
  - `_get_next_page_url` advances pagination without any browser automation

It is safe for server environments such as Render because it does not require
Chrome or any browser process.
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Iterable, List, Optional
from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup, Tag

from hunter.models.dto import JobResult
from .base import BaseScraper
from .utils import absolute_url, build_headers, extract_text, random_delay

logger = logging.getLogger(__name__)

_RESULTS_PER_PAGE = 10
_MAX_SAFE_PAGES = 3
_REQUEST_TIMEOUT_SECONDS = 10
_INITIAL_DATA_RE = re.compile(r"window\._initialData\s*=\s*", re.DOTALL)
_JSON_SCRIPT_SELECTORS = [
    "script[type='application/json']",
    "script#__NEXT_DATA__",
]

_USER_AGENTS: List[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
]

_CARD_SELECTORS: List[str] = [
    "div.job_seen_beacon",
    "div[data-jk]",
    "a[data-jk]",
    "div[data-testid='slider_item']",
    "div.cardOutline",
    "[data-jk]",
]

_BLOCK_TITLE_KEYWORDS = (
    "sign in",
    "log in",
    "login",
    "cloudflare",
    "access denied",
    "403 forbidden",
    "just a moment",
    "security check",
    "captcha",
    "are you a human",
    "robot",
    "verify",
)

_BLOCK_TEXT_PATTERNS = (
    "verify you are a human",
    "press and hold",
    "captcha",
    "access denied",
    "security check",
)


class IndeedScraper(BaseScraper):
    base_url = "https://www.indeed.com"

    def __init__(
        self,
        headless: bool = True,
        fetch_descriptions: bool = False,
        debug: bool = False,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.headless = headless
        self.fetch_descriptions = fetch_descriptions
        self.debug = debug
        self.timeout = min(self.timeout, _REQUEST_TIMEOUT_SECONDS)
        self.min_delay = max(1.0, self.min_delay)
        self.max_delay = min(max(self.max_delay, self.min_delay), 2.5)
        self._last_query = ""
        self._last_location = ""
        self._last_page_had_results = True
        self._last_response_text = ""
        self._current_page_number = 1
        self._request_count = 0
        self._blocked_detected = False
        self._session.headers.update(
            build_headers(
                {
                    "Referer": self.base_url + "/",
                    "Origin": self.base_url,
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                }
            )
        )

    def scrape(
        self,
        query: str,
        location: str = "",
        max_pages: int = 5,
    ) -> List[JobResult]:
        safe_max_pages = max(1, min(max_pages, _MAX_SAFE_PAGES))
        if safe_max_pages != max_pages:
            logger.info(
                "IndeedScraper limiting max_pages from %d to %d for safer execution.",
                max_pages,
                safe_max_pages,
            )

        self._blocked_detected = False
        self._request_count = 0
        self._prime_session()
        return super().scrape(query, location, safe_max_pages)

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        self._prepare_request(url)
        return super()._fetch_page(url)

    def _build_search_url(self, query: str, location: str, page: int) -> str:
        self._last_query = query
        self._last_location = location

        offset = max(page - 1, 0) * _RESULTS_PER_PAGE
        url = f"{self.base_url}/jobs?q={quote_plus(query.strip())}"
        if location.strip():
            url += f"&l={quote_plus(location.strip())}"
        if offset:
            url += f"&start={offset}"
        return url

    def _prime_session(self) -> None:
        try:
            home = self._session.get(
                self.base_url + "/",
                timeout=self.timeout,
                allow_redirects=True,
            )
            if not home.encoding:
                home.encoding = home.apparent_encoding or "utf-8"
            logger.info("Indeed session primed with status %s", home.status_code)
        except Exception as exc:
            logger.debug("Could not prime Indeed session: %s", exc)

    def _parse_jobs(self, soup: BeautifulSoup) -> List[Tag]:
        self._last_response_text = str(soup)

        for selector in _CARD_SELECTORS:
            cards = self._dedupe_cards(
                [card for card in soup.select(selector) if isinstance(card, Tag)]
            )
            if cards:
                self._last_page_had_results = True
                logger.info(
                    "Indeed page %d: %d jobs parsed via selector %r.",
                    self._current_page_number,
                    len(cards),
                    selector,
                )
                return cards

        synthetic_cards = self._build_synthetic_cards_from_bootstrap_data(
            self._last_response_text,
            soup=soup,
        )
        self._last_page_had_results = bool(synthetic_cards)
        if synthetic_cards:
            logger.info(
                "Indeed page %d: using bootstrap fallback with %d jobs.",
                self._current_page_number,
                len(synthetic_cards),
            )
            return synthetic_cards

        if self._is_blocked(soup):
            self._blocked_detected = True
            self._last_page_had_results = False
            logger.warning(
                "Indeed block detected on page %d. Title=%r",
                self._current_page_number,
                extract_text(soup.title),
            )
            if self.debug:
                self._save_debug_html(self._last_response_text)
            return []

        logger.warning("Indeed page %d: no job cards found.", self._current_page_number)
        if self.debug:
            self._save_debug_html(self._last_response_text)
        return []

    def _normalize(self, raw: Tag) -> JobResult:
        if raw.get("data-synthetic") == "1":
            job = JobResult.create(
                title=raw.get("data-title", ""),
                company=raw.get("data-company", ""),
                location=raw.get("data-location", ""),
                description=raw.get("data-description", ""),
                link=raw.get("data-link", ""),
                source="indeed",
            )
            if self.fetch_descriptions and job.link and not job.description:
                job.description = self._fetch_full_description(job.link)
            return job

        link = self._extract_link(raw)
        description = self._extract_description(raw)
        if self.fetch_descriptions and link and not description:
            description = self._fetch_full_description(link)

        return JobResult.create(
            title=self._extract_title(raw),
            company=self._extract_company(raw),
            location=self._extract_location(raw),
            description=description,
            link=link,
            source="indeed",
        )

    def _get_next_page_url(
        self,
        soup: BeautifulSoup,
        current_page: int,
    ) -> Optional[str]:
        if self._blocked_detected or self._is_blocked(soup) or not self._last_page_had_results:
            logger.info(
                "Indeed pagination stopping after page %d due to block or empty results.",
                current_page,
            )
            return None

        next_link = (
            soup.select_one("a[data-testid='pagination-page-next']")
            or soup.select_one("a[aria-label*='Next Page']")
            or soup.select_one("a[aria-label*='Next']")
        )
        if isinstance(next_link, Tag):
            href = next_link.get("href")
            if isinstance(href, str) and href.strip():
                return absolute_url(self.base_url, href)

        if not self._last_query.strip():
            return None

        return self._build_search_url(
            self._last_query,
            self._last_location,
            current_page + 1,
        )

    def _extract_title(self, card: Tag) -> str:
        candidates = [
            card.find("h2", class_=lambda c: c and "jobTitle" in c),
            card.find("span", class_=lambda c: c and "jobTitle" in c),
            card.find("a", class_=lambda c: c and "jcs-JobTitle" in (c or "")),
            card.find("span", attrs={"title": True}),
            card.find("h2"),
        ]
        for tag in candidates:
            if not isinstance(tag, Tag):
                continue
            inner = tag.find("span", attrs={"title": True})
            text = extract_text(inner if isinstance(inner, Tag) else tag)
            if text:
                return text
        return ""

    def _extract_company(self, card: Tag) -> str:
        candidates = [
            card.find(attrs={"data-testid": "company-name"}),
            card.find(attrs={"data-testid": "companyName"}),
            card.find("span", class_="companyName"),
            card.find("span", class_=lambda c: c and "company" in (c or "").lower()),
        ]
        for tag in candidates:
            text = extract_text(tag)
            if text:
                return text
        return ""

    def _extract_location(self, card: Tag) -> str:
        candidates = [
            card.find(attrs={"data-testid": "text-location"}),
            card.find(attrs={"data-testid": "job-location"}),
            card.find("div", class_="companyLocation"),
            card.find(class_=lambda c: c and "location" in (c or "").lower()),
        ]
        for tag in candidates:
            text = extract_text(tag)
            if text:
                return text
        return ""

    def _extract_link(self, card: Tag) -> str:
        job_key = card.get("data-jk")
        if isinstance(job_key, str) and job_key.strip():
            return absolute_url(self.base_url, f"/viewjob?jk={job_key}")

        inner = card.find(attrs={"data-jk": True})
        if isinstance(inner, Tag):
            inner_job_key = inner.get("data-jk")
            if isinstance(inner_job_key, str) and inner_job_key.strip():
                return absolute_url(self.base_url, f"/viewjob?jk={inner_job_key}")

        anchor_candidates = [
            card.find("a", class_=lambda c: c and "jcs-JobTitle" in (c or "")),
            card.find("a", href=lambda h: h and "/viewjob" in (h or "")),
            card.find("a", href=lambda h: h and "/rc/clk" in (h or "")),
            card.find("a", href=True),
        ]
        for anchor in anchor_candidates:
            if not isinstance(anchor, Tag):
                continue
            href = anchor.get("href")
            if isinstance(href, str) and href.strip():
                return absolute_url(self.base_url, href)

        return ""

    def _extract_description(self, card: Tag) -> str:
        candidates = [
            card.find("div", class_=lambda c: c and "job-snippet" in (c or "")),
            card.find("div", attrs={"data-testid": "job-snippet"}),
            card.find("ul", class_=lambda c: c and "jobCardShelfContainer" in (c or "")),
            card.find("div", class_=lambda c: c and "snippet" in (c or "").lower()),
        ]
        for tag in candidates:
            text = extract_text(tag)
            if text:
                return text

        meta = card.find("ul", class_=lambda c: c and "metadataContainer" in (c or ""))
        if isinstance(meta, Tag):
            items = [extract_text(li) for li in meta.find_all("li") if extract_text(li)]
            if items:
                return " | ".join(items)

        return ""

    def _fetch_response(self, url: str):
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )

                if not response.encoding:
                    response.encoding = response.apparent_encoding or "utf-8"

                if response.status_code == 403:
                    logger.warning(
                        "Indeed returned HTTP 403 on attempt %d/%d for %s",
                        attempt,
                        self.max_retries,
                        url,
                    )
                    return response

                response.raise_for_status()
                return response

            except Exception as exc:
                logger.warning(
                    "Indeed request error on attempt %d/%d for %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )

                if attempt < self.max_retries:
                    random_delay(self.min_delay, self.max_delay)

        return None

    def _fetch_full_description(self, url: str) -> str:
        self._prepare_request(url)
        response = self._fetch_response(url)
        if response is None:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")
        if self._is_blocked(soup):
            logger.warning("Indeed blocked full-description fetch for %s", url)
            return ""

        desc_tag = soup.find("div", id="jobDescriptionText") or soup.find(
            "div",
            class_=lambda c: c and "jobsearch-jobDescriptionText" in (c or ""),
        )
        return extract_text(desc_tag)

    def _is_blocked(self, soup: BeautifulSoup) -> bool:
        title = extract_text(soup.title).lower()
        page_text = soup.get_text(" ", strip=True).lower()

        if any(keyword in title for keyword in _BLOCK_TITLE_KEYWORDS):
            return True

        return any(pattern in page_text for pattern in _BLOCK_TEXT_PATTERNS)

    def _save_debug_html(self, page_source: str) -> None:
        try:
            path = Path("debug_indeed.html")
            path.write_text(page_source, encoding="utf-8")
            logger.info("Debug HTML saved to %s", path.resolve())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not save debug HTML: %s", exc)

    def _extract_jobs_from_bootstrap_data(self, page_source: str) -> List[JobResult]:
        jobs = self._extract_job_dicts_from_embedded_data(page_source)
        normalized_jobs: List[JobResult] = []
        seen_links: set[str] = set()

        for job_data in jobs:
            normalized = self._normalize_job_data(job_data)
            if not normalized.is_valid() or normalized.link in seen_links:
                continue
            seen_links.add(normalized.link)
            normalized_jobs.append(normalized)

        return normalized_jobs

    def _build_synthetic_cards_from_bootstrap_data(
        self,
        page_source: str,
        soup: Optional[BeautifulSoup] = None,
    ) -> List[Tag]:
        jobs = self._extract_job_dicts_from_embedded_data(page_source, soup=soup)
        normalized_jobs: List[JobResult] = []
        seen_links: set[str] = set()

        for job_data in jobs:
            normalized = self._normalize_job_data(job_data)
            if not normalized.is_valid() or normalized.link in seen_links:
                continue
            seen_links.add(normalized.link)
            normalized_jobs.append(normalized)

        return [self._job_result_to_tag(job) for job in normalized_jobs]

    def _extract_job_dicts_from_embedded_data(
        self,
        page_source: str,
        soup: Optional[BeautifulSoup] = None,
    ) -> List[dict[str, Any]]:
        payloads: List[Any] = []

        match = _INITIAL_DATA_RE.search(page_source)
        if match:
            decoder = json.JSONDecoder()
            try:
                payload, _ = decoder.raw_decode(page_source[match.end():])
                payloads.append(payload)
            except json.JSONDecodeError as exc:
                logger.debug("Could not decode window._initialData: %s", exc)

        search_soup = soup or BeautifulSoup(page_source, "html.parser")
        for selector in _JSON_SCRIPT_SELECTORS:
            for script in search_soup.select(selector):
                script_text = script.string or script.get_text()
                if not script_text or "title" not in script_text:
                    continue
                try:
                    payloads.append(json.loads(script_text))
                except json.JSONDecodeError:
                    continue

        jobs: List[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for payload in payloads:
            for entry in self._iter_bootstrap_job_entries(payload):
                key = self._job_identity(entry)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                jobs.append(entry)
        return jobs

    def _iter_bootstrap_job_entries(self, obj: Any) -> Iterable[dict[str, Any]]:
        if isinstance(obj, dict):
            if self._looks_like_job_dict(obj):
                yield obj

            results = obj.get("results")
            if isinstance(results, list):
                for entry in results:
                    if not isinstance(entry, dict):
                        continue
                    job_data = entry.get("job")
                    if isinstance(job_data, dict):
                        yield job_data

            for value in obj.values():
                yield from self._iter_bootstrap_job_entries(value)

        elif isinstance(obj, list):
            for item in obj:
                yield from self._iter_bootstrap_job_entries(item)

    def _looks_like_job_dict(self, obj: dict[str, Any]) -> bool:
        has_title = any(obj.get(key) for key in ("title", "jobTitle", "displayTitle"))
        has_link = any(
            obj.get(key)
            for key in ("jobUrl", "link", "url", "viewJobLink", "key", "jobkey")
        )
        return has_title and has_link

    def _job_identity(self, job_data: dict[str, Any]) -> str:
        for key in ("key", "jobkey", "jobUrl", "viewJobLink", "link", "url", "title"):
            value = job_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(id(job_data))

    def _normalize_job_data(self, job_data: dict[str, Any]) -> JobResult:
        title = str(job_data.get("title") or job_data.get("displayTitle") or "").strip()
        company = str(
            job_data.get("sourceEmployerName")
            or job_data.get("company")
            or job_data.get("companyName")
            or job_data.get("truncatedCompany")
            or ""
        ).strip()
        location = str(
            job_data.get("formattedLocation")
            or job_data.get("location")
            or job_data.get("jobLocationCity")
            or ""
        ).strip()

        if not location:
            remote_model = job_data.get("remoteWorkModel")
            if isinstance(remote_model, dict):
                location = str(remote_model.get("text") or "").strip()

        description = self._extract_description_from_job_data(job_data)
        link = self._extract_link_from_job_data(job_data)

        return JobResult.create(
            title=title,
            company=company,
            location=location,
            description=description,
            link=link,
            source="indeed",
        )

    def _extract_description_from_job_data(self, job_data: dict[str, Any]) -> str:
        snippet = job_data.get("snippet")
        if isinstance(snippet, str) and snippet.strip():
            snippet_soup = BeautifulSoup(snippet, "html.parser")
            text = extract_text(snippet_soup)
            if text:
                return text

        description = job_data.get("description")
        if isinstance(description, dict):
            text = str(description.get("text") or "").strip()
            if text:
                return text
        elif isinstance(description, str):
            clean = description.strip()
            if clean:
                return clean

        benefits: List[str] = []
        for item in self._iter_job_taxonomy_attributes(job_data):
            label = str(item.get("label") or "").strip()
            if label:
                benefits.append(label)

        return " | ".join(benefits)

    def _iter_job_taxonomy_attributes(
        self,
        job_data: dict[str, Any],
    ) -> Iterable[dict[str, Any]]:
        taxonomy_attributes = job_data.get("taxonomyAttributes")
        if not isinstance(taxonomy_attributes, list):
            return []

        for group in taxonomy_attributes:
            if not isinstance(group, dict):
                continue
            attributes = group.get("attributes")
            if not isinstance(attributes, list):
                continue
            for item in attributes:
                if isinstance(item, dict):
                    yield item

    def _extract_link_from_job_data(self, job_data: dict[str, Any]) -> str:
        for key in ("jobUrl", "viewJobLink", "link", "url"):
            value = job_data.get(key)
            if isinstance(value, str) and value.strip():
                return absolute_url(self.base_url, value)

        job_key = str(job_data.get("key") or job_data.get("jobkey") or "").strip()
        if job_key:
            return absolute_url(self.base_url, f"/viewjob?jk={job_key}")

        return ""

    def _job_result_to_tag(self, job: JobResult) -> Tag:
        soup = BeautifulSoup("", "html.parser")
        tag = soup.new_tag("article")
        tag["data-synthetic"] = "1"
        tag["data-title"] = job.title
        tag["data-company"] = job.company
        tag["data-location"] = job.location
        tag["data-description"] = job.description
        tag["data-link"] = job.link
        return tag

    def _prepare_request(self, url: str) -> None:
        if self._request_count > 0:
            random_delay(self.min_delay, self.max_delay)

        self._request_count += 1
        self._current_page_number = self._page_number_from_url(url)
        self._session.headers.update(
            build_headers(
                {
                    "User-Agent": random.choice(_USER_AGENTS),
                    "Referer": self.base_url + "/",
                    "Origin": self.base_url,
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                }
            )
        )

    def _page_number_from_url(self, url: str) -> int:
        parsed = urlparse(url)
        start_value = parse_qs(parsed.query).get("start", ["0"])[0]
        try:
            start = int(start_value)
        except (TypeError, ValueError):
            start = 0
        return (start // _RESULTS_PER_PAGE) + 1

    def _dedupe_cards(self, cards: List[Tag]) -> List[Tag]:
        deduped: List[Tag] = []
        seen: set[str] = set()

        for card in cards:
            identity = self._extract_card_identity(card)
            if identity in seen:
                continue
            seen.add(identity)
            deduped.append(card)

        return deduped

    def _extract_card_identity(self, card: Tag) -> str:
        for key in ("data-link", "data-jk"):
            value = card.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        link = self._extract_link(card)
        if link:
            return link

        title = card.get("data-title")
        if isinstance(title, str) and title.strip():
            return title.strip()

        return str(id(card))
