from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag

from hunter.models.dto import JobResult

from .base import (
    BaseJobProvider,
    ProviderBlockedError,
    ProviderParseError,
    absolute_url,
    extract_text,
)

logger = logging.getLogger(__name__)

_RESULTS_PER_PAGE = 10
_JSON_SCRIPT_SELECTORS = [
    "script[type='application/json']",
    "script#__NEXT_DATA__",
]
_INITIAL_DATA_RE = re.compile(r"window\._initialData\s*=\s*", re.DOTALL)
_CARD_SELECTORS = [
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


class IndeedProvider(BaseJobProvider):
    name = "indeed"
    base_url = "https://www.indeed.com"

    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        capped_pages = self._cap_pages(max_pages)
        jobs: list[JobResult] = []

        self._prime_session()
        for page in range(1, capped_pages + 1):
            soup = self._fetch_search_page(query=query, location=location, page=page)
            page_jobs = self._extract_jobs_from_soup(soup)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
            if page < capped_pages:
                self._pause()
        return jobs

    def _prime_session(self) -> None:
        try:
            self._request(
                f"{self.base_url}/",
                headers={
                    "Referer": self.base_url,
                    "Origin": self.base_url,
                },
                blocked_statuses=(403,),
            )
        except ProviderBlockedError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.debug("indeed_prime_session_failed error=%s", exc)

    def _fetch_search_page(
        self,
        *,
        query: str,
        location: str,
        page: int,
    ) -> BeautifulSoup:
        offset = max(page - 1, 0) * _RESULTS_PER_PAGE
        url = f"{self.base_url}/jobs?q={quote_plus(query.strip())}"
        if location.strip():
            url += f"&l={quote_plus(location.strip())}"
        if offset:
            url += f"&start={offset}"
        return self._get_soup(
            url,
            headers={
                "Referer": self.base_url + "/",
                "Origin": self.base_url,
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
            },
            blocked_statuses=(403,),
        )

    def _extract_jobs_from_soup(self, soup: BeautifulSoup) -> list[JobResult]:
        if self._is_blocked(soup):
            raise ProviderBlockedError("Indeed responded with a blocked page")

        for selector in _CARD_SELECTORS:
            cards = [card for card in soup.select(selector) if isinstance(card, Tag)]
            if cards:
                return self._normalize_cards(cards)

        return self._extract_jobs_from_bootstrap_data(str(soup), soup=soup)

    def _normalize_cards(self, cards: list[Tag]) -> list[JobResult]:
        jobs: list[JobResult] = []
        seen: set[str] = set()
        for card in cards:
            job = JobResult.create(
                title=self._extract_title(card),
                company=self._extract_company(card),
                location=self._extract_location(card),
                description=self._extract_description(card),
                link=self._extract_link(card),
                source=self.name,
            )
            if not job.is_valid():
                continue
            dedupe_key = job.deduplication_key()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            jobs.append(job)
        return jobs

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
            card.find("span", class_=lambda c: c and "company" in str(c).lower()),
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
            card.find(class_=lambda c: c and "location" in str(c).lower()),
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

        anchor = card.find("a", href=True)
        if isinstance(anchor, Tag):
            return absolute_url(self.base_url, str(anchor.get("href") or ""))
        return ""

    def _extract_description(self, card: Tag) -> str:
        candidates = [
            card.find("div", class_=lambda c: c and "job-snippet" in str(c)),
            card.find("div", attrs={"data-testid": "job-snippet"}),
            card.find("div", class_=lambda c: c and "snippet" in str(c).lower()),
        ]
        for tag in candidates:
            text = extract_text(tag)
            if text:
                return text
        return ""

    def _is_blocked(self, soup: BeautifulSoup) -> bool:
        title = extract_text(soup.title).lower()
        page_text = soup.get_text(" ", strip=True).lower()
        if any(keyword in title for keyword in _BLOCK_TITLE_KEYWORDS):
            return True
        return any(pattern in page_text for pattern in _BLOCK_TEXT_PATTERNS)

    def _extract_jobs_from_bootstrap_data(
        self,
        page_source: str,
        *,
        soup: BeautifulSoup | None = None,
    ) -> list[JobResult]:
        jobs: list[JobResult] = []
        seen: set[str] = set()
        for job_data in self._extract_job_dicts_from_embedded_data(page_source, soup=soup):
            job = self._normalize_job_data(job_data)
            if not job.is_valid():
                continue
            dedupe_key = job.deduplication_key()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            jobs.append(job)
        if not jobs and page_source.strip():
            raise ProviderParseError(f"{self.name} response did not contain parseable jobs")
        return jobs

    def _extract_job_dicts_from_embedded_data(
        self,
        page_source: str,
        *,
        soup: BeautifulSoup | None = None,
    ) -> list[dict[str, Any]]:
        payloads: list[Any] = []
        match = _INITIAL_DATA_RE.search(page_source)
        if match:
            decoder = json.JSONDecoder()
            try:
                payload, _ = decoder.raw_decode(page_source[match.end():])
                payloads.append(payload)
            except json.JSONDecodeError:
                pass

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

        jobs: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for payload in payloads:
            for entry in self._iter_bootstrap_job_entries(payload):
                identity = self._job_identity(entry)
                if identity in seen_keys:
                    continue
                seen_keys.add(identity)
                jobs.append(entry)
        return jobs

    def _iter_bootstrap_job_entries(self, payload: Any) -> Iterable[dict[str, Any]]:
        if isinstance(payload, dict):
            if self._looks_like_job_dict(payload):
                yield payload

            results = payload.get("results")
            if isinstance(results, list):
                for entry in results:
                    if not isinstance(entry, dict):
                        continue
                    job_data = entry.get("job")
                    if isinstance(job_data, dict):
                        yield job_data

            for value in payload.values():
                yield from self._iter_bootstrap_job_entries(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from self._iter_bootstrap_job_entries(item)

    def _looks_like_job_dict(self, payload: dict[str, Any]) -> bool:
        has_title = any(payload.get(key) for key in ("title", "jobTitle", "displayTitle"))
        has_link = any(
            payload.get(key)
            for key in ("jobUrl", "link", "url", "viewJobLink", "key", "jobkey")
        )
        return has_title and has_link

    def _job_identity(self, payload: dict[str, Any]) -> str:
        for key in ("key", "jobkey", "jobUrl", "viewJobLink", "link", "url", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(id(payload))

    def _normalize_job_data(self, payload: dict[str, Any]) -> JobResult:
        location = str(
            payload.get("formattedLocation")
            or payload.get("location")
            or payload.get("jobLocationCity")
            or ""
        ).strip()
        if not location:
            remote_model = payload.get("remoteWorkModel")
            if isinstance(remote_model, dict):
                location = str(remote_model.get("text") or "").strip()

        return JobResult.create(
            title=str(payload.get("title") or payload.get("displayTitle") or ""),
            company=str(
                payload.get("sourceEmployerName")
                or payload.get("company")
                or payload.get("companyName")
                or payload.get("truncatedCompany")
                or ""
            ),
            location=location,
            description=self._extract_description_from_job_data(payload),
            link=self._extract_link_from_job_data(payload),
            source=self.name,
        )

    def _extract_description_from_job_data(self, payload: dict[str, Any]) -> str:
        snippet = payload.get("snippet")
        if isinstance(snippet, str) and snippet.strip():
            return extract_text(BeautifulSoup(snippet, "html.parser"))

        description = payload.get("description")
        if isinstance(description, dict):
            return str(description.get("text") or "").strip()
        if isinstance(description, str):
            return description.strip()

        benefits: list[str] = []
        for item in self._iter_job_taxonomy_attributes(payload):
            label = str(item.get("label") or "").strip()
            if label:
                benefits.append(label)
        return " | ".join(benefits)

    def _iter_job_taxonomy_attributes(
        self,
        payload: dict[str, Any],
    ) -> Iterable[dict[str, Any]]:
        taxonomy_attributes = payload.get("taxonomyAttributes")
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

    def _extract_link_from_job_data(self, payload: dict[str, Any]) -> str:
        for key in ("jobUrl", "viewJobLink", "link", "url"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return absolute_url(self.base_url, value)
        job_key = str(payload.get("key") or payload.get("jobkey") or "").strip()
        if job_key:
            return absolute_url(self.base_url, f"/viewjob?jk={job_key}")
        return ""
