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
)
from hunter.providers.registry import build_enabled_providers

from .job_deduplication_service import JobDeduplicationService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AggregationResult:
    jobs: list[JobResult] = field(default_factory=list)
    provider_results: list[ProviderRunResult] = field(default_factory=list)
    duplicates_removed: int = 0
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
    def scraped(self) -> int:
        return len(self.jobs)

    @property
    def status(self) -> str:
        if self.providers_succeeded and self.providers_failed:
            return "partial_success"
        if self.providers_succeeded:
            return "success"
        return "error"


class JobAggregationService:
    def __init__(
        self,
        *,
        providers: list[BaseJobProvider] | None = None,
        deduplication_service: JobDeduplicationService | None = None,
    ) -> None:
        self.providers = providers or build_enabled_providers()
        self.deduplication_service = deduplication_service or JobDeduplicationService()

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
                provider.close()

        jobs, duplicates_removed = self.deduplication_service.deduplicate(collected_jobs)
        duration = time.perf_counter() - started
        logger.info(
            "aggregation_completed providers_run=%d providers_succeeded=%d providers_failed=%d providers_blocked=%d providers_invalid_response=%d scraped=%d duplicates_removed=%d duration_seconds=%.3f",
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
            len(jobs),
            duplicates_removed,
            duration,
        )

        return AggregationResult(
            jobs=jobs,
            provider_results=provider_results,
            duplicates_removed=duplicates_removed,
            duration_seconds=duration,
        )
