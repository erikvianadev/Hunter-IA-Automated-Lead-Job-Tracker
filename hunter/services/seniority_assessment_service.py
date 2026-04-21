from __future__ import annotations

from hunter.models.models import Resume, SeniorityAssessment

from .resume_analysis_service import ResumeAnalysisService
from .resume_security_service import ResumeSecurityService, ResumeTrustError


class SeniorityAssessmentError(Exception):
    pass


class SeniorityAssessmentService:
    def __init__(
        self,
        *,
        analysis_service: ResumeAnalysisService | None = None,
        security_service: ResumeSecurityService | None = None,
    ) -> None:
        self.analysis_service = analysis_service or ResumeAnalysisService()
        self.security_service = security_service or ResumeSecurityService()

    def assess(self, *, resume: Resume) -> SeniorityAssessment:
        try:
            self.security_service.assert_trusted(
                resume=resume,
                action="Resume seniority assessment is blocked",
            )
        except ResumeTrustError as exc:
            raise SeniorityAssessmentError(exc.decision.message) from exc

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

        # Internship base reduced from 35 to 30 to prevent it from winning by default
        # when experience_entries=0 (parser failure on PT-BR PDFs with unrecognised sections).
        # At base 35, a profile with 0 experience but skills>=3 and projects beat all other tracks.
        # At base 30, junior wins once skills>=2, which is correct for someone with any skill breadth.
        internship_score = min(
            100,
            30 + (15 if projects_count else 0) + (10 if skills_count >= 3 else 0) + (10 if summary_present else 0),
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
            5 + min(experience_entries, 6) * 15 + (15 if projects_count >= 2 else 0) + (15 if skills_count >= 8 else 0) + (10 if structure_score >= 80 else 0) + (10 if overall_score >= 80 else 0),
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
        _track_priority = {"senior": 4, "mid": 3, "freelance": 2, "junior": 1, "internship": 0}
        recommended_track = max(
            score_map,
            key=lambda track: (score_map[track], _track_priority.get(track, 0)),
        )
        low_evidence = experience_entries == 0 and overall_score >= 70
        reasoning = {
            "experience_entries": experience_entries,
            "projects_count": projects_count,
            "skills_count": skills_count,
            "links_count": links_count,
            "summary_present": summary_present,
            "structure_score": structure_score,
            "overall_score": overall_score,
            "low_evidence_warning": low_evidence,
            "explanation": self._build_explanation(
                recommended_track=recommended_track,
                experience_entries=experience_entries,
                projects_count=projects_count,
                skills_count=skills_count,
                low_evidence=low_evidence,
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
        low_evidence: bool = False,
    ) -> str:
        base = (
            f"O nível mais aderente no momento é {recommended_track}, com base em "
            f"{experience_entries} experiências identificadas, {projects_count} sinais de projetos "
            f"e {skills_count} habilidades distintas."
        )
        if low_evidence:
            base += (
                " A leitura de experiências profissionais foi limitada — "
                "se o currículo tiver seções de experiência, revise a formatação "
                "para melhorar a precisão da análise."
            )
        return base
