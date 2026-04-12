from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from hunter.models.dto import JobResult

from .base import (
    BaseJobProvider,
    ProviderBlockedError,
    ProviderInvalidResponseError,
    ProviderParseError,
    ProviderUnavailableError,
)
from .search import SearchCriteria

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LeverSite:
    site: str
    company: str


class LeverProvider(BaseJobProvider):
    name = "lever"
    api_base_url = "https://api.lever.co/v0/postings"

    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        sites = self._configured_sites()
        if not sites:
            logger.info("lever_no_sites_configured provider=%s", self.name)
            return []

        criteria = SearchCriteria(query=query, location=location)
        jobs: list[JobResult] = []
        seen: set[str] = set()
        failures = 0

        for site in sites:
            try:
                payload = self._get_json(
                    f"{self.api_base_url}/{site.site}",
                    params={"mode": "json", "limit": 100},
                    headers={"Accept": "application/json"},
                )
                jobs_payload = self._normalize_jobs_payload(payload, keys=("data",))
                site_jobs = self._extract_site_jobs(
                    jobs_payload=jobs_payload,
                    site=site,
                    criteria=criteria,
                )
                logger.info(
                    "provider_target_completed provider=%s site=%s jobs=%d",
                    self.name,
                    site.site,
                    len(site_jobs),
                )
                for job in site_jobs:
                    dedupe_key = job.deduplication_key()
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    jobs.append(job)
            except (
                ProviderBlockedError,
                ProviderInvalidResponseError,
                ProviderParseError,
                ProviderUnavailableError,
            ) as exc:
                failures += 1
                logger.warning(
                    "provider_target_failed provider=%s site=%s error=%s",
                    self.name,
                    site.site,
                    exc,
                )

        if failures == len(sites) and not jobs:
            raise ProviderUnavailableError("lever could not fetch any configured site")
        return jobs

    def _configured_sites(self) -> list[LeverSite]:
        raw_sites = self._get_option("sites", [])
        sites: list[LeverSite] = []
        for item in raw_sites:
            if isinstance(item, str) and item.strip():
                site = item.strip()
                sites.append(
                    LeverSite(
                        site=site,
                        company=site.replace("-", " ").title(),
                    )
                )
                continue
            if not isinstance(item, dict):
                continue
            site = str(item.get("site") or "").strip()
            if not site:
                continue
            company = str(item.get("company") or site.replace("-", " ").title()).strip()
            sites.append(LeverSite(site=site, company=company))
        return sites

    def _extract_site_jobs(
        self,
        *,
        jobs_payload: list[dict[str, Any]],
        site: LeverSite,
        criteria: SearchCriteria,
    ) -> list[JobResult]:
        results: list[JobResult] = []
        for item in jobs_payload:
            categories = item.get("categories") or {}
            if not isinstance(categories, dict):
                categories = {}

            primary_location = str(categories.get("location") or "").strip()
            all_locations = self._extract_all_locations(categories)
            workplace_type = str(item.get("workplaceType") or "").strip().lower()
            description = self._extract_description(item)
            searchable = " ".join(
                [
                    str(item.get("text") or ""),
                    description,
                    primary_location,
                    " ".join(all_locations),
                    str(categories.get("team") or ""),
                    str(categories.get("department") or ""),
                    str(categories.get("commitment") or ""),
                ]
            )

            if not criteria.matches_query(searchable):
                continue
            if not criteria.matches_location(
                primary_location,
                extra_locations=all_locations,
                is_remote=workplace_type == "remote" or "remote" in searchable.lower(),
            ):
                continue

            job = JobResult.create(
                title=str(item.get("text") or ""),
                company=site.company,
                location=primary_location or self._fallback_location(all_locations, workplace_type),
                description=description,
                link=str(item.get("hostedUrl") or item.get("applyUrl") or ""),
                source=self.name,
            )
            if job.is_valid():
                results.append(job)
        return results

    def _extract_all_locations(self, categories: dict[str, Any]) -> list[str]:
        locations: list[str] = []
        all_locations = categories.get("allLocations")
        if isinstance(all_locations, list):
            for value in all_locations:
                text = str(value or "").strip()
                if text and text not in locations:
                    locations.append(text)
        location = str(categories.get("location") or "").strip()
        if location and location not in locations:
            locations.insert(0, location)
        return locations

    def _extract_description(self, item: dict[str, Any]) -> str:
        description_parts = [
            str(item.get("descriptionPlain") or "").strip(),
            str(item.get("descriptionBodyPlain") or "").strip(),
            str(item.get("openingPlain") or "").strip(),
            str(item.get("additionalPlain") or "").strip(),
        ]
        for entry in item.get("lists") or []:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("text") or "").strip()
            content = str(entry.get("content") or "").strip()
            if label and content:
                description_parts.append(f"{label}: {content}")
        return " ".join(part for part in description_parts if part)

    def _fallback_location(self, all_locations: list[str], workplace_type: str) -> str:
        if all_locations:
            return all_locations[0]
        if workplace_type == "remote":
            return "Remote"
        return ""
