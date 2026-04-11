from __future__ import annotations

import re

from hunter.models.models import Job, JobMatch, Resume

from .resume_analysis_service import ResumeAnalysisService
from .seniority_assessment_service import SeniorityAssessmentService


class JobMatchingError(Exception):
    pass


class JobMatchingService:
    def __init__(
        self,
        *,
        analysis_service: ResumeAnalysisService | None = None,
        seniority_service: SeniorityAssessmentService | None = None,
    ) -> None:
        self.analysis_service = analysis_service or ResumeAnalysisService()
        self.seniority_service = seniority_service or SeniorityAssessmentService(
            analysis_service=self.analysis_service
        )

    def match(self, *, owner, resume: Resume, job: Job) -> JobMatch:
        if resume.owner_id != owner.id or job.owner_id != owner.id:
            raise JobMatchingError("Resume and job must belong to the authenticated user.")

        analysis = resume.analysis if hasattr(resume, 'analysis') else self.analysis_service.analyze(resume=resume)
        seniority = (
            resume.seniority_assessment
            if hasattr(resume, 'seniority_assessment')
            else self.seniority_service.assess(resume=resume)
        )
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
            strengths.append(f"Overlapping skills: {', '.join(overlap[:5])}.")
        if analysis.project_score >= 60:
            strengths.append("Project evidence strengthens practical fit.")
        if analysis.structure_score >= 70:
            strengths.append("Resume structure is clear enough for screening.")

        gaps: list[str] = []
        if missing:
            gaps.append(f"Potential missing signals: {', '.join(missing)}.")
        if analysis.project_score < 50:
            gaps.append("Project evidence is limited for this role.")
        if seniority_fit < 10:
            gaps.append("Resume track may not align closely with the job seniority signals.")

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
            return "Strong match. Prioritize this application."
        if match_score >= 60:
            return "Promising match. Apply after tightening resume alignment."
        if match_score >= 40:
            return "Moderate match. Address the main skill gaps before applying."
        return "Low match. Focus on skill-building or choose a closer role."
