from __future__ import annotations

from django.db import transaction

from hunter.models.models import Resume


class ResumeProfileService:
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
        queryset = (
            Resume.objects
            .filter(owner=owner)
            .select_related('analysis', 'seniority_assessment')
            .order_by('-is_active', '-created_at')
        )
        if resume_ids:
            queryset = queryset.filter(id__in=resume_ids)

        resumes = list(queryset)
        compared_resumes = [self._serialize_resume(resume) for resume in resumes]
        best_resume = self._pick_best_resume(compared_resumes)

        return {
            "compared_resumes": compared_resumes,
            "best_resume_by_score": best_resume,
        }

    def _serialize_resume(self, resume: Resume) -> dict[str, object]:
        analysis = resume.analysis if hasattr(resume, 'analysis') else None
        seniority = resume.seniority_assessment if hasattr(resume, 'seniority_assessment') else None
        return {
            "id": resume.id,
            "label": resume.label,
            "target_role": resume.target_role,
            "is_active": resume.is_active,
            "parse_status": resume.parse_status,
            "overall_score": analysis.overall_score if analysis is not None else None,
            "structure_score": analysis.structure_score if analysis is not None else None,
            "project_score": analysis.project_score if analysis is not None else None,
            "recommended_track": (
                seniority.recommended_track
                if seniority is not None
                else None
            ),
            "created_at": resume.created_at,
            "updated_at": resume.updated_at,
        }

    def _pick_best_resume(self, compared_resumes: list[dict[str, object]]):
        scored_resumes = [
            resume
            for resume in compared_resumes
            if resume["overall_score"] is not None
        ]
        if not scored_resumes:
            return None
        return max(
            scored_resumes,
            key=lambda item: (
                item["overall_score"],
                item["project_score"] or 0,
                int(bool(item["is_active"])),
            ),
        )
