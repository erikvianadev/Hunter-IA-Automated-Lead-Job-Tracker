from __future__ import annotations

from django.utils import timezone

from hunter.choices import JobApplicationStatus
from hunter.models.models import Job, JobApplication, SavedJob


class JobWorkflowError(Exception):
    pass


class JobWorkflowService:
    APPLYING_STATUSES = {
        JobApplicationStatus.APPLIED,
        JobApplicationStatus.INTERVIEW,
        JobApplicationStatus.REJECTED,
        JobApplicationStatus.OFFER,
    }

    def save_job(self, *, owner, job: Job) -> tuple[SavedJob, bool]:
        self._validate_ownership(owner=owner, job=job)
        return SavedJob.objects.get_or_create(owner=owner, job=job)

    def unsave_job(self, *, owner, job: Job) -> bool:
        self._validate_ownership(owner=owner, job=job)
        deleted_count, _ = SavedJob.objects.filter(owner=owner, job=job).delete()
        return deleted_count > 0

    def apply_to_job(
        self,
        *,
        owner,
        job: Job,
        status: str = JobApplicationStatus.APPLIED,
        notes: str | None = None,
    ) -> tuple[JobApplication, bool]:
        self._validate_ownership(owner=owner, job=job)
        application, created = JobApplication.objects.get_or_create(
            owner=owner,
            job=job,
            defaults={
                'status': status,
                'notes': notes or '',
                'applied_at': self._next_applied_at(
                    current_applied_at=None,
                    next_status=status,
                ),
            },
        )
        if created:
            return application, True
        return self.update_application(
            application=application,
            status=status,
            notes=notes,
        ), False

    def update_application(
        self,
        *,
        application: JobApplication,
        status: str | None = None,
        notes: str | None = None,
    ) -> JobApplication:
        update_fields: list[str] = []

        if status is not None and application.status != status:
            application.status = status
            update_fields.append('status')

        if notes is not None and application.notes != notes:
            application.notes = notes
            update_fields.append('notes')

        next_applied_at = self._next_applied_at(
            current_applied_at=application.applied_at,
            next_status=application.status,
        )
        if application.applied_at != next_applied_at:
            application.applied_at = next_applied_at
            update_fields.append('applied_at')

        if update_fields:
            update_fields.append('updated_at')
            application.save(update_fields=update_fields)
        return application

    def _next_applied_at(self, *, current_applied_at, next_status: str):
        if current_applied_at is not None:
            return current_applied_at
        if next_status in self.APPLYING_STATUSES:
            return timezone.now()
        return None

    def _validate_ownership(self, *, owner, job: Job) -> None:
        if job.owner_id != owner.id:
            raise JobWorkflowError("Job must belong to the authenticated user.")
