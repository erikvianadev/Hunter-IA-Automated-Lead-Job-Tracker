from __future__ import annotations

from hunter.models.dto import JobResult
from hunter.services.job_aggregation_service import JobAggregationService


class JobAggregator:
    """
    Backward-compatible shim around the new aggregation service.
    """

    def __init__(self) -> None:
        self.service = JobAggregationService()

    def search(self, query: str, location: str = "") -> list[JobResult]:
        return self.service.aggregate(query=query, location=location).jobs
