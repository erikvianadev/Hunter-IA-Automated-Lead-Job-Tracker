from __future__ import annotations

from collections import OrderedDict

from django.db.models import Avg, Max

from hunter.models.models import JobMatch, Resume

from .resume_security_service import ResumeSecurityService

AREA_LABELS = {
    "structure": "estrutura",
    "clarity": "clareza",
    "market_fit": "aderencia ao mercado",
    "projects": "projetos",
}
TRACK_LABELS = {
    "internship": "estagio",
    "junior": "junior",
    "mid": "pleno",
    "senior": "senior",
    "freelance": "freelancer",
}


def get_area_label(value: str) -> str:
    return AREA_LABELS.get(value, value.replace("_", " "))


def get_track_label(value: str | None) -> str:
    return TRACK_LABELS.get(value or "", value or "seu nivel atual")


class ResumeReportService:
    def __init__(self, *, security_service: ResumeSecurityService | None = None) -> None:
        self.security_service = security_service or ResumeSecurityService()

    def build(self, *, resume: Resume) -> dict[str, object]:
        decision = self.security_service.evaluate(resume=resume)
        analysis = (
            resume.analysis
            if decision.trusted and hasattr(resume, 'analysis')
            else None
        )
        seniority = (
            resume.seniority_assessment
            if decision.trusted and hasattr(resume, 'seniority_assessment')
            else None
        )
        match_summary = self._build_match_summary(resume=resume)
        strengths = self._build_strengths(
            analysis=analysis,
            seniority=seniority,
            trust_decision=decision,
        )
        top_gaps = self._build_top_gaps(
            resume=resume,
            analysis=analysis,
            seniority=seniority,
            trust_decision=decision,
        )
        priority_actions = self._build_priority_actions(
            analysis=analysis,
            seniority=seniority,
            top_gaps=top_gaps,
            trust_decision=decision,
        )

        return {
            "resume_id": resume.id,
            "label": resume.label,
            "target_role": resume.target_role,
            "parse_status": resume.parse_status,
            "ingestion_status": decision.normalized_status,
            "ingestion_trusted": decision.trusted,
            "ingestion_diagnostics": decision.diagnostics,
            "is_active": resume.is_active,
            "category_scores": {
                "overall": analysis.overall_score if analysis is not None else None,
                "structure": analysis.structure_score if analysis is not None else None,
                "clarity": analysis.clarity_score if analysis is not None else None,
                "market_fit": analysis.market_fit_score if analysis is not None else None,
                "projects": analysis.project_score if analysis is not None else None,
            },
            "recommended_track": (
                seniority.recommended_track if seniority is not None else None
            ),
            "strengths": strengths,
            "top_gaps": top_gaps,
            "priority_actions": priority_actions,
            "recent_match_summary": match_summary,
            "executive_summary": self._build_executive_summary(
                resume=resume,
                analysis=analysis,
                seniority=seniority,
                match_summary=match_summary,
                trust_decision=decision,
            ),
            "profile_summary": self._build_profile_summary(
                resume=resume,
                analysis=analysis,
                seniority=seniority,
                trust_decision=decision,
            ),
        }

    def _build_match_summary(self, *, resume: Resume) -> dict[str, object]:
        queryset = JobMatch.objects.filter(
            owner=resume.owner,
            resume=resume,
        ).order_by('-match_score', '-created_at')
        aggregate = queryset.aggregate(
            average_match_score=Avg('match_score'),
            best_match_score=Max('match_score'),
        )
        top_match = queryset.first()
        average_match_score = aggregate["average_match_score"]
        return {
            "total_matches": queryset.count(),
            "average_match_score": (
                round(float(average_match_score), 2)
                if average_match_score is not None
                else None
            ),
            "best_match_score": aggregate["best_match_score"],
            "top_recommendation": top_match.recommendation if top_match is not None else None,
        }

    def _build_strengths(self, *, analysis, seniority, trust_decision) -> list[str]:
        strengths: list[str] = []
        if not trust_decision.trusted:
            return strengths
        if analysis is not None:
            structured_strengths = analysis.raw_summary.get("what_is_working", [])
            strengths.extend(item.get("statement", "") for item in structured_strengths[:3])
            if not strengths:
                strengths.extend(analysis.strengths[:3])
            if analysis.overall_score >= 75:
                strengths.append("A qualidade geral do curriculo ja esta competitiva para triagens iniciais.")
            if analysis.market_fit_score >= 70:
                strengths.append("Os sinais de aderencia ao mercado estao fortes o bastante para candidaturas mais direcionadas.")
        if seniority is not None:
            strengths.append(
                f"As evidencias atuais se alinham melhor a vagas de nivel {get_track_label(seniority.recommended_track)}."
            )
        return self._deduplicate(strengths)[:5]

    def _build_top_gaps(self, *, resume: Resume, analysis, seniority, trust_decision) -> list[str]:
        gaps: list[str] = []
        if not trust_decision.trusted:
            gaps.append(trust_decision.message)
            suggestion = trust_decision.diagnostics.get("suggestion")
            if isinstance(suggestion, str) and suggestion:
                gaps.append(suggestion)
            return self._deduplicate(gaps)[:5]
        if analysis is None:
            gaps.append("A analise do curriculo ainda nao foi gerada.")
        else:
            score_map = {
                "structure": analysis.structure_score,
                "clarity": analysis.clarity_score,
                "market_fit": analysis.market_fit_score,
                "projects": analysis.project_score,
            }
            weakest_area = min(score_map, key=score_map.get)
            gaps.append(f"A area com menor score hoje e {get_area_label(weakest_area)}.")
            structured_gaps = analysis.raw_summary.get("what_is_missing", [])
            gaps.extend(item.get("statement", "") for item in structured_gaps[:3])
            if not structured_gaps:
                gaps.extend(analysis.weaknesses[:3])

        if seniority is None:
            gaps.append("A leitura de senioridade ainda nao esta disponivel.")

        match_gaps = list(
            JobMatch.objects.filter(
                owner=resume.owner,
                resume=resume,
            )
            .order_by('-created_at')
            .values_list('gaps', flat=True)[:3]
        )
        for gap_list in match_gaps:
            gaps.extend(gap_list[:2])
        return self._deduplicate(gaps)[:5]

    def _build_priority_actions(self, *, analysis, seniority, top_gaps: list[str], trust_decision) -> list[str]:
        actions: list[str] = []
        if not trust_decision.trusted:
            actions.append("Envie um PDF ou DOCX mais limpo antes de rodar analise, senioridade ou aderencia.")
            suggestion = trust_decision.diagnostics.get("suggestion")
            if isinstance(suggestion, str) and suggestion:
                actions.append(suggestion)
            return self._deduplicate(actions)[:5]
        if analysis is None:
            actions.append("Gere a analise do curriculo para liberar recomendacoes com score.")
        else:
            structured_actions = analysis.raw_summary.get("priority_actions", [])
            if structured_actions:
                actions.extend(
                    f"{item.get('priority_label', 'Prioridade')}: {item.get('title', '')}. {item.get('impact', '')}".strip()
                    for item in structured_actions[:3]
                )
            else:
                actions.extend(analysis.recommendations[:3])
            if analysis.market_fit_score < 60:
                actions.append("Ajuste o curriculo para um cargo-alvo mais claro e com melhor cobertura de palavras-chave.")
            if analysis.project_score < 60:
                actions.append("Reforce os projetos com stack, escopo e impacto mensuravel.")
        if seniority is None:
            actions.append("Gere a leitura de senioridade para focar candidaturas no nivel certo.")
        else:
            actions.append(
                f"Priorize vagas de nivel {get_track_label(seniority.recommended_track)} enquanto fortalece os sinais mais fracos."
            )
        if not actions and top_gaps:
            actions.append(f"Comece por aqui: {top_gaps[0]}")
        return self._deduplicate(actions)[:5]

    def _build_executive_summary(self, *, resume: Resume, analysis, seniority, match_summary, trust_decision) -> str:
        if not trust_decision.trusted:
            return (
                f"{resume.label or resume.original_filename} esta bloqueado para as proximas etapas porque "
                f"{trust_decision.message.lower()}"
            )
        score = analysis.overall_score if analysis is not None else None
        score_text = (
            f"com score geral de {score}/100"
            if score is not None
            else "ainda sem score completo de analise"
        )
        target_text = resume.target_role or "o cargo-alvo atual"
        track_text = (
            f"mais alinhado a oportunidades de nivel {get_track_label(seniority.recommended_track)}"
            if seniority is not None
            else "com a leitura de senioridade ainda pendente"
        )
        match_text = (
            f"Seus matches recentes tem media de {match_summary['average_match_score']}/100 e melhor score de {match_summary['best_match_score']}/100."
            if match_summary["total_matches"] > 0
            else "Voce ainda nao tem historico de aderencia com vagas."
        )
        return (
            f"{resume.label or resume.original_filename} hoje esta posicionado para {target_text}, {score_text}, e aparece {track_text}. "
            f"{match_text}"
        )

    def _build_profile_summary(self, *, resume: Resume, analysis, seniority, trust_decision) -> str:
        if not trust_decision.trusted:
            suggestion = trust_decision.diagnostics.get("suggestion")
            suggestion_text = f" {suggestion}" if isinstance(suggestion, str) and suggestion else ""
            return (
                "Este curriculo foi preservado para diagnostico, mas o estado de ingestao ainda nao e confiavel para scoring ou aderencia."
                f"{suggestion_text}"
            )
        if analysis is None:
            return (
                f"{resume.label or resume.original_filename} ja foi enviado e lido, mas ainda precisa de analise "
                "antes de receber um resumo completo de perfil."
            )

        strengths = []
        if analysis.structure_score >= 70:
            strengths.append("estrutura solida")
        if analysis.clarity_score >= 70:
            strengths.append("clareza boa")
        if analysis.market_fit_score >= 70:
            strengths.append("aderencia de mercado forte")
        if analysis.project_score >= 70:
            strengths.append("projetos criveis")
        strengths_text = ", ".join(strengths) if strengths else "algumas lacunas estruturais importantes"
        if strengths_text == "algumas lacunas estruturais importantes":
            strengths_text = "algumas lacunas estruturais importantes"

        track_text = (
            f" O nivel mais aderente hoje e {get_track_label(seniority.recommended_track)}."
            if seniority is not None
            else ""
        )
        return (
            f"Neste momento, o curriculo mostra {strengths_text}, com maior valor vindo dos sinais objetivos encontrados nas secoes atuais."
            f"{track_text}"
        )

    def _deduplicate(self, values: list[str]) -> list[str]:
        return list(OrderedDict.fromkeys(value for value in values if value))
