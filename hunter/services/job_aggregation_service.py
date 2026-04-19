from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from hunter.models.dto import JobResult
from hunter.providers.base import (
    BaseJobProvider,
    ProviderRunResult,
    FAILURE_BLOCKED,
    FAILURE_INVALID_RESPONSE,
    FAILURE_PARSE_ERROR,
    FAILURE_UNAVAILABLE,
)
from hunter.providers.registry import build_enabled_providers

from .job_deduplication_service import JobDeduplicationService
from .job_quality_service import JobQualityService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AggregationResult:
    jobs: list[JobResult] = field(default_factory=list)
    provider_results: list[ProviderRunResult] = field(default_factory=list)
    duplicates_removed: int = 0
    quality_filtered: int = 0
    quality_issue_counts: dict[str, int] = field(default_factory=dict)
    duration_seconds: float = 0.0

    @property
    def providers_run(self) -> list[str]:
        return [result.provider for result in self.provider_results]

    @property
    def providers_succeeded(self) -> list[str]:
        return [result.provider for result in self.provider_results if result.success]

    @property
    def providers_failed(self) -> list[str]:
        return [result.provider for result in self.provider_results if not result.success]

    @property
    def providers_blocked(self) -> list[str]:
        return [
            result.provider
            for result in self.provider_results
            if result.failure_type == FAILURE_BLOCKED
        ]

    @property
    def providers_invalid_response(self) -> list[str]:
        return [
            result.provider
            for result in self.provider_results
            if result.failure_type == FAILURE_INVALID_RESPONSE
        ]

    @property
    def providers_unavailable(self) -> list[str]:
        return [
            result.provider
            for result in self.provider_results
            if result.failure_type == FAILURE_UNAVAILABLE
        ]

    @property
    def providers_parse_error(self) -> list[str]:
        return [
            result.provider
            for result in self.provider_results
            if result.failure_type == FAILURE_PARSE_ERROR
        ]

    @property
    def provider_failure_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in self.provider_results:
            if result.success:
                continue
            key = result.failure_type or "unknown"
            counts[key] = counts.get(key, 0) + 1
        return counts

    @property
    def provider_job_counts(self) -> dict[str, int]:
        return {result.provider: result.count for result in self.provider_results}

    @property
    def raw_scraped(self) -> int:
        return sum(result.count for result in self.provider_results)

    @property
    def scraped(self) -> int:
        return len(self.jobs)

    @property
    def status(self) -> str:
        if self.providers_succeeded and self.providers_failed:
            return "partial_success"
        if self.providers_succeeded:
            return "success"
        return "total_failure"


class JobAggregationService:
    def __init__(
        self,
        *,
        providers: list[BaseJobProvider] | None = None,
        deduplication_service: JobDeduplicationService | None = None,
        quality_service: JobQualityService | None = None,
    ) -> None:
        self.providers = providers or build_enabled_providers()
        self.deduplication_service = deduplication_service or JobDeduplicationService()
        self.quality_service = quality_service or JobQualityService()

    def aggregate(self, *, query: str, location: str = "") -> AggregationResult:
        started = time.perf_counter()
        collected_jobs: list[JobResult] = []
        provider_results: list[ProviderRunResult] = []

        try:
            for provider in self.providers:
                result = provider.run(query=query, location=location)
                provider_results.append(result)
                collected_jobs.extend(result.jobs)
        finally:
            for provider in self.providers:
                try:
                    provider.close()
                except Exception:
                    logger.debug("provider_close_failed provider=%s", provider.__class__.__name__)

        quality_filtered = 0
        quality_issue_counts: dict[str, int] = {}
        duplicates_removed = 0
        jobs: list[JobResult] = collected_jobs
        try:
            quality_result = self.quality_service.prepare(collected_jobs)
            jobs, duplicates_removed = self.deduplication_service.deduplicate(quality_result.jobs)
            quality_filtered = quality_result.rejected
            quality_issue_counts = quality_result.issue_counts
        except Exception:
            logger.exception("aggregation_post_processing_failed")

        duration = time.perf_counter() - started
        logger.info(
            "aggregation_completed providers_run=%d providers_succeeded=%d providers_failed=%d providers_blocked=%d providers_invalid_response=%d providers_unavailable=%d raw_scraped=%d quality_filtered=%d scraped=%d duplicates_removed=%d provider_job_counts=%s quality_issue_counts=%s duration_seconds=%.3f",
            len(provider_results),
            len([result for result in provider_results if result.success]),
            len([result for result in provider_results if not result.success]),
            len([result for result in provider_results if result.failure_type == FAILURE_BLOCKED]),
            len(
                [
                    result
                    for result in provider_results
                    if result.failure_type == FAILURE_INVALID_RESPONSE
                ]
            ),
            len([result for result in provider_results if result.failure_type == FAILURE_UNAVAILABLE]),
            sum(result.count for result in provider_results),
            quality_filtered,
            len(jobs),
            duplicates_removed,
            {result.provider: result.count for result in provider_results},
            quality_issue_counts,
            duration,
        )

        return AggregationResult(
            jobs=jobs,
            provider_results=provider_results,
            duplicates_removed=duplicates_removed,
            quality_filtered=quality_filtered,
            quality_issue_counts=quality_issue_counts,
            duration_seconds=duration,
        )
