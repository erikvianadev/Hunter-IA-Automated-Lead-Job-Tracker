from __future__ import annotations

import logging

from hunter.models.dto import JobResult

from .base import BaseJobProvider
from .search import SearchCriteria

logger = logging.getLogger(__name__)

_DEFAULT_COUNTRIES = ["us", "gb"]
_RESULTS_PER_PAGE = 20


class AdzunaProvider(BaseJobProvider):
    """
    Adzuna Jobs API provider.

    Requires ADZUNA_APP_ID and ADZUNA_APP_KEY in provider options.
    Returns 0 jobs silently when credentials are absent (provider stays enabled
    but inactive until the operator supplies the keys).

    Free tier: https://developer.adzuna.com (250 requests/month).
    """

    name = "adzuna"
    base_url = "https://api.adzuna.com"

    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        app_id = str(self._get_option("app_id", "") or "").strip()
        app_key = str(self._get_option("app_key", "") or "").strip()
        if not app_id or not app_key:
            logger.info(
                "adzuna_credentials_absent provider=%s skipping — set ADZUNA_APP_ID and ADZUNA_APP_KEY to activate",
                self.name,
            )
            return []

        countries: list[str] = list(self._get_option("countries") or _DEFAULT_COUNTRIES)
        criteria = SearchCriteria(query=query, location=location)
        results: list[JobResult] = []
        country_errors: list[Exception] = []
        any_fetch_succeeded = False

        for country in countries:
            try:
                country_jobs = self._fetch_country(
                    app_id=app_id,
                    app_key=app_key,
                    country=country,
                    query=query,
                    location=location,
                    criteria=criteria,
                )
                results.extend(country_jobs)
                any_fetch_succeeded = True
                logger.info(
                    "adzuna_country_done country=%s jobs=%d",
                    country,
                    len(country_jobs),
                )
            except Exception as exc:
                country_errors.append(exc)
                logger.warning(
                    "adzuna_country_failed country=%s error=%s",
                    country,
                    exc,
                )

        if not any_fetch_succeeded and country_errors:
            raise country_errors[-1]

        return [job for job in results if job.is_valid()]

    def _fetch_country(
        self,
        *,
        app_id: str,
        app_key: str,
        country: str,
        query: str,
        location: str,
        criteria: SearchCriteria,
    ) -> list[JobResult]:
        url = f"{self.base_url}/v1/api/jobs/{country}/search/1"
        params: dict[str, object] = {
            "app_id": app_id,
            "app_key": app_key,
            "what": query.strip(),
            "results_per_page": _RESULTS_PER_PAGE,
        }
        if location.strip() and not criteria.remote_location:
            params["where"] = location.strip()

        payload = self._get_json(url, params=params, headers={"Accept": "application/json"})
        raw_jobs = self._normalize_jobs_payload(payload, keys=("results",))

        results: list[JobResult] = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title") or "")

            company_raw = item.get("company") or {}
            company = (
                str(company_raw.get("display_name") or "")
                if isinstance(company_raw, dict)
                else str(company_raw or "")
            )

            location_raw = item.get("location") or {}
            candidate_location = (
                str(location_raw.get("display_name") or "")
                if isinstance(location_raw, dict)
                else str(location_raw or "")
            )

            description = str(item.get("description") or "")
            link = str(item.get("redirect_url") or "")

            searchable = " ".join(
                [title, company, description, candidate_location]
            ).lower()

            if not criteria.matches_query(searchable):
                logger.debug(
                    "adzuna_discard_query country=%s title=%r",
                    country,
                    title[:80],
                )
                continue

            # When searching for remote jobs we omit `where` from the API call
            # and trust Adzuna's own filtering — Adzuna labels jobs with city
            # names, not "Remote", so a local remote-location check would
            # discard every result.
            if not criteria.remote_location and not criteria.matches_location(
                candidate_location,
                is_remote="remote" in candidate_location.lower(),
            ):
                logger.debug(
                    "adzuna_discard_location country=%s title=%r candidate_location=%r",
                    country,
                    title[:80],
                    candidate_location[:60],
                )
                continue

            results.append(
                JobResult.create(
                    title=title,
                    company=company,
                    location=candidate_location or "Remote",
                    description=description,
                    link=link,
                    source=self.name,
                )
            )

        return results
