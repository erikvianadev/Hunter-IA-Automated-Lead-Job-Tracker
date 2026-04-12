from __future__ import annotations

from django.db import transaction

from hunter.models.models import Resume

from .resume_comparison_service import ResumeComparisonService


class ResumeProfileService:
    def __init__(self, *, comparison_service: ResumeComparisonService | None = None) -> None:
        self.comparison_service = comparison_service or ResumeComparisonService()

    @transaction.atomic
    def activate(self, *, owner, resume: Resume) -> Resume:
        if resume.owner_id != owner.id:
            raise Resume.DoesNotExist

        Resume.objects.filter(owner=owner, is_active=True).exclude(id=resume.id).update(
            is_active=False
        )
        if not resume.is_active:
            resume.is_active = True
            resume.save(update_fields=["is_active", "updated_at"])
        return resume

    def compare(self, *, owner, resume_ids: list[int] | None = None) -> dict[str, object]:
        return self.comparison_service.build(
            owner=owner,
            resume_ids=resume_ids,
        )
