from __future__ import annotations

import logging

from hunter.models.dto import JobResult, normalize_key_part

logger = logging.getLogger(__name__)


class JobDeduplicationService:
    def deduplicate(self, jobs: list[JobResult]) -> tuple[list[JobResult], int]:
        canonical_seen: dict[str, JobResult] = {}
        fallback_seen: dict[str, JobResult] = {}
        duplicates_removed = 0

        for job in jobs:
            canonical_url = job.canonical_url()
            fallback_key = self._fallback_key(job)

            if canonical_url and canonical_url in canonical_seen:
                canonical_seen[canonical_url].merge(job)
                duplicates_removed += 1
                continue

            if fallback_key in fallback_seen:
                fallback_seen[fallback_key].merge(job)
                duplicates_removed += 1
                continue

            fallback_seen[fallback_key] = job
            if canonical_url:
                canonical_seen[canonical_url] = job

        deduplicated = list(fallback_seen.values())
        logger.info(
            "deduplication_completed input_jobs=%d deduplicated_jobs=%d duplicates_removed=%d",
            len(jobs),
            len(deduplicated),
            duplicates_removed,
        )
        return deduplicated, duplicates_removed

    def _fallback_key(self, job: JobResult) -> str:
        return "|".join(
            [
                normalize_key_part(job.title),
                normalize_key_part(job.company),
                normalize_key_part(job.location),
            ]
        )
