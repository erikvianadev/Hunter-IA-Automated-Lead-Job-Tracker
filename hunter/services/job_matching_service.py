from __future__ import annotations

import re

from hunter.models.models import Job, JobMatch, Resume

from .resume_analysis_service import ResumeAnalysisService
from .resume_security_service import ResumeSecurityService, ResumeTrustError
from .seniority_assessment_service import SeniorityAssessmentError, SeniorityAssessmentService


class JobMatchingError(Exception):
    pass


class JobMatchingService:
    def __init__(
        self,
        *,
        analysis_service: ResumeAnalysisService | None = None,
        seniority_service: SeniorityAssessmentService | None = None,
        security_service: ResumeSecurityService | None = None,
    ) -> None:
        self.analysis_service = analysis_service or ResumeAnalysisService()
        self.seniority_service = seniority_service or SeniorityAssessmentService(
            analysis_service=self.analysis_service
        )
        self.security_service = security_service or ResumeSecurityService()

    def match(self, *, owner, resume: Resume, job: Job) -> JobMatch:
        if resume.owner_id != owner.id or job.owner_id != owner.id:
            raise JobMatchingError("O curriculo e a vaga precisam pertencer a sua conta.")
        try:
            self.security_service.assert_trusted(
                resume=resume,
                action="A atualizacao de aderencia foi bloqueada",
            )
        except ResumeTrustError as exc:
            raise JobMatchingError(exc.decision.message) from exc

        analysis = resume.analysis if hasattr(resume, 'analysis') else self.analysis_service.analyze(resume=resume)
        try:
            seniority = (
                resume.seniority_assessment
                if hasattr(resume, 'seniority_assessment')
                else self.seniority_service.assess(resume=resume)
            )
        except SeniorityAssessmentError as exc:
            raise JobMatchingError(str(exc)) from exc
        parsed_resume = analysis.raw_summary.get("parsed_resume", {})
        resume_skills = {skill.lower() for skill in parsed_resume.get("skills", [])}
        resume_projects = parsed_resume.get("projects", [])
        job_tokens = self._extract_job_keywords(job)
        overlap = sorted(skill for skill in resume_skills if skill in job_tokens)
        missing = sorted(token for token in job_tokens if token not in resume_skills)[:5]
        seniority_fit = self._score_seniority_fit(job=job, seniority=seniority)

        match_score = min(
            100,
            30
            + min(len(overlap), 8) * 6
            + round(analysis.overall_score * 0.2)
            + (10 if resume_projects else 0)
            + seniority_fit,
            )

        strengths: list[str] = []
        if overlap:
            strengths.append(f"Habilidades em comum: {', '.join(overlap[:5])}.")
        if analysis.project_score >= 60:
            strengths.append("Os projetos ajudam a sustentar a aderencia pratica para essa vaga.")
        if analysis.structure_score >= 70:
            strengths.append("A estrutura do curriculo esta clara o bastante para uma triagem inicial.")

        gaps: list[str] = []
        if missing:
            gaps.append(f"Sinais que ainda podem estar faltando: {', '.join(missing)}.")
        if analysis.project_score < 50:
            gaps.append("A evidencia de projetos ainda esta fraca para este tipo de vaga.")
        if seniority_fit < 10:
            gaps.append("Seu nivel atual pode nao estar tao alinhado aos sinais de senioridade dessa vaga.")

        recommendation = self._build_recommendation(match_score=match_score)
        reasoning = {
            "overlapping_skills": overlap,
            "missing_keywords": missing,
            "resume_overall_score": analysis.overall_score,
            "resume_project_score": analysis.project_score,
            "recommended_track": seniority.recommended_track,
            "seniority_fit_score": seniority_fit,
        }

        job_match, _ = JobMatch.objects.update_or_create(
            owner=owner,
            resume=resume,
            job=job,
            defaults={
                "match_score": match_score,
                "strengths": strengths,
                "gaps": gaps,
                "recommendation": recommendation,
                "reasoning": reasoning,
            },
        )
        return job_match

    def _extract_job_keywords(self, job: Job) -> set[str]:
        text = f"{job.title} {job.description}".lower()
        normalized = re.sub(r"[^a-z0-9+#./ ]+", " ", text)
        keywords = {token for token in normalized.split() if len(token) >= 3}
        interesting = {
            token
            for token in keywords
            if token
            in {
                "python",
                "sql",
                "django",
                "flask",
                "fastapi",
                "tableau",
                "powerbi",
                "pandas",
                "spark",
                "aws",
                "azure",
                "gcp",
                "react",
                "docker",
                "kubernetes",
                "api",
                "javascript",
                "typescript",
                "excel",
                "machine",
                "learning",
                "analytics",
            }
        }
        return interesting

    def _score_seniority_fit(self, *, job: Job, seniority) -> int:
        text = f"{job.title} {job.description}".lower()
        if any(keyword in text for keyword in ["intern", "internship", "trainee"]):
            return round(seniority.internship_score * 0.15)
        if any(keyword in text for keyword in ["junior", "entry", "associate"]):
            return round(seniority.junior_score * 0.15)
        if any(keyword in text for keyword in ["senior", "lead", "principal", "staff"]):
            return round(seniority.senior_score * 0.15)
        if any(keyword in text for keyword in ["freelance", "contract", "consultant"]):
            return round(seniority.freelance_score * 0.15)
        return round(seniority.mid_score * 0.15)

    def _build_recommendation(self, *, match_score: int) -> str:
        if match_score >= 80:
            return "Boa aderencia. Vale priorizar esta candidatura."
        if match_score >= 60:
            return "Aderencia promissora. Vale aplicar depois de alguns ajustes finos no curriculo."
        if match_score >= 40:
            return "Aderencia moderada. Feche as principais lacunas antes de aplicar."
        return "Aderencia baixa agora. Talvez valha fortalecer sinais-chave ou focar em uma vaga mais proxima."
