from __future__ import annotations

from collections import Counter

from django.db.models import Avg, Max

from hunter.models.models import JobMatch, Resume


AREA_CONFIG = {
    "structure": {
        "field": "structure_score",
        "label": "Estrutura",
        "strength": "mais fácil de escanear por recrutadores e sistemas de triagem",
        "weakness": "pode esconder informações boas por falta de organização",
    },
    "clarity": {
        "field": "clarity_score",
        "label": "Clareza",
        "strength": "explica melhor seu papel, escopo e impacto sem exigir muita interpretação",
        "weakness": "pode deixar o recrutador com mais dúvidas sobre senioridade e responsabilidades",
    },
    "market_fit": {
        "field": "market_fit_score",
        "label": "Aderência ao mercado",
        "strength": "conversa melhor com palavras-chave, foco de cargo e expectativas do mercado",
        "weakness": "pode parecer menos direcionado para a vaga mesmo com boa experiência",
    },
    "projects": {
        "field": "project_score",
        "label": "Projetos e evidências",
        "strength": "mostra provas mais concretas de entrega técnica e impacto",
        "weakness": "precisa de mais exemplos concretos de stack, resultado ou escopo",
    },
}


class ResumeComparisonService:
    def build(self, *, owner, resume_ids: list[int] | None = None) -> dict[str, object]:
        queryset = (
            Resume.objects
            .filter(owner=owner)
            .select_related('analysis', 'seniority_assessment')
            .order_by('-is_active', '-created_at')
        )
        if resume_ids:
            queryset = queryset.filter(id__in=resume_ids)

        resumes = list(queryset)
        compared_resumes = [self._serialize_resume(resume) for resume in resumes]
        compared_resumes = self._add_contextual_resume_guidance(compared_resumes=compared_resumes)
        likely_target_role = self._derive_likely_target_role(compared_resumes=compared_resumes)
        area_comparison = self._build_area_comparison(compared_resumes=compared_resumes)
        routing_recommendations = self._build_routing_recommendations(
            compared_resumes=compared_resumes,
            likely_target_role=likely_target_role,
        )

        return {
            "compared_resumes": compared_resumes,
            "best_resume_by_score": self._pick_best_resume(compared_resumes=compared_resumes),
            "best_resume_for_likely_target": self._pick_best_for_target(
                compared_resumes=compared_resumes,
                likely_target_role=likely_target_role,
            ),
            "likely_target_role": likely_target_role,
            "comparison_summary": self._build_summary(
                compared_resumes=compared_resumes,
                likely_target_role=likely_target_role,
                routing_recommendations=routing_recommendations,
            ),
            "main_differences": self._build_main_differences(compared_resumes=compared_resumes),
            "stronger_areas": self._build_stronger_areas(compared_resumes=compared_resumes),
            "area_comparison": area_comparison,
            "routing_recommendations": routing_recommendations,
            "use_now_recommendation": (
                routing_recommendations[0] if routing_recommendations else None
            ),
        }

    def _serialize_resume(self, resume: Resume) -> dict[str, object]:
        analysis = resume.analysis if hasattr(resume, 'analysis') else None
        seniority = resume.seniority_assessment if hasattr(resume, 'seniority_assessment') else None
        match_summary = JobMatch.objects.filter(
            owner=resume.owner,
            resume=resume,
        ).aggregate(
            average_match_score=Avg('match_score'),
            best_match_score=Max('match_score'),
        )
        average_match_score = match_summary["average_match_score"]
        return {
            "id": resume.id,
            "label": resume.label or resume.original_filename,
            "target_role": resume.target_role,
            "is_active": resume.is_active,
            "parse_status": resume.parse_status,
            "overall_score": analysis.overall_score if analysis is not None else None,
            "structure_score": analysis.structure_score if analysis is not None else None,
            "clarity_score": analysis.clarity_score if analysis is not None else None,
            "market_fit_score": analysis.market_fit_score if analysis is not None else None,
            "project_score": analysis.project_score if analysis is not None else None,
            "recommended_track": (
                seniority.recommended_track if seniority is not None else None
            ),
            "average_match_score": (
                round(float(average_match_score), 2)
                if average_match_score is not None
                else None
            ),
            "best_match_score": match_summary["best_match_score"],
            "created_at": resume.created_at,
            "updated_at": resume.updated_at,
        }

    def _add_contextual_resume_guidance(
        self,
        *,
        compared_resumes: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        for resume in compared_resumes:
            strength_areas = self._build_resume_area_guidance(resume=resume, kind="strength")
            weak_areas = self._build_resume_area_guidance(resume=resume, kind="weakness")
            resume["strength_areas"] = strength_areas
            resume["weak_areas"] = weak_areas
            resume["use_now_for"] = self._build_use_now_for(resume=resume)
            resume["caution_for"] = self._build_caution_for(resume=resume)
            resume["decision_note"] = self._build_resume_decision_note(
                resume=resume,
                strength_areas=strength_areas,
                weak_areas=weak_areas,
            )
        return compared_resumes

    def _pick_best_resume(self, *, compared_resumes: list[dict[str, object]]):
        scored_resumes = [
            resume for resume in compared_resumes if resume["overall_score"] is not None
        ]
        if not scored_resumes:
            return None
        return max(
            scored_resumes,
            key=lambda item: (
                item["overall_score"],
                item["market_fit_score"] or 0,
                item["project_score"] or 0,
                item["best_match_score"] or 0,
                int(bool(item["is_active"])),
            ),
        )

    def _pick_best_for_target(
        self,
        *,
        compared_resumes: list[dict[str, object]],
        likely_target_role: str | None,
    ):
        if not compared_resumes:
            return None
        target_candidates = [
            resume
            for resume in compared_resumes
            if likely_target_role
            and (resume["target_role"] or "").strip().lower() == likely_target_role.lower()
        ]
        candidates = target_candidates or compared_resumes
        scored_candidates = [
            resume for resume in candidates if resume["market_fit_score"] is not None
        ]
        if not scored_candidates:
            return None
        return max(
            scored_candidates,
            key=lambda item: (
                item["market_fit_score"],
                item["overall_score"] or 0,
                item["best_match_score"] or 0,
                int(bool(item["is_active"])),
            ),
        )

    def _derive_likely_target_role(self, *, compared_resumes: list[dict[str, object]]) -> str | None:
        active_target = next(
            (
                resume["target_role"]
                for resume in compared_resumes
                if resume["is_active"] and resume["target_role"]
            ),
            None,
        )
        if active_target:
            return active_target

        roles = [resume["target_role"] for resume in compared_resumes if resume["target_role"]]
        if not roles:
            return None
        return Counter(roles).most_common(1)[0][0]

    def _build_summary(
        self,
        *,
        compared_resumes: list[dict[str, object]],
        likely_target_role: str | None,
        routing_recommendations: list[dict[str, object]] | None = None,
    ) -> str:
        if not compared_resumes:
            return "Ainda não há currículos disponíveis para comparar."

        best_resume = self._pick_best_resume(compared_resumes=compared_resumes)
        if len(compared_resumes) == 1:
            return "Há apenas uma versão disponível; use a leitura abaixo como diagnóstico do currículo atual."

        if best_resume is None:
            return "As versões foram enviadas, mas ainda falta score de análise para uma comparação realmente acionável."

        target_text = (
            f" para {likely_target_role}"
            if likely_target_role
            else ""
        )
        route = routing_recommendations[0] if routing_recommendations else None
        route_text = (
            f" Para usar agora, a recomendação mais prática é {route['recommended_resume']['label']} em {route['title'].lower()}."
            if route
            else ""
        )
        return (
            f"{best_resume['label']} é a versão mais forte no conjunto{target_text}, "
            f"mas a melhor escolha muda conforme o tipo de vaga e o sinal que você quer enfatizar."
            f"{route_text}"
        )

    def _build_main_differences(self, *, compared_resumes: list[dict[str, object]]) -> list[str]:
        if len(compared_resumes) < 2:
            return []

        differences: list[str] = []
        for area_key in ("structure", "clarity", "projects", "market_fit"):
            config = AREA_CONFIG[area_key]
            winner = self._winner_for_area(compared_resumes, config["field"])
            if winner is not None:
                differences.append(
                    f"{config['label']}: {winner['label']} leva vantagem porque {config['strength']}."
                )

        match_winner = self._winner_for_area(compared_resumes, "best_match_score")
        if match_winner is not None:
            differences.append(
                f"Histórico de matches: {match_winner['label']} tem o melhor sinal recente de aderência."
            )
        return differences[:5]

    def _build_stronger_areas(self, *, compared_resumes: list[dict[str, object]]) -> dict[str, object]:
        return {
            "structure": self._winner_for_area(compared_resumes, "structure_score"),
            "clarity": self._winner_for_area(compared_resumes, "clarity_score"),
            "projects": self._winner_for_area(compared_resumes, "project_score"),
            "market_fit": self._winner_for_area(compared_resumes, "market_fit_score"),
        }

    def _build_area_comparison(
        self,
        *,
        compared_resumes: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        comparison: list[dict[str, object]] = []
        for key, config in AREA_CONFIG.items():
            field_name = config["field"]
            scored = [
                {
                    "resume_id": resume["id"],
                    "resume_label": resume["label"],
                    "score": resume[field_name],
                }
                for resume in compared_resumes
                if resume[field_name] is not None
            ]
            winner = self._winner_for_area(compared_resumes, field_name)
            spread = None
            if scored:
                scores = [item["score"] for item in scored]
                spread = max(scores) - min(scores)
            comparison.append(
                {
                    "key": key,
                    "label": config["label"],
                    "winner": winner,
                    "spread": spread,
                    "scores": sorted(scored, key=lambda item: item["score"], reverse=True),
                    "decision_note": self._build_area_decision_note(
                        area_key=key,
                        winner=winner,
                        spread=spread,
                    ),
                }
            )
        return comparison

    def _build_routing_recommendations(
        self,
        *,
        compared_resumes: list[dict[str, object]],
        likely_target_role: str | None,
    ) -> list[dict[str, object]]:
        recommendations: list[dict[str, object]] = []
        best_target_resume = self._pick_best_for_target(
            compared_resumes=compared_resumes,
            likely_target_role=likely_target_role,
        )
        if best_target_resume is not None:
            title = (
                f"Vagas de {likely_target_role}"
                if likely_target_role
                else "Vagas alinhadas ao foco principal"
            )
            recommendations.append(
                self._build_route(
                    context_key="target_role",
                    title=title,
                    recommended_resume=best_target_resume,
                    when_to_use="Use quando a vaga parece próxima do cargo-alvo declarado e você precisa maximizar aderência de mercado.",
                    why=self._score_reason(
                        resume=best_target_resume,
                        fields=("market_fit_score", "overall_score"),
                        label="aderência e qualidade geral",
                    ),
                )
            )

        ats_resume = self._pick_by_weight(
            compared_resumes=compared_resumes,
            weighted_fields={"structure_score": 0.5, "clarity_score": 0.5},
        )
        if ats_resume is not None:
            recommendations.append(
                self._build_route(
                    context_key="fast_screening",
                    title="Triagem rápida ou ATS",
                    recommended_resume=ats_resume,
                    when_to_use="Use em vagas com inscrição em volume, formulários longos ou descrição genérica que depende de leitura rápida.",
                    why=self._score_reason(
                        resume=ats_resume,
                        fields=("structure_score", "clarity_score"),
                        label="estrutura e clareza",
                    ),
                )
            )

        technical_resume = self._pick_by_weight(
            compared_resumes=compared_resumes,
            weighted_fields={"project_score": 0.6, "market_fit_score": 0.4},
        )
        if technical_resume is not None:
            recommendations.append(
                self._build_route(
                    context_key="technical_evidence",
                    title="Vagas técnicas com prova de entrega",
                    recommended_resume=technical_resume,
                    when_to_use="Use quando o anúncio cobra projetos, stack, ownership ou exemplos concretos de impacto.",
                    why=self._score_reason(
                        resume=technical_resume,
                        fields=("project_score", "market_fit_score"),
                        label="projetos e aderência técnica",
                    ),
                )
            )

        overall_resume = self._pick_best_resume(compared_resumes=compared_resumes)
        if overall_resume is not None:
            recommendations.append(
                self._build_route(
                    context_key="default_now",
                    title="Padrão para aplicar agora",
                    recommended_resume=overall_resume,
                    when_to_use="Use como escolha segura quando a vaga não exige um recorte específico ou quando você precisa decidir rápido.",
                    why=self._score_reason(
                        resume=overall_resume,
                        fields=("overall_score", "market_fit_score", "best_match_score"),
                        label="score geral, aderência e histórico de match",
                    ),
                )
            )

        return self._deduplicate_routes(recommendations)[:4]

    def _winner_for_area(self, compared_resumes: list[dict[str, object]], field_name: str):
        candidates = [resume for resume in compared_resumes if resume[field_name] is not None]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (
                item[field_name],
                item["overall_score"] or 0,
                item["best_match_score"] or 0,
                int(bool(item["is_active"])),
            ),
        )

    def _pick_by_weight(
        self,
        *,
        compared_resumes: list[dict[str, object]],
        weighted_fields: dict[str, float],
    ):
        candidates = []
        for resume in compared_resumes:
            available = [
                (resume[field_name], weight)
                for field_name, weight in weighted_fields.items()
                if resume[field_name] is not None
            ]
            if available:
                score = sum(value * weight for value, weight in available)
                weight_total = sum(weight for _, weight in available)
                candidates.append((resume, score / weight_total))
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (
                item[1],
                item[0]["overall_score"] or 0,
                item[0]["best_match_score"] or 0,
                int(bool(item[0]["is_active"])),
            ),
        )[0]

    def _build_resume_area_guidance(
        self,
        *,
        resume: dict[str, object],
        kind: str,
    ) -> list[dict[str, object]]:
        scored_areas = [
            {
                "key": key,
                "label": config["label"],
                "score": resume[config["field"]],
                "guidance": config[kind],
            }
            for key, config in AREA_CONFIG.items()
            if resume[config["field"]] is not None
        ]
        reverse = kind == "strength"
        return sorted(scored_areas, key=lambda item: item["score"], reverse=reverse)[:2]

    def _build_use_now_for(self, *, resume: dict[str, object]) -> list[str]:
        uses: list[str] = []
        area_keys = [item["key"] for item in resume.get("strength_areas", [])]
        if "market_fit" in area_keys:
            uses.append("vagas próximas do cargo-alvo e com palavras-chave parecidas")
        if "projects" in area_keys:
            uses.append("processos que valorizam projetos, stack e entregas concretas")
        if "structure" in area_keys or "clarity" in area_keys:
            uses.append("triagens rápidas em que leitura objetiva pesa bastante")
        if resume.get("best_match_score"):
            uses.append("vagas semelhantes aos matches em que essa versão já performou bem")
        if not uses:
            uses.append("comparações iniciais, até gerar análise e senioridade completas")
        return uses[:3]

    def _build_caution_for(self, *, resume: dict[str, object]) -> list[str]:
        cautions: list[str] = []
        for area in resume.get("weak_areas", []):
            if area["key"] == "market_fit":
                cautions.append("vagas muito específicas sem ajustar palavras-chave e foco do cargo")
            elif area["key"] == "projects":
                cautions.append("vagas técnicas que pedem evidências fortes de entrega")
            elif area["key"] == "clarity":
                cautions.append("processos com pouca entrevista inicial, onde o currículo precisa explicar tudo sozinho")
            elif area["key"] == "structure":
                cautions.append("formulários e triagens que dependem de leitura muito escaneável")
        return cautions[:2]

    def _build_resume_decision_note(
        self,
        *,
        resume: dict[str, object],
        strength_areas: list[dict[str, object]],
        weak_areas: list[dict[str, object]],
    ) -> str:
        if not strength_areas:
            return "Ainda falta análise para dizer onde esta versão deve ser usada com mais segurança."
        strength = strength_areas[0]
        note = (
            f"Use quando {strength['guidance']}; o score de {strength['label'].lower()} "
            f"é {strength['score']}/100."
        )
        if weak_areas:
            weakness = weak_areas[0]
            note += (
                f" Antes de usar em vagas mais exigentes, revise {weakness['label'].lower()} "
                f"porque esta é a área mais frágil."
            )
        return note

    def _build_area_decision_note(
        self,
        *,
        area_key: str,
        winner: dict[str, object] | None,
        spread: int | None,
    ) -> str:
        config = AREA_CONFIG[area_key]
        if winner is None or spread is None:
            return f"Falta score de {config['label'].lower()} para comparar essa área."
        if spread <= 3:
            return (
                f"A diferença em {config['label'].lower()} é pequena; decida pelo contexto da vaga "
                "ou pelo currículo mais alinhado ao cargo."
            )
        return (
            f"{winner['label']} leva vantagem clara em {config['label'].lower()} e tende a funcionar melhor "
            f"quando a vaga exige {config['strength']}."
        )

    def _build_route(
        self,
        *,
        context_key: str,
        title: str,
        recommended_resume: dict[str, object],
        when_to_use: str,
        why: str,
    ) -> dict[str, object]:
        return {
            "context_key": context_key,
            "title": title,
            "recommended_resume": recommended_resume,
            "why": why,
            "when_to_use": when_to_use,
            "watch_out": self._build_watch_out(resume=recommended_resume),
            "next_step": self._build_next_step(resume=recommended_resume),
            "confidence": self._derive_confidence(resume=recommended_resume),
        }

    def _score_reason(
        self,
        *,
        resume: dict[str, object],
        fields: tuple[str, ...],
        label: str,
    ) -> str:
        scores = [resume[field] for field in fields if resume.get(field) is not None]
        if not scores:
            return f"{resume['label']} é a melhor opção disponível para esse contexto, mas ainda precisa de mais dados de score."
        average = round(sum(scores) / len(scores))
        return f"{resume['label']} combina melhor {label}, com média de {average}/100 nos sinais usados para essa rota."

    def _build_watch_out(self, *, resume: dict[str, object]) -> str:
        weak_areas = resume.get("weak_areas", [])
        if not weak_areas:
            return "Sem uma lacuna dominante nos scores atuais; revise a vaga antes de aplicar."
        weakest = weak_areas[0]
        return (
            f"Atenção a {weakest['label'].lower()}: {weakest['guidance']}."
        )

    def _build_next_step(self, *, resume: dict[str, object]) -> str:
        weak_areas = resume.get("weak_areas", [])
        if not weak_areas:
            return "Use esta versão como base e gere matches com vagas reais para validar a escolha."
        weakest = weak_areas[0]
        return (
            f"Antes de candidaturas mais importantes, ajuste {weakest['label'].lower()} nesta versão."
        )

    def _derive_confidence(self, *, resume: dict[str, object]) -> str:
        if resume.get("overall_score") is None:
            return "baixa"
        if (resume.get("best_match_score") or 0) >= 75 or (resume.get("overall_score") or 0) >= 75:
            return "alta"
        if (resume.get("overall_score") or 0) >= 60:
            return "média"
        return "baixa"

    def _deduplicate_routes(
        self,
        recommendations: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        seen: set[tuple[str, int]] = set()
        unique: list[dict[str, object]] = []
        for recommendation in recommendations:
            key = (
                recommendation["context_key"],
                recommendation["recommended_resume"]["id"],
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(recommendation)
        return unique
