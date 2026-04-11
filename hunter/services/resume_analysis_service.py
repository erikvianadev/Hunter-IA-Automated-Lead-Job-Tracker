from __future__ import annotations

from hunter.models.models import Resume, ResumeAnalysis

from .resume_parser_service import ResumeParserService
from .resume_scoring_service import ResumeScoringService


class ResumeAnalysisError(Exception):
    pass


class ResumeAnalysisService:
    def __init__(
        self,
        *,
        parser_service: ResumeParserService | None = None,
        scoring_service: ResumeScoringService | None = None,
    ) -> None:
        self.parser_service = parser_service or ResumeParserService()
        self.scoring_service = scoring_service or ResumeScoringService()

    def analyze(self, *, resume: Resume) -> ResumeAnalysis:
        text = (resume.extracted_text or "").strip()
        if len(text) < 40 or len(text.split()) < 8:
            raise ResumeAnalysisError(
                "Resume text is missing or insufficient for analysis. Upload a clearer PDF or DOCX file first."
            )

        parsed_resume = self.parser_service.parse(text=text)
        scores = self.scoring_service.score(parsed_resume=parsed_resume, text=text)
        strengths = self._build_strengths(parsed_resume=parsed_resume, scores=scores)
        weaknesses = self._build_weaknesses(parsed_resume=parsed_resume, scores=scores)
        recommendations = self._build_recommendations(
            parsed_resume=parsed_resume,
            scores=scores,
        )

        analysis, _ = ResumeAnalysis.objects.update_or_create(
            resume=resume,
            defaults={
                "overall_score": scores["overall_score"],
                "structure_score": scores["structure_score"],
                "clarity_score": scores["clarity_score"],
                "market_fit_score": scores["market_fit_score"],
                "project_score": scores["project_score"],
                "strengths": strengths,
                "weaknesses": weaknesses,
                "recommendations": recommendations,
                "raw_summary": {
                    "parsed_resume": parsed_resume,
                    "score_factors": scores["score_factors"],
                },
            },
        )
        return analysis

    def _build_strengths(
        self,
        *,
        parsed_resume: dict[str, object],
        scores: dict[str, object],
    ) -> list[str]:
        strengths: list[str] = []
        if parsed_resume.get("summary"):
            strengths.append("Includes a professional summary that gives quick context.")
        if parsed_resume.get("experience"):
            strengths.append("Lists professional experience, which improves recruiter readability.")
        if parsed_resume.get("skills"):
            strengths.append("Highlights concrete skills that support market positioning.")
        if parsed_resume.get("projects"):
            strengths.append("Includes project evidence that helps demonstrate execution.")
        if parsed_resume.get("links"):
            strengths.append("Provides links that can help validate portfolio or profile details.")
        if scores["clarity_score"] >= 70:
            strengths.append("Resume content is concise enough to be scanned quickly.")
        return strengths[:5]

    def _build_weaknesses(
        self,
        *,
        parsed_resume: dict[str, object],
        scores: dict[str, object],
    ) -> list[str]:
        weaknesses: list[str] = []
        if not parsed_resume.get("summary"):
            weaknesses.append("Missing a clear summary or profile section.")
        if not parsed_resume.get("skills"):
            weaknesses.append("Skills are not clearly grouped into a dedicated section.")
        if not parsed_resume.get("projects"):
            weaknesses.append("Project evidence is limited or missing.")
        if not parsed_resume.get("links"):
            weaknesses.append("No portfolio, GitHub, LinkedIn, or other supporting links were detected.")
        if scores["structure_score"] < 60:
            weaknesses.append("Section structure is thin, which can make the resume harder to scan.")
        return weaknesses[:5]

    def _build_recommendations(
        self,
        *,
        parsed_resume: dict[str, object],
        scores: dict[str, object],
    ) -> list[str]:
        recommendations: list[str] = []
        if not parsed_resume.get("summary"):
            recommendations.append("Add a 2-3 sentence summary tailored to your target role.")
        if not parsed_resume.get("skills"):
            recommendations.append("Create a dedicated skills section with tools, languages, and frameworks.")
        if not parsed_resume.get("projects"):
            recommendations.append("Add 1-3 projects with outcomes, stack, and scope.")
        if not parsed_resume.get("links"):
            recommendations.append("Include links to GitHub, LinkedIn, or a portfolio.")
        if scores["clarity_score"] < 70:
            recommendations.append("Tighten wording and favor short bullet points with measurable outcomes.")
        return recommendations[:5]
