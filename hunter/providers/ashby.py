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
class AshbyBoard:
    board: str
    company: str


class AshbyProvider(BaseJobProvider):
    name = "ashby"
    api_base_url = "https://api.ashbyhq.com/posting-api/job-board"

    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        boards = self._configured_boards()
        if not boards:
            logger.info("ashby_no_boards_configured provider=%s", self.name)
            return []

        criteria = SearchCriteria(query=query, location=location)
        jobs: list[JobResult] = []
        seen: set[str] = set()
        failures = 0

        for board in boards:
            try:
                payload = self._get_json(
                    f"{self.api_base_url}/{board.board}",
                    headers={"Accept": "application/json"},
                )
                jobs_payload = self._normalize_jobs_payload(payload, keys=("jobs",))
                board_jobs = self._extract_board_jobs(
                    jobs_payload=jobs_payload,
                    board=board,
                    criteria=criteria,
                )
                logger.info(
                    "provider_target_completed provider=%s board=%s jobs=%d",
                    self.name,
                    board.board,
                    len(board_jobs),
                )
                for job in board_jobs:
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
                    "provider_target_failed provider=%s board=%s error=%s",
                    self.name,
                    board.board,
                    exc,
                )

        if failures == len(boards) and not jobs:
            raise ProviderUnavailableError("ashby could not fetch any configured board")
        return jobs

    def _configured_boards(self) -> list[AshbyBoard]:
        raw_boards = self._get_option("job_boards", [])
        boards: list[AshbyBoard] = []
        for item in raw_boards:
            if isinstance(item, str) and item.strip():
                board = item.strip()
                boards.append(
                    AshbyBoard(
                        board=board,
                        company=board.replace("-", " ").title(),
                    )
                )
                continue
            if not isinstance(item, dict):
                continue
            board = str(item.get("board") or item.get("job_board") or "").strip()
            if not board:
                continue
            company = str(item.get("company") or board.replace("-", " ").title()).strip()
            boards.append(AshbyBoard(board=board, company=company))
        return boards

    def _extract_board_jobs(
        self,
        *,
        jobs_payload: list[dict[str, Any]],
        board: AshbyBoard,
        criteria: SearchCriteria,
    ) -> list[JobResult]:
        results: list[JobResult] = []
        for item in jobs_payload:
            if item.get("isListed") is False:
                continue

            primary_location = str(item.get("location") or "").strip()
            secondary_locations = self._extract_secondary_locations(item)
            workplace_type = str(item.get("workplaceType") or "").strip().lower()
            description = str(item.get("descriptionPlain") or "").strip()
            searchable = " ".join(
                [
                    str(item.get("title") or ""),
                    description,
                    primary_location,
                    " ".join(secondary_locations),
                    str(item.get("department") or ""),
                    str(item.get("team") or ""),
                    str(item.get("employmentType") or ""),
                ]
            )

            if not criteria.matches_query(searchable):
                continue
            if not criteria.matches_location(
                primary_location,
                extra_locations=secondary_locations,
                is_remote=bool(item.get("isRemote")) or workplace_type == "remote",
            ):
                continue

            job = JobResult.create(
                title=str(item.get("title") or ""),
                company=board.company,
                location=primary_location or self._fallback_location(secondary_locations, item),
                description=description,
                link=str(item.get("jobUrl") or item.get("applyUrl") or ""),
                source=self.name,
            )
            if job.is_valid():
                results.append(job)
        return results

    def _extract_secondary_locations(self, item: dict[str, Any]) -> list[str]:
        locations: list[str] = []
        for secondary in item.get("secondaryLocations") or []:
            if not isinstance(secondary, dict):
                continue
            text = str(secondary.get("location") or "").strip()
            if text and text not in locations:
                locations.append(text)
        return locations

    def _fallback_location(self, secondary_locations: list[str], item: dict[str, Any]) -> str:
        if secondary_locations:
            return secondary_locations[0]
        if item.get("isRemote") or str(item.get("workplaceType") or "").lower() == "remote":
            return "Remote"
        postal_address = ((item.get("address") or {}).get("postalAddress") or {})
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            value = str(postal_address.get(key) or "").strip()
            if value:
                return value
        return ""
