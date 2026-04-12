from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from hunter.models.dto import JobResult

from .base import (
    BaseJobProvider,
    ProviderBlockedError,
    ProviderInvalidResponseError,
    ProviderParseError,
    ProviderUnavailableError,
    absolute_url,
)
from .search import SearchCriteria

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GreenhouseBoard:
    token: str
    company: str


class GreenhouseProvider(BaseJobProvider):
    name = "greenhouse"
    api_base_url = "https://boards-api.greenhouse.io/v1/boards"

    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        boards = self._configured_boards()
        if not boards:
            logger.info("greenhouse_no_boards_configured provider=%s", self.name)
            return []

        criteria = SearchCriteria(query=query, location=location)
        jobs: list[JobResult] = []
        seen: set[str] = set()
        failures = 0

        for board in boards:
            try:
                payload = self._get_json(
                    f"{self.api_base_url}/{board.token}/jobs",
                    params={"content": "true"},
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
                    board.token,
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
                    board.token,
                    exc,
                )

        if failures == len(boards) and not jobs:
            raise ProviderUnavailableError("greenhouse could not fetch any configured board")
        return jobs

    def _configured_boards(self) -> list[GreenhouseBoard]:
        raw_boards = self._get_option("board_tokens", [])
        boards: list[GreenhouseBoard] = []
        for item in raw_boards:
            if isinstance(item, str) and item.strip():
                token = item.strip()
                boards.append(
                    GreenhouseBoard(
                        token=token,
                        company=token.replace("-", " ").title(),
                    )
                )
                continue
            if not isinstance(item, dict):
                continue
            token = str(item.get("token") or item.get("board_token") or "").strip()
            if not token:
                continue
            company = str(item.get("company") or token.replace("-", " ").title()).strip()
            boards.append(GreenhouseBoard(token=token, company=company))
        return boards

    def _extract_board_jobs(
        self,
        *,
        jobs_payload: list[dict[str, Any]],
        board: GreenhouseBoard,
        criteria: SearchCriteria,
    ) -> list[JobResult]:
        results: list[JobResult] = []
        for item in jobs_payload:
            location = self._extract_location(item)
            office_locations = self._extract_office_locations(item)
            content = self._extract_content(item)
            searchable = " ".join(
                [
                    str(item.get("title") or ""),
                    location,
                    content,
                    " ".join(self._extract_names(item.get("departments"))),
                    " ".join(office_locations),
                ]
            )

            if not criteria.matches_query(searchable):
                continue
            if not criteria.matches_location(
                location,
                extra_locations=office_locations,
                is_remote="remote" in " ".join([location, *office_locations]).lower(),
            ):
                continue

            job = JobResult.create(
                title=str(item.get("title") or ""),
                company=board.company,
                location=location or "Remote",
                description=content,
                link=absolute_url(
                    f"https://boards.greenhouse.io/{board.token}/",
                    str(item.get("absolute_url") or ""),
                ),
                source=self.name,
            )
            if job.is_valid():
                results.append(job)
        return results

    def _extract_location(self, item: dict[str, Any]) -> str:
        location = item.get("location")
        if isinstance(location, dict):
            return str(location.get("name") or "").strip()
        if isinstance(location, str):
            return location.strip()
        office_locations = self._extract_office_locations(item)
        return office_locations[0] if office_locations else ""

    def _extract_office_locations(self, item: dict[str, Any]) -> list[str]:
        locations: list[str] = []
        for office in item.get("offices") or []:
            if not isinstance(office, dict):
                continue
            for value in (office.get("location"), office.get("name")):
                text = str(value or "").strip()
                if text and text not in locations:
                    locations.append(text)
        return locations

    def _extract_names(self, values: object) -> list[str]:
        names: list[str] = []
        if not isinstance(values, list):
            return names
        for item in values:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                names.append(name)
        return names

    def _extract_content(self, item: dict[str, Any]) -> str:
        content = str(item.get("content") or "").strip()
        if not content:
            return ""
        return BeautifulSoup(content, "html.parser").get_text(" ", strip=True)
