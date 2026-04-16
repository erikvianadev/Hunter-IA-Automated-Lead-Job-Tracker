from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

from django.db import transaction

from hunter.models.dto import JobResult
from hunter.models.models import Job

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PersistenceResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)

    @property
    def saved(self) -> int:
        return self.created + self.updated


class JobPersistenceService:
    def __init__(self) -> None:
        self.field_max_lengths = {
            "title": Job._meta.get_field("title").max_length,
            "company_name": Job._meta.get_field("company_name").max_length,
            "location": Job._meta.get_field("location").max_length,
            "url": Job._meta.get_field("url").max_length,
        }

    def save_jobs(self, *, owner, jobs: list[JobResult]) -> PersistenceResult:
        persisted_jobs: list[Job] = []
        created = 0
        updated = 0
        unchanged = 0
        skipped = 0
        errors: list[dict[str, str]] = []

        for job in jobs:
            try:
                with transaction.atomic():
                    obj, was_created, changed = self._save_one_job(owner=owner, job=job)
            except ValueError as exc:
                skipped += 1
                errors.append({"reason": str(exc)})
                logger.warning(
                    "persistence_job_skipped owner_id=%s reason=%s",
                    getattr(owner, "id", None),
                    exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                skipped += 1
                errors.append({"reason": "unexpected_persistence_error"})
                logger.exception(
                    "persistence_job_failed owner_id=%s error=%s",
                    getattr(owner, "id", None),
                    exc,
                )
                continue

            persisted_jobs.append(obj)
            if was_created:
                created += 1
            elif changed:
                updated += 1
            else:
                unchanged += 1

        logger.info(
            "persistence_completed owner_id=%s total=%d created=%d updated=%d unchanged=%d skipped=%d",
            getattr(owner, "id", None),
            len(jobs),
            created,
            updated,
            unchanged,
            skipped,
        )
        return PersistenceResult(
            created=created,
            updated=updated,
            unchanged=unchanged,
            skipped=skipped,
            errors=errors,
            jobs=persisted_jobs,
        )

    def _save_one_job(self, *, owner, job: JobResult) -> tuple[Job, bool, bool]:
        if not isinstance(job, JobResult):
            raise ValueError("invalid_job_payload")

        normalized_url = self._normalize_url_for_storage(job.canonical_url())
        defaults = {
            "title": self._normalize_text_for_storage(job.title, "title"),
            "company_name": self._normalize_text_for_storage(job.company, "company_name"),
            "location": self._normalize_text_for_storage(job.location, "location"),
            "description": self._normalize_description_for_storage(job.description),
        }
        self._validate_defaults(defaults, normalized_url)

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
                    title=defaults["title"],
                    company_name=defaults["company_name"],
                    location=defaults["location"],
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
        return obj, was_created, changed

    def _normalize_text_for_storage(self, value: str, field_name: str) -> str:
        normalized = str(value or "").strip()
        max_length = self.field_max_lengths.get(field_name)
        if not max_length or len(normalized) <= max_length:
            return normalized

        trimmed = normalized[:max_length].rstrip()
        logger.warning(
            "persistence_text_trimmed field=%s original_length=%d stored_length=%d",
            field_name,
            len(normalized),
            len(trimmed),
        )
        return trimmed

    def _normalize_description_for_storage(self, value: str) -> str:
        return str(value or "").strip()

    def _normalize_url_for_storage(self, value: str) -> str:
        normalized = (value or "").strip()
        max_length = self.field_max_lengths["url"]
        if not normalized or len(normalized) <= max_length:
            return normalized

        parts = urlsplit(normalized)
        without_query = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, "", "")
        )
        if without_query and len(without_query) <= max_length:
            logger.warning(
                "persistence_url_shortened original_length=%d stored_length=%d",
                len(normalized),
                len(without_query),
            )
            return without_query

        logger.warning(
            "persistence_url_dropped original_length=%d max_length=%d",
            len(normalized),
            max_length,
        )
        return ""

    def _validate_defaults(self, defaults: dict[str, str], normalized_url: str) -> None:
        if not defaults["title"]:
            raise ValueError("missing_title")
        if not defaults["company_name"]:
            raise ValueError("missing_company")
        if not defaults["location"]:
            raise ValueError("missing_location")
        if not normalized_url:
            raise ValueError("missing_actionable_link")
