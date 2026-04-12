from __future__ import annotations

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
from .search import SearchCriteria


class WeWorkRemotelyProvider(BaseJobProvider):
    name = "weworkremotely"
    base_url = "https://weworkremotely.com"

    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        criteria = SearchCriteria(query=query, location=location)
        soup = self._get_soup(
            f"{self.base_url}/remote-jobs/search?term={quote_plus(query.strip())}",
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
        if self._is_blocked(soup):
            raise ProviderBlockedError(f"{self.name} returned a blocked page")

        listings = self._extract_listings(soup)

        results: list[JobResult] = []
        for listing in listings:
            if not isinstance(listing, Tag):
                continue
            anchor = listing.find("a", href=True)
            if not isinstance(anchor, Tag):
                continue

            company = extract_text(listing.select_one(".company"))
            title = extract_text(listing.select_one(".title"))
            candidate_location = extract_text(
                listing.select_one(".region.company")
            ) or extract_text(listing.select_one(".region"))

            if not criteria.matches_location(
                candidate_location,
                is_remote="remote" in candidate_location.lower(),
            ):
                continue

            results.append(
                JobResult.create(
                    title=title,
                    company=company,
                    location=candidate_location or "Remote",
                    description=extract_text(listing.select_one(".featured")),
                    link=absolute_url(self.base_url, str(anchor.get("href") or "")),
                    source=self.name,
                )
            )
        return [job for job in results if job.is_valid()]

    def _extract_listings(self, soup: BeautifulSoup) -> list[Tag]:
        selectors = [
            "section.jobs article ul li",
            "section.jobs li",
            "main li a[href*='/remote-jobs/']",
        ]
        for selector in selectors:
            listings = [item for item in soup.select(selector) if isinstance(item, Tag)]
            if listings:
                return listings
        raise ProviderParseError(f"{self.name} did not return recognizable job listings")

    def _is_blocked(self, soup: BeautifulSoup) -> bool:
        title = extract_text(soup.title).lower()
        page_text = soup.get_text(" ", strip=True).lower()
        blocked_markers = (
            "403",
            "access denied",
            "forbidden",
            "cloudflare",
            "captcha",
            "security check",
        )
        return any(marker in title or marker in page_text for marker in blocked_markers)
