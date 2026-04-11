from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.db import transaction

from hunter.models.dto import JobResult
from hunter.models.models import Job

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PersistenceResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    jobs: list[Job] = field(default_factory=list)

    @property
    def saved(self) -> int:
        return self.created + self.updated


class JobPersistenceService:
    @transaction.atomic
    def save_jobs(self, *, owner, jobs: list[JobResult]) -> PersistenceResult:
        persisted_jobs: list[Job] = []
        created = 0
        updated = 0
        unchanged = 0

        for job in jobs:
            normalized_url = job.canonical_url()
            defaults = {
                "title": job.title,
                "company_name": job.company,
                "location": job.location,
                "description": job.description,
            }

            if normalized_url:
                existing_jobs = list(
                    Job.objects.select_for_update()
                    .filter(owner=owner, url=normalized_url)
                    .order_by("id")
                )
                obj = existing_jobs[0] if existing_jobs else None
                was_created = obj is None
                if obj is None:
                    obj = Job.objects.create(owner=owner, url=normalized_url, **defaults)
                elif len(existing_jobs) > 1:
                    logger.warning(
                        "persistence_duplicate_rows owner_id=%s url=%s duplicate_count=%d",
                        getattr(owner, "id", None),
                        normalized_url,
                        len(existing_jobs),
                    )
            else:
                obj = (
                    Job.objects.select_for_update()
                    .filter(
                        owner=owner,
                        title=job.title,
                        company_name=job.company,
                        location=job.location,
                    )
                    .order_by("id")
                    .first()
                )
                was_created = obj is None
                if obj is None:
                    obj = Job.objects.create(owner=owner, url="", **defaults)

            changed = was_created
            if not was_created:
                for field_name, candidate_value in defaults.items():
                    if candidate_value and getattr(obj, field_name) != candidate_value:
                        setattr(obj, field_name, candidate_value)
                        changed = True
                if normalized_url and obj.url != normalized_url:
                    obj.url = normalized_url
                    changed = True
                if changed:
                    obj.save(
                        update_fields=[
                            "title",
                            "company_name",
                            "location",
                            "description",
                            "url",
                            "updated_at",
                        ]
                    )

            persisted_jobs.append(obj)
            if was_created:
                created += 1
            elif changed:
                updated += 1
            else:
                unchanged += 1

        logger.info(
            "persistence_completed owner_id=%s total=%d created=%d updated=%d unchanged=%d",
            getattr(owner, "id", None),
            len(jobs),
            created,
            updated,
            unchanged,
        )
        return PersistenceResult(
            created=created,
            updated=updated,
            unchanged=unchanged,
            jobs=persisted_jobs,
        )
