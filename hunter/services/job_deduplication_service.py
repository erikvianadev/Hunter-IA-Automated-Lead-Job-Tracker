from __future__ import annotations

import logging

from hunter.models.dto import JobResult, normalize_key_part

logger = logging.getLogger(__name__)


class JobDeduplicationService:
    def deduplicate(self, jobs: list[JobResult]) -> tuple[list[JobResult], int]:
        seen: dict[str, JobResult] = {}
        deduplicated: list[JobResult] = []
        duplicates_removed = 0

        for job in jobs:
            keys = self._dedupe_keys(job)
            existing = next((seen[key] for key in keys if key in seen), None)
            if existing:
                existing.merge(job)
                self._register_keys(seen, existing, keys)
                duplicates_removed += 1
                continue

            deduplicated.append(job)
            self._register_keys(seen, job, keys)

        logger.info(
            "deduplication_completed input_jobs=%d deduplicated_jobs=%d duplicates_removed=%d",
            len(jobs),
            len(deduplicated),
            duplicates_removed,
        )
        return deduplicated, duplicates_removed

    def _dedupe_keys(self, job: JobResult) -> list[str]:
        keys: list[str] = []
        canonical_url = job.canonical_url()
        if canonical_url:
            keys.append(f"url:{canonical_url}")

        fallback_key = self._fallback_key(job)
        if fallback_key:
            keys.append(f"fallback:{fallback_key}")

        role_company_key = self._role_company_key(job)
        if role_company_key:
            keys.append(f"role_company:{role_company_key}")

        return keys

    def _register_keys(
        self,
        seen: dict[str, JobResult],
        job: JobResult,
        keys: list[str],
    ) -> None:
        for key in keys:
            seen[key] = job

    def _fallback_key(self, job: JobResult) -> str:
        title = normalize_key_part(job.title)
        company = normalize_key_part(job.company)
        location = self._normalize_location(job.location)
        if not title or not company or not location:
            return ""
        return "|".join([title, company, location])

    def _role_company_key(self, job: JobResult) -> str:
        title = normalize_key_part(job.title)
        company = normalize_key_part(job.company)
        if not title or not company:
            return ""
        return "|".join([title, company])

    def _normalize_location(self, value: str) -> str:
        normalized = normalize_key_part(value)
        remote_markers = {"anywhere", "global", "remote", "remota", "remoto", "worldwide"}
        if any(marker in normalized for marker in remote_markers):
            return "remote"
        return normalized
