from __future__ import annotations

from django.db.models import Avg, Max

from hunter.choices import JobApplicationStatus
from hunter.models.models import Job, JobApplication, JobMatch, Resume, SavedJob

from .resume_comparison_service import ResumeComparisonService
from .resume_report_service import ResumeReportService

TRACK_LABELS = {
    "internship": "estagio",
    "junior": "junior",
    "mid": "pleno",
    "senior": "senior",
    "freelance": "freelancer",
}

PENDING_PARSE_STATUSES = {"pending", "processing"}


def get_track_label(value: str | None) -> str:
    return TRACK_LABELS.get(value or "", value or "seu nivel atual")


class DashboardService:
    TOP_MATCHES_LIMIT = 5
    RECOMMENDED_JOBS_LIMIT = 5
    MIN_RECOMMENDED_MATCH_SCORE = 40

    def __init__(
        self,
        *,
        report_service: ResumeReportService | None = None,
        comparison_service: ResumeComparisonService | None = None,
    ) -> None:
        self.report_service = report_service or ResumeReportService()
        self.comparison_service = comparison_service or ResumeComparisonService()

    def build(self, *, owner) -> dict[str, object]:
        total_jobs = Job.objects.filter(owner=owner).count()
        total_saved_jobs = SavedJob.objects.filter(owner=owner).count()
        total_applications = JobApplication.objects.filter(owner=owner).count()
        resume_queryset = (
            Resume.objects
            .filter(owner=owner)
            .select_related('analysis', 'seniority_assessment')
        )
        all_resumes = list(resume_queryset.order_by('-is_active', '-created_at'))
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
            .filter(
                owner=owner,
                resume__owner=owner,
                job__owner=owner,
            )
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
        comparison_payload = self.comparison_service.build(owner=owner)
        report_preview = (
            self.report_service.build(resume=active_resume)
            if active_resume is not None
            else None
        )

        return {
            "summary": {
                "total_resumes": len(all_resumes),
                "total_saved_jobs": total_saved_jobs,
                "total_applications": total_applications,
                "total_matches": match_queryset.count(),
                "active_resume_label": active_resume.label if active_resume is not None else None,
                "active_resume_target_role": (
                    active_resume.target_role if active_resume is not None else None
                ),
                "active_resume_status": self._derive_active_resume_status(
                    active_resume=active_resume,
                    analysis=analysis,
                    seniority_assessment=seniority_assessment,
                ),
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
            "activation": self._build_activation(
                active_resume=active_resume,
                analysis=analysis,
                seniority_assessment=seniority_assessment,
                total_jobs=total_jobs,
                total_saved_jobs=total_saved_jobs,
                total_applications=total_applications,
            ),
            "best_resume_summary": comparison_payload["best_resume_by_score"],
            "resume_report_preview": (
                {
                    "resume_id": report_preview["resume_id"],
                    "executive_summary": report_preview["executive_summary"],
                    "top_gap": report_preview["top_gaps"][0] if report_preview["top_gaps"] else None,
                    "top_priority_action": (
                        report_preview["priority_actions"][0]
                        if report_preview["priority_actions"]
                        else None
                    ),
                    "average_match_score": report_preview["recent_match_summary"]["average_match_score"],
                }
                if report_preview is not None
                else None
            ),
            "comparison_available": len(all_resumes) > 1,
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
                    "title": "Envie seu curriculo principal",
                    "detail": "Um curriculo atualizado libera analise, aderencia com vagas e orientacoes mais uteis no painel.",
                    "priority": 1,
                }
            ]

        actions: list[dict[str, object]] = []
        if analysis is None:
            actions.append(
                {
                    "action_type": "resume_analysis",
                    "title": "Gerar a analise do curriculo",
                    "detail": "Libere um diagnostico com score antes de priorizar as proximas oportunidades.",
                    "priority": 1,
                }
            )
        else:
            for recommendation in analysis.recommendations[:2]:
                actions.append(
                    {
                        "action_type": "resume_improvement",
                        "title": "Melhorar a qualidade do curriculo",
                        "detail": recommendation,
                        "priority": 2,
                    }
                )
            parsed_resume = analysis.raw_summary.get("parsed_resume", {})
            if not parsed_resume.get("projects"):
                actions.append(
                    {
                        "action_type": "project_signal",
                        "title": "Adicionar evidencia de projetos",
                        "detail": "Projetos ainda nao apareceram com clareza e podem reforcar sua credibilidade.",
                        "priority": 1,
                    }
                )
            if not parsed_resume.get("links"):
                actions.append(
                    {
                        "action_type": "link_signal",
                        "title": "Adicionar links de portfolio ou perfil",
                        "detail": "Links de portfolio, GitHub ou LinkedIn ajudam a aumentar a confianca no seu perfil.",
                        "priority": 2,
                    }
                )
        if seniority_assessment is None:
            actions.append(
                {
                    "action_type": "seniority_assessment",
                    "title": "Avaliar seu nivel-alvo",
                    "detail": "Gere a leitura de senioridade para concentrar candidaturas no nivel mais aderente.",
                    "priority": 2,
                }
            )
        else:
            actions.append(
                {
                    "action_type": "target_roles",
                    "title": "Priorizar o nivel certo de vaga",
                    "detail": f"Comece pelas oportunidades mais alinhadas ao nivel {get_track_label(seniority_assessment.recommended_track)}.",
                    "priority": 3,
                }
            )

        top_match = match_queryset.first()
        if top_match is not None and top_match.match_score < 60:
            actions.append(
                {
                    "action_type": "match_gap",
                    "title": "Fechar as principais lacunas de aderencia",
                    "detail": "Seus melhores matches ainda estao medianos ou baixos. Ajuste os sinais mais importantes antes de aplicar em volume.",
                    "priority": 1,
                }
            )

        actions.sort(key=lambda item: (item["priority"], item["title"]))
        return actions[:5]

    def _build_activation(
        self,
        *,
        active_resume,
        analysis,
        seniority_assessment,
        total_jobs: int,
        total_saved_jobs: int,
        total_applications: int,
    ) -> dict[str, object]:
        has_first_job_action = total_saved_jobs > 0 or total_applications > 0
        checklist = [
            {
                "id": "account_created",
                "title": "Conta criada",
                "detail": "Seu workspace ja esta pronto para organizar curriculo, vagas e candidaturas.",
                "completed": True,
            },
            {
                "id": "resume_uploaded",
                "title": "Curriculo enviado",
                "detail": "Com um curriculo ativo, a plataforma consegue liberar analise e priorizar proximos passos.",
                "completed": active_resume is not None,
            },
            {
                "id": "analysis_generated",
                "title": "Analise gerada",
                "detail": "A analise mostra a qualidade atual do curriculo e aponta os ajustes mais uteis.",
                "completed": analysis is not None,
            },
            {
                "id": "seniority_generated",
                "title": "Senioridade gerada",
                "detail": "A leitura de senioridade ajuda a focar nas vagas mais coerentes com o seu momento.",
                "completed": seniority_assessment is not None,
            },
            {
                "id": "job_search_completed",
                "title": "Busca realizada",
                "detail": "A busca monta sua shortlist inicial e abre o caminho para comparar oportunidades.",
                "completed": total_jobs > 0,
            },
            {
                "id": "first_job_action",
                "title": "Primeira acao em vaga",
                "detail": "Salvar uma vaga ou iniciar uma candidatura transforma pesquisa em progresso concreto.",
                "completed": has_first_job_action,
            },
        ]
        first_incomplete_index = next(
            (index for index, step in enumerate(checklist) if not step["completed"]),
            None,
        )
        for index, step in enumerate(checklist):
            step["current"] = index == first_incomplete_index and not step["completed"]

        completed_steps = sum(1 for step in checklist if step["completed"])
        total_steps = len(checklist)
        progress_percent = round((completed_steps / total_steps) * 100)

        return {
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "progress_percent": progress_percent,
            "is_complete": completed_steps == total_steps,
            "headline": self._build_activation_headline(completed_steps=completed_steps, total_steps=total_steps),
            "summary": self._build_activation_summary(
                completed_steps=completed_steps,
                total_steps=total_steps,
                active_resume=active_resume,
                total_jobs=total_jobs,
                has_first_job_action=has_first_job_action,
            ),
            "checklist": checklist,
            "next_best_action": self._build_next_best_action(
                active_resume=active_resume,
                analysis=analysis,
                seniority_assessment=seniority_assessment,
                total_jobs=total_jobs,
                has_first_job_action=has_first_job_action,
            ),
        }

    def _build_activation_headline(self, *, completed_steps: int, total_steps: int) -> str:
        if completed_steps == total_steps:
            return "Primeiro valor destravado"
        if completed_steps <= 2:
            return "Vamos chegar ao primeiro valor"
        if completed_steps == total_steps - 1:
            return "Falta so uma etapa para consolidar seu fluxo"
        return "Voce ja esta perto do primeiro valor"

    def _build_activation_summary(
        self,
        *,
        completed_steps: int,
        total_steps: int,
        active_resume,
        total_jobs: int,
        has_first_job_action: bool,
    ) -> str:
        remaining_steps = total_steps - completed_steps
        if remaining_steps == 0:
            return "Seu setup inicial ja cobre curriculo, diagnostico, busca e a primeira acao em vaga."
        if active_resume is None:
            return "Comece pelo curriculo principal para liberar as proximas etapas do produto com mais clareza."
        if total_jobs == 0:
            return "Seu curriculo ja esta no fluxo. Agora vale montar a primeira shortlist de vagas."
        if not has_first_job_action:
            return "Voce ja encontrou vagas. Falta transformar a busca em um primeiro movimento concreto."
        return f"Faltam {remaining_steps} etapas para fechar sua ativacao inicial."

    def _build_next_best_action(
        self,
        *,
        active_resume,
        analysis,
        seniority_assessment,
        total_jobs: int,
        has_first_job_action: bool,
    ) -> dict[str, str]:
        if active_resume is None:
            return {
                "action_type": "resume_upload",
                "title": "Envie seu curriculo principal",
                "detail": "Esse e o passo que libera analise, senioridade e aderencia com vagas.",
                "cta_label": "Enviar curriculo",
                "cta_href": "/resumes",
            }

        if active_resume.parse_status in PENDING_PARSE_STATUSES:
            return {
                "action_type": "resume_processing",
                "title": "Acompanhe o preparo do curriculo",
                "detail": "Estamos organizando o arquivo para liberar os proximos insights com seguranca.",
                "cta_label": "Ver curriculos",
                "cta_href": "/resumes",
            }

        if active_resume.parse_status != "completed":
            return {
                "action_type": "resume_replace",
                "title": "Envie uma nova versao do curriculo",
                "detail": "Uma versao mais limpa em PDF ou DOCX ajuda a liberar analise, senioridade e match.",
                "cta_label": "Corrigir curriculo",
                "cta_href": "/resumes",
            }

        if analysis is None:
            return {
                "action_type": "resume_analysis",
                "title": "Gere a analise do curriculo",
                "detail": "Com a analise pronta, voce descobre onde ajustar o material antes de buscar em volume.",
                "cta_label": "Analisar curriculo",
                "cta_href": "/resumes",
            }

        if seniority_assessment is None:
            return {
                "action_type": "seniority_assessment",
                "title": "Avalie sua senioridade",
                "detail": "Esse passo ajuda a priorizar vagas no nivel mais aderente ao seu momento atual.",
                "cta_label": "Avaliar senioridade",
                "cta_href": "/resumes",
            }

        if total_jobs == 0:
            return {
                "action_type": "job_search",
                "title": "Busque suas primeiras vagas",
                "detail": "Monte uma shortlist inicial para comparar oportunidades e identificar onde agir primeiro.",
                "cta_label": "Buscar vagas",
                "cta_href": "/jobs",
            }

        if not has_first_job_action:
            return {
                "action_type": "job_first_action",
                "title": "Salve uma vaga ou inicie uma candidatura",
                "detail": "A primeira acao transforma sua busca em progresso visivel dentro do produto.",
                "cta_label": "Tomar acao em vaga",
                "cta_href": "/jobs",
            }

        return {
            "action_type": "activation_complete",
            "title": "Continue pelo fluxo mais promissor",
            "detail": "Seu setup inicial esta pronto. Agora vale acompanhar candidaturas e priorizar as melhores oportunidades.",
            "cta_label": "Ver candidaturas",
            "cta_href": "/applications",
        }

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

    def _derive_active_resume_status(self, *, active_resume, analysis, seniority_assessment):
        if active_resume is None:
            return "not_set"
        if active_resume.parse_status != "completed":
            return "processing"
        if analysis is None:
            return "uploaded"
        if seniority_assessment is None:
            return "analyzed"
        return "ready"
