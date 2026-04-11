from __future__ import annotations

from django.db.models import Avg, Max

from hunter.choices import JobApplicationStatus
from hunter.models.models import JobApplication, JobMatch, Resume, SavedJob


class DashboardService:
    TOP_MATCHES_LIMIT = 5
    RECOMMENDED_JOBS_LIMIT = 5
    MIN_RECOMMENDED_MATCH_SCORE = 40

    def build(self, *, owner) -> dict[str, object]:
        resume_queryset = (
            Resume.objects
            .filter(owner=owner)
            .select_related('analysis', 'seniority_assessment')
        )
        active_resume = resume_queryset.filter(is_active=True).order_by('-created_at').first()
        analysis = (
            active_resume.analysis
            if active_resume and hasattr(active_resume, 'analysis')
            else None
        )
        seniority_assessment = (
            active_resume.seniority_assessment
            if active_resume and hasattr(active_resume, 'seniority_assessment')
            else None
        )
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
                "total_saved_jobs": SavedJob.objects.filter(owner=owner).count(),
                "total_applications": JobApplication.objects.filter(owner=owner).count(),
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
            "analysis": analysis,
            "seniority_assessment": seniority_assessment,
            "top_matches": list(match_queryset[: self.TOP_MATCHES_LIMIT]),
            "recommended_jobs": self._build_recommended_jobs(
                owner=owner,
                match_queryset=match_queryset,
            ),
            "priority_actions": self._build_priority_actions(
                active_resume=active_resume,
                analysis=analysis,
                seniority_assessment=seniority_assessment,
                match_queryset=match_queryset,
            ),
            "profile_insights": self._build_profile_insights(
                analysis=analysis,
                seniority_assessment=seniority_assessment,
            ),
        }

    def _normalize_average(self, value):
        if value is None:
            return None
        return round(float(value), 2)

    def _build_recommended_jobs(self, *, owner, match_queryset):
        applied_job_ids = set(
            JobApplication.objects
            .filter(owner=owner)
            .exclude(status=JobApplicationStatus.SAVED)
            .values_list('job_id', flat=True)
        )
        recommendations = []
        for match in match_queryset:
            if match.job_id in applied_job_ids:
                continue
            if match.match_score < self.MIN_RECOMMENDED_MATCH_SCORE:
                continue
            recommendations.append(
                {
                    "match_id": match.id,
                    "job_id": match.job_id,
                    "title": match.job.title,
                    "company_name": match.job.company_name,
                    "location": match.job.location,
                    "url": match.job.url,
                    "match_score": match.match_score,
                    "recommendation": match.recommendation,
                }
            )
            if len(recommendations) >= self.RECOMMENDED_JOBS_LIMIT:
                break
        return recommendations

    def _build_priority_actions(
        self,
        *,
        active_resume,
        analysis,
        seniority_assessment,
        match_queryset,
    ):
        if active_resume is None:
            return [
                {
                    "action_type": "resume_upload",
                    "title": "Upload your active resume",
                    "detail": "A current resume unlocks analysis, matching, and dashboard guidance.",
                    "priority": 1,
                }
            ]

        actions: list[dict[str, object]] = []
        if analysis is None:
            actions.append(
                {
                    "action_type": "resume_analysis",
                    "title": "Run resume analysis",
                    "detail": "Generate score-based feedback before prioritizing opportunities.",
                    "priority": 1,
                }
            )
        else:
            for recommendation in analysis.recommendations[:2]:
                actions.append(
                    {
                        "action_type": "resume_improvement",
                        "title": "Improve resume quality",
                        "detail": recommendation,
                        "priority": 2,
                    }
                )
            parsed_resume = analysis.raw_summary.get("parsed_resume", {})
            if not parsed_resume.get("projects"):
                actions.append(
                    {
                        "action_type": "project_signal",
                        "title": "Add project evidence",
                        "detail": "Projects are missing from the parsed resume and can improve credibility.",
                        "priority": 1,
                    }
                )
            if not parsed_resume.get("links"):
                actions.append(
                    {
                        "action_type": "link_signal",
                        "title": "Add portfolio or profile links",
                        "detail": "Links are missing from the parsed resume and can strengthen recruiter trust.",
                        "priority": 2,
                    }
                )
        if seniority_assessment is None:
            actions.append(
                {
                    "action_type": "seniority_assessment",
                    "title": "Assess your target track",
                    "detail": "Run seniority assessment to focus applications on the right level.",
                    "priority": 2,
                }
            )
        else:
            actions.append(
                {
                    "action_type": "target_roles",
                    "title": "Prioritize the right role level",
                    "detail": f"Focus on {seniority_assessment.recommended_track} opportunities first.",
                    "priority": 3,
                }
            )

        top_match = match_queryset.first()
        if top_match is not None and top_match.match_score < 60:
            actions.append(
                {
                    "action_type": "match_gap",
                    "title": "Close the top matching gaps",
                    "detail": "Current top matches are moderate or low. Address the key missing signals before applying broadly.",
                    "priority": 1,
                }
            )

        actions.sort(key=lambda item: (item["priority"], item["title"]))
        return actions[:5]

    def _build_profile_insights(self, *, analysis, seniority_assessment):
        return {
            "recommended_track": (
                seniority_assessment.recommended_track
                if seniority_assessment is not None
                else None
            ),
            "competitiveness_level": self._derive_competitiveness_level(analysis=analysis),
            "top_gap_area": self._derive_top_gap_area(analysis=analysis),
        }

    def _derive_competitiveness_level(self, *, analysis):
        if analysis is None:
            return None
        if analysis.overall_score >= 75:
            return "high"
        if analysis.overall_score >= 50:
            return "medium"
        return "low"

    def _derive_top_gap_area(self, *, analysis):
        if analysis is None:
            return None
        score_map = {
            "structure": analysis.structure_score,
            "clarity": analysis.clarity_score,
            "market_fit": analysis.market_fit_score,
            "projects": analysis.project_score,
        }
        return min(score_map, key=score_map.get)
