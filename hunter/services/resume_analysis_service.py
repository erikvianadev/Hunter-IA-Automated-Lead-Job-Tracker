from __future__ import annotations

from hunter.models.models import Resume, ResumeAnalysis

from .resume_parser_service import ResumeParserService
from .resume_security_service import ResumeSecurityService, ResumeTrustError
from .resume_scoring_service import ResumeScoringService


class ResumeAnalysisError(Exception):
    pass


class ResumeAnalysisService:
    def __init__(
        self,
        *,
        parser_service: ResumeParserService | None = None,
        scoring_service: ResumeScoringService | None = None,
        security_service: ResumeSecurityService | None = None,
    ) -> None:
        self.parser_service = parser_service or ResumeParserService()
        self.scoring_service = scoring_service or ResumeScoringService()
        self.security_service = security_service or ResumeSecurityService()

    def analyze(self, *, resume: Resume) -> ResumeAnalysis:
        try:
            decision = self.security_service.assert_trusted(
                resume=resume,
                action="Resume analysis is blocked",
            )
        except ResumeTrustError as exc:
            raise ResumeAnalysisError(exc.decision.message) from exc

        text = (resume.extracted_text or "").strip()
        if len(text) < 40 or len(text.split()) < 8:
            raise ResumeAnalysisError(decision.message)

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
            strengths.append("Traz um resumo profissional que contextualiza voce logo no inicio.")
        if parsed_resume.get("experience"):
            strengths.append("Apresenta experiencia profissional de forma facil de ler.")
        if parsed_resume.get("skills"):
            strengths.append("Destaca habilidades concretas que ajudam no posicionamento para vagas.")
        if parsed_resume.get("projects"):
            strengths.append("Inclui projetos que ajudam a demonstrar capacidade de execucao.")
        if parsed_resume.get("links"):
            strengths.append("Oferece links que ajudam a validar portfolio, GitHub ou perfil profissional.")
        if scores["clarity_score"] >= 70:
            strengths.append("O conteudo esta objetivo o bastante para uma leitura rapida.")
        return strengths[:5]

    def _build_weaknesses(
        self,
        *,
        parsed_resume: dict[str, object],
        scores: dict[str, object],
    ) -> list[str]:
        weaknesses: list[str] = []
        if not parsed_resume.get("summary"):
            weaknesses.append("Falta um resumo claro ou uma secao inicial de perfil.")
        if not parsed_resume.get("skills"):
            weaknesses.append("As habilidades ainda nao aparecem agrupadas em uma secao dedicada.")
        if not parsed_resume.get("projects"):
            weaknesses.append("Projetos com evidencia de execucao ainda estao ausentes ou muito fracos.")
        if not parsed_resume.get("links"):
            weaknesses.append("Nao encontramos links de portfolio, GitHub, LinkedIn ou provas complementares.")
        if scores["structure_score"] < 60:
            weaknesses.append("A estrutura de secoes ainda esta fraca e dificulta a leitura rapida.")
        return weaknesses[:5]

    def _build_recommendations(
        self,
        *,
        parsed_resume: dict[str, object],
        scores: dict[str, object],
    ) -> list[str]:
        recommendations: list[str] = []
        if not parsed_resume.get("summary"):
            recommendations.append("Adicione um resumo de 2 a 3 frases alinhado ao cargo que voce quer conquistar.")
        if not parsed_resume.get("skills"):
            recommendations.append("Crie uma secao de habilidades com ferramentas, linguagens e frameworks relevantes.")
        if not parsed_resume.get("projects"):
            recommendations.append("Inclua de 1 a 3 projetos com impacto, stack usada e escopo de entrega.")
        if not parsed_resume.get("links"):
            recommendations.append("Inclua links para GitHub, LinkedIn ou portfolio.")
        if scores["clarity_score"] < 70:
            recommendations.append("Deixe a redacao mais enxuta e prefira bullets curtos com resultados mensuraveis.")
        return recommendations[:5]
