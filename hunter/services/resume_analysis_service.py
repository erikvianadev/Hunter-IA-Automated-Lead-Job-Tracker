from __future__ import annotations

import re

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
        focus_area = self._infer_focus_area(resume=resume, parsed_resume=parsed_resume)
        working_signals = self._build_working_signals(
            parsed_resume=parsed_resume,
            scores=scores,
            focus_area=focus_area,
        )
        missing_signals = self._build_missing_signals(
            parsed_resume=parsed_resume,
            scores=scores,
            text=text,
            focus_area=focus_area,
        )
        priority_actions = self._build_priority_actions(
            parsed_resume=parsed_resume,
            scores=scores,
            text=text,
            focus_area=focus_area,
        )
        priority_summary = self._build_priority_summary(priority_actions=priority_actions)
        strengths = [item["statement"] for item in working_signals][:5]
        weaknesses = [item["statement"] for item in missing_signals][:5]
        recommendations = self._build_recommendations(
            priority_actions=priority_actions,
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
                    "focus_area": focus_area,
                    "what_is_working": working_signals,
                    "what_is_missing": missing_signals,
                    "priority_actions": priority_actions,
                    "priority_summary": priority_summary,
                },
            },
        )
        return analysis

    def _build_working_signals(
        self,
        *,
        parsed_resume: dict[str, object],
        scores: dict[str, object],
        focus_area: dict[str, str],
    ) -> list[dict[str, str]]:
        strengths: list[dict[str, str]] = []
        skills = parsed_resume.get("skills", [])
        projects = parsed_resume.get("projects", [])
        links = parsed_resume.get("links", [])
        experience = parsed_resume.get("experience", [])
        if parsed_resume.get("summary"):
            strengths.append(
                {
                    "title": "Resumo inicial definido",
                    "statement": "O curriculo abre com um resumo que contextualiza seu perfil logo no inicio.",
                    "evidence": f"Resumo detectado para {focus_area['label']}.",
                    "why_it_works": "Isso reduz o tempo de triagem e deixa mais claro qual problema profissional voce resolve.",
                }
            )
        if experience:
            strengths.append(
                {
                    "title": "Experiencia profissional visivel",
                    "statement": "A experiencia profissional aparece de forma legivel e ajuda a sustentar sua narrativa.",
                    "evidence": f"Foram encontradas {len(experience)} entradas de experiencia.",
                    "why_it_works": "Isso ajuda a conectar stack, escopo e historico recente sem depender de adivinhacao do recrutador.",
                }
            )
        if skills:
            strengths.append(
                {
                    "title": "Stack explicita",
                    "statement": f"Ha sinais concretos de stack com {self._format_list(skills[:4])}.",
                    "evidence": f"{len(skills)} habilidades tecnicas foram agrupadas na leitura.",
                    "why_it_works": f"Isso melhora seu posicionamento para {focus_area['plural_label']} que filtram por tecnologia e contexto tecnico.",
                }
            )
        if projects:
            strengths.append(
                {
                    "title": "Projetos aparecem no curriculo",
                    "statement": "Os projetos citados ajudam a mostrar capacidade de execucao alem da lista de habilidades.",
                    "evidence": f"Foram encontrados {len(projects)} sinais de projeto ou portfolio.",
                    "why_it_works": "Projetos ajudam a transformar conhecimento declarado em prova pratica de entrega.",
                }
            )
        if links:
            strengths.append(
                {
                    "title": "Links de validacao disponiveis",
                    "statement": "O curriculo oferece links que reforcam portfolio, GitHub ou perfil profissional.",
                    "evidence": f"{len(links)} link(s) foram identificados na leitura.",
                    "why_it_works": "Isso adiciona camadas de validacao sem alongar o curriculo.",
                }
            )
        if scores["clarity_score"] >= 70:
            strengths.append(
                {
                    "title": "Leitura objetiva",
                    "statement": "O conteudo esta objetivo o bastante para uma leitura rapida.",
                    "evidence": f"Clareza atual em {scores['clarity_score']}/100.",
                    "why_it_works": "Uma triagem inicial fica mais eficiente quando as informacoes centrais aparecem sem excesso de ruido.",
                }
            )
        return strengths[:5]

    def _build_missing_signals(
        self,
        *,
        parsed_resume: dict[str, object],
        scores: dict[str, object],
        text: str,
        focus_area: dict[str, str],
    ) -> list[dict[str, str]]:
        weaknesses: list[dict[str, str]] = []
        skills = parsed_resume.get("skills", [])
        projects = parsed_resume.get("projects", [])
        if not parsed_resume.get("summary"):
            weaknesses.append(
                {
                    "title": "Falta de contexto inicial",
                    "statement": "Falta um resumo claro ou uma secao inicial de perfil.",
                    "evidence": "Nenhum resumo consistente foi identificado na abertura do curriculo.",
                    "risk": f"Sem esse contexto, fica mais dificil entender sua proposta para {focus_area['plural_label']}.",
                    "category": "summary",
                }
            )
        if len(skills) < 4:
            weaknesses.append(
                {
                    "title": "Stack pouco explicita",
                    "statement": "As habilidades tecnicas ainda aparecem de forma curta ou pouco agrupada.",
                    "evidence": f"A leitura encontrou {len(skills)} habilidade(s) explicitamente agrupada(s).",
                    "risk": f"Isso reduz a chance de bater com filtros e triagens de {focus_area['plural_label']}.",
                    "category": "skills",
                }
            )
        if not projects:
            weaknesses.append(
                {
                    "title": "Pouca prova pratica",
                    "statement": "Projetos com evidencia de execucao ainda estao ausentes ou muito fracos.",
                    "evidence": "Nenhum bloco de projetos foi encontrado na estrutura atual.",
                    "risk": f"Sem prova pratica, sua aderencia para {focus_area['plural_label']} perde sustentacao.",
                    "category": "projects",
                }
            )
        elif not self._has_metrics(text=text):
            weaknesses.append(
                {
                    "title": "Impacto pouco mensuravel",
                    "statement": "Os projetos aparecem, mas ainda sem numeros, escopo ou resultado concreto.",
                    "evidence": "A leitura nao encontrou sinais claros de metricas, volume ou resultado numerico.",
                    "risk": "Sem impacto observado, o curriculo fica descritivo e menos convincente.",
                    "category": "impact",
                }
            )
        if not parsed_resume.get("links"):
            weaknesses.append(
                {
                    "title": "Validacao externa limitada",
                    "statement": "Nao encontramos links de portfolio, GitHub, LinkedIn ou provas complementares.",
                    "evidence": "Nenhum link confiavel foi extraido do arquivo.",
                    "risk": "Voce perde uma forma simples de sustentar credibilidade sem ocupar mais espaco.",
                    "category": "links",
                }
            )
        if scores["structure_score"] < 60:
            weaknesses.append(
                {
                    "title": "Estrutura fraca para triagem",
                    "statement": "A estrutura de secoes ainda esta fraca e dificulta a leitura rapida.",
                    "evidence": f"Estrutura atual em {scores['structure_score']}/100.",
                    "risk": "Quando a ordem e a separacao das secoes nao ajudam, os sinais bons perdem forca.",
                    "category": "structure",
                }
            )
        if scores["clarity_score"] < 65:
            weaknesses.append(
                {
                    "title": "Leitura ainda pouco enxuta",
                    "statement": "A redacao ainda pode ficar mais direta para destacar stack, escopo e resultado.",
                    "evidence": f"Clareza atual em {scores['clarity_score']}/100.",
                    "risk": "O excesso de ambiguidade dilui o que deveria ser lido como diferencial.",
                    "category": "clarity",
                }
            )
        return weaknesses[:5]

    def _build_priority_actions(
        self,
        *,
        parsed_resume: dict[str, object],
        scores: dict[str, object],
        text: str,
        focus_area: dict[str, str],
    ) -> list[dict[str, object]]:
        actions: list[dict[str, object]] = []
        skills = parsed_resume.get("skills", [])
        projects = parsed_resume.get("projects", [])
        links = parsed_resume.get("links", [])

        if not projects:
            actions.append(
                {
                    "title": "Adicionar projetos com stack e resultado",
                    "priority_label": "Alta prioridade",
                    "priority_rank": 1,
                    "reason": "Hoje falta prova pratica de execucao no curriculo.",
                    "impact": f"Impacta sua aderencia para {focus_area['plural_label']} porque a vaga quer evidencias de entrega e nao so lista de tecnologias.",
                    "fix_first": True,
                    "category": "projects",
                }
            )
        elif not self._has_metrics(text=text):
            actions.append(
                {
                    "title": "Quantificar impacto dos projetos e experiencias",
                    "priority_label": "Alta prioridade",
                    "priority_rank": 1,
                    "reason": "Os projetos aparecem, mas ainda sem resultados concretos para sustentar senioridade e impacto.",
                    "impact": "Com numeros, escopo e efeito do que voce entregou, a leitura deixa de ser generica e passa a parecer comprovada.",
                    "fix_first": False,
                    "category": "impact",
                }
            )

        if len(skills) < 4:
            actions.append(
                {
                    "title": "Explicitar melhor a stack principal",
                    "priority_label": "Alta prioridade" if scores["market_fit_score"] < 60 else "Media prioridade",
                    "priority_rank": 1 if scores["market_fit_score"] < 60 else 2,
                    "reason": "A secao de habilidades ainda nao sustenta com clareza o tipo de vaga que voce quer disputar.",
                    "impact": f"Isso melhora a aderencia para {focus_area['plural_label']} que filtram logo por linguagem, framework e ferramentas-chave.",
                    "fix_first": False,
                    "category": "skills",
                }
            )

        if not parsed_resume.get("summary"):
            actions.append(
                {
                    "title": "Abrir o curriculo com um resumo direcionado",
                    "priority_label": "Alta prioridade" if scores["structure_score"] < 65 else "Media prioridade",
                    "priority_rank": 1 if scores["structure_score"] < 65 else 2,
                    "reason": "Sem contexto logo no inicio, seu posicionamento depende demais da leitura completa do documento.",
                    "impact": f"Ajuda a deixar claro seu foco em {focus_area['label']} antes mesmo de entrarem nos detalhes da experiencia.",
                    "fix_first": False,
                    "category": "summary",
                }
            )

        if scores["structure_score"] < 60:
            actions.append(
                {
                    "title": "Reorganizar a hierarquia das secoes",
                    "priority_label": "Alta prioridade",
                    "priority_rank": 1,
                    "reason": "A estrutura atual dificulta a triagem rapida e faz sinais bons competirem com ruido.",
                    "impact": "Corrigir primeiro aumenta o valor de tudo o que voce ja tem, porque melhora a legibilidade do curriculo inteiro.",
                    "fix_first": not actions,
                    "category": "structure",
                }
            )

        if not links:
            actions.append(
                {
                    "title": "Adicionar links de validacao",
                    "priority_label": "Media prioridade",
                    "priority_rank": 2,
                    "reason": "Falta uma ponte direta para portfolio, GitHub ou perfil profissional.",
                    "impact": "Isso ajuda a sustentar credibilidade com um ajuste simples e de baixo esforco.",
                    "fix_first": False,
                    "category": "links",
                }
            )

        if scores["clarity_score"] < 70:
            actions.append(
                {
                    "title": "Enxugar a redacao e destacar resultado",
                    "priority_label": "Media prioridade",
                    "priority_rank": 2,
                    "reason": "O curriculo ainda pode ser lido com mais rapidez e menos ambiguidade.",
                    "impact": "Bullets mais diretos deixam stack, escopo e resultado visiveis na primeira leitura.",
                    "fix_first": False,
                    "category": "clarity",
                }
            )

        if not actions:
            actions.append(
                {
                    "title": "Refinar a versao atual para vagas mais especificas",
                    "priority_label": "Baixa prioridade",
                    "priority_rank": 3,
                    "reason": "A base do curriculo ja esta consistente e nao ha um bloqueio estrutural evidente.",
                    "impact": f"O maior ganho agora vem de ajustar a narrativa para {focus_area['plural_label']} mais especificas.",
                    "fix_first": True,
                    "category": "focus",
                }
            )

        ordered_actions = sorted(
            actions,
            key=lambda item: (
                item["priority_rank"],
                0 if item["fix_first"] else 1,
                item["title"],
            ),
        )
        if ordered_actions:
            ordered_actions[0]["fix_first"] = True
        return ordered_actions[:5]

    def _build_priority_summary(
        self,
        *,
        priority_actions: list[dict[str, object]],
    ) -> dict[str, object]:
        if not priority_actions:
            return {
                "label": "Base consistente",
                "impact": "Seu curriculo ja tem base para disputar vagas proximas ao foco atual.",
                "directive": "Refine por vaga",
            }

        first_action = priority_actions[0]
        return {
            "label": first_action["priority_label"],
            "impact": first_action["impact"],
            "directive": "Corrija primeiro" if first_action.get("fix_first") else "Ajuste em seguida",
            "title": first_action["title"],
        }

    def _build_recommendations(
        self,
        *,
        priority_actions: list[dict[str, object]],
    ) -> list[str]:
        recommendations: list[str] = []
        for action in priority_actions[:5]:
            prefix = f"{action['priority_label']}: {action['title']}."
            recommendations.append(
                f"{prefix} Motivo: {action['reason']} Impacto: {action['impact']}"
            )
        return recommendations

    def _infer_focus_area(
        self,
        *,
        resume: Resume,
        parsed_resume: dict[str, object],
    ) -> dict[str, str]:
        target_text = f"{resume.target_role} {' '.join(parsed_resume.get('skills', []))}".lower()
        if any(token in target_text for token in ["backend", "api", "django", "flask", "fastapi", "docker"]):
            return {"key": "backend", "label": "vagas backend", "plural_label": "vagas backend"}
        if any(token in target_text for token in ["data", "analyst", "analytics", "sql", "pandas", "bi"]):
            return {"key": "dados", "label": "vagas de dados", "plural_label": "vagas de dados"}
        if any(token in target_text for token in ["front", "frontend", "react", "javascript", "typescript"]):
            return {"key": "frontend", "label": "vagas frontend", "plural_label": "vagas frontend"}
        if resume.target_role:
            role_label = resume.target_role.strip().lower()
            return {
                "key": "alvo",
                "label": f"vagas de {role_label}",
                "plural_label": f"vagas de {role_label}",
            }
        return {"key": "geral", "label": "vagas proximas ao seu perfil", "plural_label": "vagas proximas ao seu perfil"}

    def _has_metrics(self, *, text: str) -> bool:
        return bool(re.search(r"\b\d+(?:[%x]|k|m)?\b", text.lower()))

    def _format_list(self, values: list[str]) -> str:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} e {cleaned[1]}"
        return f"{', '.join(cleaned[:-1])} e {cleaned[-1]}"
