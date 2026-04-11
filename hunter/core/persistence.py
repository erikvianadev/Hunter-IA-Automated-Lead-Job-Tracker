from __future__ import annotations

from hunter.models.dto import JobResult
from hunter.services.job_persistence_service import JobPersistenceService


class JobPersistence:
    """
    Backward-compatible shim around the new persistence service.
    """

    def __init__(self) -> None:
        self.service = JobPersistenceService()

    def save_jobs(self, owner, jobs: list[JobResult]):
        return self.service.save_jobs(owner=owner, jobs=jobs).jobs
