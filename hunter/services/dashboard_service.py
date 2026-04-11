from __future__ import annotations

from django.db.models import Avg, Max

from hunter.models.models import JobMatch, Resume


class DashboardService:
    TOP_MATCHES_LIMIT = 5

    def build(self, *, owner) -> dict[str, object]:
        resume_queryset = (
            Resume.objects
            .filter(owner=owner)
            .select_related('analysis', 'seniority_assessment')
        )
        active_resume = resume_queryset.filter(is_active=True).order_by('-created_at').first()
        match_queryset = (
            JobMatch.objects
            .filter(owner=owner)
            .select_related('job', 'resume')
            .order_by('-match_score', '-created_at')
        )
        match_summary = (
            match_queryset
            .aggregate(
                average_match_score=Avg('match_score'),
                top_match_score=Max('match_score'),
            )
        )

        return {
            "summary": {
                "total_resumes": resume_queryset.count(),
                "total_matches": match_queryset.count(),
                "average_match_score": self._normalize_average(
                    match_summary["average_match_score"]
                ),
                "top_match_score": match_summary["top_match_score"],
                "analysis_ready": bool(active_resume and hasattr(active_resume, 'analysis')),
                "seniority_ready": bool(
                    active_resume and hasattr(active_resume, 'seniority_assessment')
                ),
            },
            "active_resume": active_resume,
            "analysis": (
                active_resume.analysis
                if active_resume and hasattr(active_resume, 'analysis')
                else None
            ),
            "seniority_assessment": (
                active_resume.seniority_assessment
                if active_resume and hasattr(active_resume, 'seniority_assessment')
                else None
            ),
            "top_matches": list(match_queryset[: self.TOP_MATCHES_LIMIT]),
        }

    def _normalize_average(self, value):
        if value is None:
            return None
        return round(float(value), 2)
