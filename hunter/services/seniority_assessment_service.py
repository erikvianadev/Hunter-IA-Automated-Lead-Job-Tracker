from __future__ import annotations

from hunter.models.models import Resume, SeniorityAssessment

from .resume_analysis_service import ResumeAnalysisService


class SeniorityAssessmentError(Exception):
    pass


class SeniorityAssessmentService:
    def __init__(self, *, analysis_service: ResumeAnalysisService | None = None) -> None:
        self.analysis_service = analysis_service or ResumeAnalysisService()

    def assess(self, *, resume: Resume) -> SeniorityAssessment:
        if not hasattr(resume, 'analysis'):
            analysis = self.analysis_service.analyze(resume=resume)
        else:
            analysis = resume.analysis

        parsed_resume = analysis.raw_summary.get("parsed_resume", {})
        score_factors = analysis.raw_summary.get("score_factors", {})
        experience_entries = int(score_factors.get("experience_entries", 0))
        projects_count = int(score_factors.get("projects_count", 0))
        skills_count = int(score_factors.get("skills_count", 0))
        links_count = int(score_factors.get("links_count", 0))
        structure_score = analysis.structure_score
        overall_score = analysis.overall_score
        summary_present = bool(parsed_resume.get("summary"))

        internship_score = min(
            100,
            35 + (15 if projects_count else 0) + (10 if skills_count >= 3 else 0) + (10 if summary_present else 0),
        )
        junior_score = min(
            100,
            25 + min(experience_entries, 2) * 15 + min(skills_count, 8) * 4 + (10 if projects_count else 0),
        )
        mid_score = min(
            100,
            10 + min(experience_entries, 4) * 18 + min(skills_count, 10) * 3 + (10 if projects_count >= 2 else 0) + (10 if overall_score >= 70 else 0),
        )
        senior_score = min(
            100,
            5 + min(experience_entries, 6) * 15 + (15 if projects_count >= 2 else 0) + (15 if skills_count >= 8 else 0) + (10 if structure_score >= 80 else 0),
        )
        freelance_score = min(
            100,
            15 + min(projects_count, 4) * 15 + (10 if links_count else 0) + (10 if summary_present else 0) + (10 if skills_count >= 5 else 0),
        )

        score_map = {
            "internship": internship_score,
            "junior": junior_score,
            "mid": mid_score,
            "senior": senior_score,
            "freelance": freelance_score,
        }
        recommended_track = max(score_map, key=score_map.get)
        reasoning = {
            "experience_entries": experience_entries,
            "projects_count": projects_count,
            "skills_count": skills_count,
            "links_count": links_count,
            "summary_present": summary_present,
            "structure_score": structure_score,
            "overall_score": overall_score,
            "explanation": self._build_explanation(
                recommended_track=recommended_track,
                experience_entries=experience_entries,
                projects_count=projects_count,
                skills_count=skills_count,
            ),
        }

        assessment, _ = SeniorityAssessment.objects.update_or_create(
            resume=resume,
            defaults={
                "internship_score": internship_score,
                "junior_score": junior_score,
                "mid_score": mid_score,
                "senior_score": senior_score,
                "freelance_score": freelance_score,
                "recommended_track": recommended_track,
                "reasoning": reasoning,
            },
        )
        return assessment

    def _build_explanation(
        self,
        *,
        recommended_track: str,
        experience_entries: int,
        projects_count: int,
        skills_count: int,
    ) -> str:
        return (
            f"Recommended track is {recommended_track} based on "
            f"{experience_entries} experience entries, {projects_count} project signals, "
            f"and {skills_count} distinct skills."
        )
