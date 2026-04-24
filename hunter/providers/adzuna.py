from __future__ import annotations

import logging

from hunter.models.dto import JobResult

from .base import BaseJobProvider
from .search import SearchCriteria

logger = logging.getLogger(__name__)

_DEFAULT_COUNTRIES = ["us", "gb"]
_RESULTS_PER_PAGE = 20

# Location tokens that indicate a Brazil-scoped search.
_BRAZIL_LOCATION_MARKERS = frozenset({"brasil", "brazil", "br"})

# PT-BR synonyms sent as extra terms in the `what=` parameter for Brazil searches.
# Keeps the English term first so Adzuna's relevance ranking stays intact.
_PTBR_SYNONYMS: dict[str, list[str]] = {
    "tech lead": ["líder técnico", "lider tecnico", "technical lead", "lead developer"],
    "backend engineer": ["desenvolvedor backend", "engenheiro backend", "backend developer"],
    "frontend engineer": ["desenvolvedor frontend", "frontend developer"],
    "python developer": ["desenvolvedor python"],
    "data engineer": ["engenheiro de dados"],
    "data scientist": ["cientista de dados"],
    "software engineer": ["engenheiro de software"],
    "full stack": ["fullstack", "full-stack"],
}


def _resolve_countries(location_normalized: str, default: list[str]) -> list[str]:
    """Return Adzuna country codes for a normalized location string.

    Returns ["br"] when the location is a Brazil marker (brasil / brazil / br).
    Falls back to *default* for every other location value.
    """
    if not location_normalized:
        return default
    tokens = set(location_normalized.split())
    if tokens & _BRAZIL_LOCATION_MARKERS:
        return ["br"]
    return default


def _expand_query_ptbr(query: str) -> str:
    """Append PT-BR synonym terms to *query* for the Brazil endpoint.

    Only expands when the normalized query has a known mapping; otherwise
    returns the query unchanged so existing behavior is preserved.
    """
    synonyms = _PTBR_SYNONYMS.get(query.strip().lower(), [])
    if not synonyms:
        return query
    return " OR ".join([query] + synonyms)


def _ptbr_matches(query_normalized: str, searchable: str) -> bool:
    """True if any PT-BR synonym for *query_normalized* appears in *searchable*."""
    synonyms = _PTBR_SYNONYMS.get(query_normalized, [])
    return any(syn in searchable for syn in synonyms)


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

        default_countries: list[str] = list(self._get_option("countries") or _DEFAULT_COUNTRIES)
        criteria = SearchCriteria(query=query, location=location)

        # For non-remote searches, detect Brazilian location and override country list.
        if criteria.remote_location:
            countries = default_countries
        else:
            countries = _resolve_countries(criteria.location, default_countries)

        brazil_search = countries == ["br"]

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
                    brazil_search=brazil_search,
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
        brazil_search: bool = False,
    ) -> list[JobResult]:
        url = f"{self.base_url}/v1/api/jobs/{country}/search/1"

        # For Brazil searches expand the query with PT-BR synonyms so Adzuna
        # returns jobs whose titles are in Portuguese.
        what_param = _expand_query_ptbr(query.strip()) if brazil_search else query.strip()

        params: dict[str, object] = {
            "app_id": app_id,
            "app_key": app_key,
            "what": what_param,
            "results_per_page": _RESULTS_PER_PAGE,
        }

        # Omit `where` for:
        #   • remote searches (trust Adzuna's own remote filtering)
        #   • Brazil country-level markers (the `br` endpoint already scopes to Brazil)
        location_is_country_marker = criteria.location in _BRAZIL_LOCATION_MARKERS
        if location.strip() and not criteria.remote_location and not location_is_country_marker:
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
                # For Brazil searches also accept jobs whose titles use PT-BR
                # synonyms (e.g. "Líder Técnico" for query "tech lead").
                if not (brazil_search and _ptbr_matches(criteria.query, searchable)):
                    logger.debug(
                        "adzuna_discard_query country=%s title=%r",
                        country,
                        title[:80],
                    )
                    continue

            # Location filter is skipped for:
            #   • remote searches — Adzuna labels jobs with city names, not "Remote"
            #   • Brazil searches — the `br` endpoint + optional `where=` already filtered
            if not criteria.remote_location and not brazil_search and not criteria.matches_location(
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
