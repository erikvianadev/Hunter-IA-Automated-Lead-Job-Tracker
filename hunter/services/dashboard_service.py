from __future__ import annotations

from django.utils import timezone
from django.db.models import Avg, Max

from hunter.choices import JobApplicationStatus
from hunter.models.models import Job, JobApplication, JobMatch, Resume, SavedJob

from .billing_service import BillingService
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
HOT_APPLICATION_STATUSES = {
    JobApplicationStatus.INTERVIEW,
    JobApplicationStatus.OFFER,
}
APPLICATION_STATUS_LABELS = {
    JobApplicationStatus.SAVED: "Salva",
    JobApplicationStatus.APPLIED: "Aplicada",
    JobApplicationStatus.INTERVIEW: "Entrevista",
    JobApplicationStatus.REJECTED: "Rejeitada",
    JobApplicationStatus.OFFER: "Oferta",
    JobApplicationStatus.ARCHIVED: "Arquivada",
}
APPLICATION_STALE_DAYS = {
    JobApplicationStatus.OFFER: 2,
    JobApplicationStatus.INTERVIEW: 3,
    JobApplicationStatus.APPLIED: 7,
    JobApplicationStatus.SAVED: 10,
}
RESUME_SCORE_AREAS = {
    "projects": {
        "score_field": "project_score",
        "title": "Evidenciar projetos e impacto",
        "impact": "Projetos e resultados pesam na decisao de aplicar em vagas fortes e na preparacao de entrevistas.",
        "guidance": "Adicione 1 ou 2 projetos com problema, stack usada e resultado mensuravel antes de priorizar volume.",
    },
    "market_fit": {
        "score_field": "market_fit_score",
        "title": "Aproximar o curriculo do cargo-alvo",
        "impact": "Aderencia de mercado baixa reduz a confianca nos matches e dificulta escolher vagas boas.",
        "guidance": "Reforce palavras-chave e responsabilidades que aparecem nas vagas com melhor match desta semana.",
    },
    "clarity": {
        "score_field": "clarity_score",
        "title": "Deixar conquistas mais claras",
        "impact": "Clareza baixa aumenta o risco de uma candidatura forte parecer generica.",
        "guidance": "Troque descricoes amplas por bullets com acao, contexto tecnico e resultado.",
    },
    "structure": {
        "score_field": "structure_score",
        "title": "Organizar a leitura do curriculo",
        "impact": "Estrutura fraca atrapalha a triagem rapida antes de aplicar ou responder recrutadores.",
        "guidance": "Reordene secoes para destacar experiencia, stack e resultados logo no inicio.",
    },
}


def get_track_label(value: str | None) -> str:
    return TRACK_LABELS.get(value or "", value or "seu nivel atual")


class DashboardService:
    TOP_MATCHES_LIMIT = 5
    RECOMMENDED_JOBS_LIMIT = 5
    MIN_RECOMMENDED_MATCH_SCORE = 40
    JOBS_TO_ACT_LIMIT = 4
    MIN_ACTIONABLE_MATCH_SCORE = 65
    APPLICATION_ATTENTION_LIMIT = 4
    RESUME_GAPS_LIMIT = 3

    def __init__(
        self,
        *,
        report_service: ResumeReportService | None = None,
        comparison_service: ResumeComparisonService | None = None,
        billing_service: BillingService | None = None,
    ) -> None:
        self.report_service = report_service or ResumeReportService()
        self.comparison_service = comparison_service or ResumeComparisonService()
        self.billing_service = billing_service or BillingService()

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
        subscription = self.billing_service.get_subscription(owner=owner)
        features = set(subscription.get("features", []))
        can_view_report_preview = BillingService.FEATURE_PREMIUM_REPORTS in features
        can_compare_resumes = BillingService.FEATURE_RESUME_COMPARISON in features
        comparison_payload = (
            self.comparison_service.build(owner=owner)
            if can_compare_resumes
            else None
        )
        report_preview = (
            self.report_service.build(resume=active_resume)
            if active_resume is not None and can_view_report_preview
            else None
        )

        recommended_jobs = self._build_recommended_jobs(
            owner=owner,
            match_queryset=match_queryset,
        )
        weekly_control = self._build_weekly_control(
            owner=owner,
            active_resume=active_resume,
            analysis=analysis,
            seniority_assessment=seniority_assessment,
            match_queryset=match_queryset,
            recommended_jobs=recommended_jobs,
            total_jobs=total_jobs,
            total_saved_jobs=total_saved_jobs,
            total_applications=total_applications,
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
            "recommended_jobs": recommended_jobs,
            "weekly_control": weekly_control,
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
            "best_resume_summary": (
                comparison_payload["best_resume_by_score"]
                if comparison_payload is not None
                else None
            ),
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
            "comparison_available": can_compare_resumes and len(all_resumes) > 1,
            "premium_features": {
                "resume_report": self._build_premium_feature_state(
                    has_relevant_data=active_resume is not None,
                    is_entitled=can_view_report_preview,
                    locked_detail=(
                        "O preview do relatorio fica reservado para contas Pro."
                    ),
                    available_detail="Preview do relatorio liberado para sua conta.",
                    unavailable_detail=(
                        "Envie um curriculo para preparar o preview do relatorio."
                    ),
                ),
                "resume_comparison": self._build_premium_feature_state(
                    has_relevant_data=len(all_resumes) > 1,
                    is_entitled=can_compare_resumes,
                    locked_detail=(
                        "A comparacao entre curriculos fica reservada para contas Pro."
                    ),
                    available_detail="Comparacao entre curriculos liberada para sua conta.",
                    unavailable_detail=(
                        "Envie mais de uma versao de curriculo para comparar."
                    ),
                ),
            },
        }

    def _normalize_average(self, value):
        if value is None:
            return None
        return round(float(value), 2)

    def _build_premium_feature_state(
        self,
        *,
        has_relevant_data: bool,
        is_entitled: bool,
        locked_detail: str,
        available_detail: str,
        unavailable_detail: str,
    ) -> dict[str, object]:
        return {
            "available": bool(has_relevant_data and is_entitled),
            "locked": bool(has_relevant_data and not is_entitled),
            "detail": (
                available_detail
                if has_relevant_data and is_entitled
                else locked_detail
                if has_relevant_data
                else unavailable_detail
            ),
        }

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

    def _build_weekly_control(
        self,
        *,
        owner,
        active_resume,
        analysis,
        seniority_assessment,
        match_queryset,
        recommended_jobs,
        total_jobs: int,
        total_saved_jobs: int,
        total_applications: int,
    ) -> dict[str, object]:
        applications = self._build_applications_needing_attention(
            owner=owner,
            match_queryset=match_queryset,
        )
        jobs_to_act_now = self._build_jobs_to_act_now(
            recommended_jobs=recommended_jobs,
            total_applications=total_applications,
        )
        resume_gaps = self._build_resume_gaps_that_matter(
            active_resume=active_resume,
            analysis=analysis,
            match_queryset=match_queryset,
            has_actionable_jobs=bool(jobs_to_act_now),
            has_hot_applications=any(
                item["status"] in HOT_APPLICATION_STATUSES for item in applications
            ),
        )
        priority_candidates = self._build_weekly_priority_candidates(
            active_resume=active_resume,
            analysis=analysis,
            seniority_assessment=seniority_assessment,
            applications=applications,
            jobs_to_act_now=jobs_to_act_now,
            resume_gaps=resume_gaps,
            total_jobs=total_jobs,
            total_saved_jobs=total_saved_jobs,
            total_applications=total_applications,
        )
        ranked_priorities = self._rank_weekly_priorities(priority_candidates)

        return {
            "headline": "Mission Control semanal",
            "summary": self._build_weekly_control_summary(
                main_priority=ranked_priorities[0] if ranked_priorities else None,
                applications=applications,
                jobs_to_act_now=jobs_to_act_now,
                resume_gaps=resume_gaps,
            ),
            "main_priority": ranked_priorities[0] if ranked_priorities else None,
            "secondary_priorities": ranked_priorities[1:5],
            "applications_needing_attention": applications,
            "jobs_to_act_now": jobs_to_act_now,
            "resume_gaps": resume_gaps,
        }

    def _build_applications_needing_attention(self, *, owner, match_queryset):
        match_by_job_id = self._build_match_by_job_id(match_queryset=match_queryset)
        applications = (
            JobApplication.objects
            .filter(owner=owner, job__owner=owner)
            .exclude(status__in=[JobApplicationStatus.REJECTED, JobApplicationStatus.ARCHIVED])
            .select_related('job')
            .order_by('-updated_at', '-created_at')[:30]
        )
        attention_items = []
        now = timezone.now()

        for application in applications:
            match = match_by_job_id.get(application.job_id)
            has_notes = bool((application.notes or '').strip())
            missing_context = self._build_application_missing_context(
                application=application,
                match=match,
            )
            reference_at = application.updated_at or application.applied_at or application.created_at
            days_since_update = max((now - reference_at).days, 0) if reference_at else 0
            stale_after_days = APPLICATION_STALE_DAYS.get(application.status)
            is_stale = stale_after_days is not None and days_since_update >= stale_after_days
            score = 0
            criteria = []
            reason = ""
            suggested_action = ""

            if application.status == JobApplicationStatus.OFFER:
                score = 120
                criteria.append("oferta em aberto")
                if not has_notes:
                    criteria.append("sem criterios de decisao salvos")
                    reason = (
                        f"{application.job.company_name} esta em oferta, mas ainda faltam criterios salvos "
                        "para aceitar, negociar ou recusar com clareza."
                    )
                else:
                    reason = (
                        f"{application.job.company_name} esta em oferta; essa decisao tem mais impacto "
                        "que novas candidaturas nesta semana."
                    )
                suggested_action = "Compare proposta, escopo, riscos e proximo movimento de negociacao."
            elif application.status == JobApplicationStatus.INTERVIEW:
                score = 110
                criteria.append("entrevista ativa")
                if not has_notes:
                    criteria.append("sem pauta de entrevista")
                    reason = (
                        f"A entrevista com {application.job.company_name} esta ativa e ainda nao tem pauta "
                        "ou observacoes registradas."
                    )
                elif is_stale:
                    criteria.append(f"sem atualizacao ha {days_since_update} dias")
                    reason = (
                        f"A entrevista com {application.job.company_name} nao recebe atualizacao ha "
                        f"{days_since_update} dias."
                    )
                else:
                    reason = (
                        f"A entrevista com {application.job.company_name} merece preparacao antes de abrir "
                        "novas frentes."
                    )
                suggested_action = "Registre pauta, pontos fortes, perguntas abertas e proximo combinado."
            elif application.status == JobApplicationStatus.APPLIED and is_stale:
                score = 86
                criteria.append(f"sem atualizacao ha {days_since_update} dias")
                reason = (
                    f"A candidatura para {application.job.company_name} esta aplicada e parada ha "
                    f"{days_since_update} dias."
                )
                suggested_action = "Revise se cabe follow-up, mudanca de etapa ou arquivamento consciente."
            elif application.status == JobApplicationStatus.APPLIED and not has_notes:
                score = 74
                criteria.append("sem contexto de envio")
                reason = (
                    f"A candidatura para {application.job.company_name} foi aplicada, mas falta contexto "
                    "para decidir o proximo follow-up."
                )
                suggested_action = "Salve canal, data, contato, expectativa de retorno e qualquer sinal relevante."
            elif (
                application.status == JobApplicationStatus.SAVED
                and match is not None
                and match.match_score >= 75
            ):
                score = 70
                criteria.append(f"match de {match.match_score}/100 ainda sem decisao")
                reason = (
                    f"{application.job.company_name} esta salva com match de {match.match_score}/100 "
                    "e ainda nao virou candidatura nem descarte."
                )
                suggested_action = "Decida aplicar agora ou remover da fila para reduzir ruido."

            if score == 0:
                continue

            if missing_context:
                score += min(len(missing_context) * 2, 8)
                criteria.append("contexto incompleto")

            attention_items.append(
                {
                    "application_id": application.id,
                    "job_id": application.job_id,
                    "title": application.job.title,
                    "company_name": application.job.company_name,
                    "status": application.status,
                    "status_label": APPLICATION_STATUS_LABELS.get(application.status, application.status),
                    "updated_at": application.updated_at,
                    "days_since_update": days_since_update,
                    "reason": reason,
                    "suggested_action": suggested_action,
                    "missing_context": missing_context,
                    "objective_criteria": criteria,
                    "score": score,
                }
            )

        attention_items.sort(key=lambda item: (-item["score"], -item["days_since_update"], item["title"]))
        return self._with_ranks(attention_items[: self.APPLICATION_ATTENTION_LIMIT])

    def _build_jobs_to_act_now(self, *, recommended_jobs, total_applications: int):
        jobs = []
        for job in recommended_jobs:
            match_score = job["match_score"]
            if match_score < self.MIN_ACTIONABLE_MATCH_SCORE:
                continue

            if match_score >= 85:
                score = 96
                reason = (
                    f"Match alto de {match_score}/100 e nenhuma candidatura em andamento para esta vaga."
                )
            elif match_score >= 75:
                score = 88
                reason = (
                    f"Bom match de {match_score}/100; vale decidir antes de expandir a shortlist."
                )
            else:
                score = 76
                reason = (
                    f"Match util de {match_score}/100, suficiente para uma revisao objetiva agora."
                )

            if total_applications == 0:
                score += 4
                reason = f"{reason} Ela pode virar a primeira candidatura acompanhada no pipeline."

            jobs.append(
                {
                    **job,
                    "reason": reason,
                    "suggested_action": "Revise a recomendacao, cheque os gaps e aplique se o contexto ainda fizer sentido.",
                    "score": score,
                }
            )

            if len(jobs) >= self.JOBS_TO_ACT_LIMIT:
                break

        jobs.sort(key=lambda item: (-item["score"], -item["match_score"], item["title"]))
        return self._with_ranks(jobs)

    def _build_resume_gaps_that_matter(
        self,
        *,
        active_resume,
        analysis,
        match_queryset,
        has_actionable_jobs: bool,
        has_hot_applications: bool,
    ):
        if active_resume is None or analysis is None:
            return []

        parsed_resume = analysis.raw_summary.get("parsed_resume", {})
        gaps: list[dict[str, object]] = []
        context_suffix = self._build_resume_gap_context(
            has_actionable_jobs=has_actionable_jobs,
            has_hot_applications=has_hot_applications,
        )

        for gap_type, config in RESUME_SCORE_AREAS.items():
            score_value = getattr(analysis, config["score_field"], None)
            if score_value is None or score_value > 76:
                continue
            urgency = 86 - min(score_value, 86)
            gaps.append(
                {
                    "gap_type": gap_type,
                    "title": config["title"],
                    "impact": f"{config['impact']} {context_suffix}".strip(),
                    "guidance": config["guidance"],
                    "score": urgency,
                }
            )

        if not parsed_resume.get("projects"):
            gaps.append(
                {
                    "gap_type": "missing_projects",
                    "title": "Adicionar projetos visiveis",
                    "impact": "Projetos nao apareceram com clareza no curriculo ativo, o que enfraquece provas para vagas tecnicas.",
                    "guidance": "Inclua projetos com stack, papel exercido e resultado antes de aplicar nas melhores vagas.",
                    "score": 90,
                }
            )

        if not parsed_resume.get("links"):
            gaps.append(
                {
                    "gap_type": "missing_links",
                    "title": "Adicionar links de prova",
                    "impact": "Sem LinkedIn, portfolio ou GitHub visivel, recrutadores tem menos contexto para validar seu perfil.",
                    "guidance": "Inclua pelo menos um link confiavel no topo do curriculo ativo.",
                    "score": 78,
                }
            )

        top_match_gaps = self._extract_top_match_gaps(match_queryset=match_queryset)
        for index, gap in enumerate(top_match_gaps[:2]):
            gaps.append(
                {
                    "gap_type": f"match_gap_{index + 1}",
                    "title": "Fechar gap citado nos melhores matches",
                    "impact": f"Os melhores matches desta semana ainda citam: {gap}",
                    "guidance": "Reforce esse sinal no curriculo ou use a candidatura para explicar a experiencia relacionada.",
                    "score": 82 - index,
                }
            )

        unique_gaps = {}
        for gap in sorted(gaps, key=lambda item: (-item["score"], item["title"])):
            unique_gaps.setdefault(gap["title"], gap)

        return self._with_ranks(list(unique_gaps.values())[: self.RESUME_GAPS_LIMIT])

    def _build_weekly_priority_candidates(
        self,
        *,
        active_resume,
        analysis,
        seniority_assessment,
        applications,
        jobs_to_act_now,
        resume_gaps,
        total_jobs: int,
        total_saved_jobs: int,
        total_applications: int,
    ):
        candidates: list[dict[str, object]] = []

        if active_resume is None:
            candidates.append(
                self._priority_candidate(
                    source="setup",
                    score=130,
                    title="Criar a base da busca semanal",
                    reason="Ainda nao existe curriculo ativo; sem ele, o painel nao consegue priorizar vagas, matches ou candidaturas com seguranca.",
                    action="Envie seu curriculo principal e use essa versao como referencia da semana.",
                    cta_label="Enviar curriculo",
                    cta_href="/resumes",
                )
            )
            candidates.append(
                self._priority_candidate(
                    source="setup",
                    score=90,
                    title="Depois, liberar diagnostico do curriculo",
                    reason="A analise transforma o arquivo enviado em lacunas e proximas acoes concretas.",
                    action="Assim que o curriculo estiver processado, gere a analise antes de buscar em volume.",
                    cta_label="Abrir curriculos",
                    cta_href="/resumes",
                )
            )
            candidates.append(
                self._priority_candidate(
                    source="setup",
                    score=70,
                    title="Montar a primeira shortlist",
                    reason="Com curriculo e diagnostico prontos, as vagas passam a ter contexto de aderencia.",
                    action="Rode uma busca focada e salve apenas oportunidades que merecem decisao.",
                    cta_label="Abrir vagas",
                    cta_href="/jobs",
                )
            )
            return candidates

        if active_resume.parse_status in PENDING_PARSE_STATUSES:
            candidates.append(
                self._priority_candidate(
                    source="resume",
                    score=126,
                    title="Acompanhar processamento do curriculo",
                    reason="O curriculo ativo ainda esta em preparo; priorizar vagas agora geraria decisoes com pouco contexto.",
                    action="Confira o status do arquivo antes de rodar analises ou comparar vagas.",
                    cta_label="Ver curriculos",
                    cta_href="/resumes",
                )
            )
        elif active_resume.parse_status != "completed":
            candidates.append(
                self._priority_candidate(
                    source="resume",
                    score=128,
                    title="Corrigir o curriculo ativo",
                    reason="A versao atual nao esta pronta para alimentar analise, senioridade e matches confiaveis.",
                    action="Envie uma nova versao em PDF ou DOCX com texto selecionavel.",
                    cta_label="Corrigir curriculo",
                    cta_href="/resumes",
                )
            )
        elif analysis is None:
            candidates.append(
                self._priority_candidate(
                    source="resume",
                    score=106,
                    title="Gerar diagnostico antes de decidir a semana",
                    reason="O curriculo ja esta pronto, mas ainda falta analise para saber qual lacuna mais limita seus proximos movimentos.",
                    action="Gere a analise e use o principal gap para orientar vagas e candidaturas.",
                    cta_label="Analisar curriculo",
                    cta_href="/resumes",
                )
            )

        if seniority_assessment is None and active_resume.parse_status == "completed":
            candidates.append(
                self._priority_candidate(
                    source="resume",
                    score=82,
                    title="Definir o nivel de vaga mais coerente",
                    reason="Sem leitura de senioridade, a shortlist pode misturar oportunidades boas com vagas fora do seu momento.",
                    action="Gere a avaliacao de senioridade e concentre energia no nivel mais aderente.",
                    cta_label="Avaliar senioridade",
                    cta_href="/resumes",
                )
            )

        if total_jobs == 0 and analysis is not None:
            candidates.append(
                self._priority_candidate(
                    source="jobs",
                    score=80,
                    title="Criar a shortlist da semana",
                    reason="Seu curriculo ja tem contexto, mas ainda nao ha vagas no workspace para transformar em decisao.",
                    action="Busque vagas alinhadas ao cargo-alvo e salve apenas as melhores para triagem.",
                    cta_label="Buscar vagas",
                    cta_href="/jobs",
                )
            )
        elif total_jobs > 0 and total_saved_jobs == 0 and total_applications == 0:
            candidates.append(
                self._priority_candidate(
                    source="jobs",
                    score=78,
                    title="Transformar busca em decisao",
                    reason="Ja existem vagas no workspace, mas nenhuma foi salva ou aplicada; isso deixa a semana sem foco operacional.",
                    action="Escolha as vagas com melhor aderencia e salve ou aplique nas que merecem energia agora.",
                    cta_label="Abrir vagas",
                    cta_href="/jobs",
                )
            )

        for application in applications:
            candidates.append(
                self._priority_candidate(
                    source="application",
                    score=application["score"],
                    title=f"{application['status_label']}: {application['title']}",
                    reason=application["reason"],
                    action=application["suggested_action"],
                    cta_label="Abrir candidaturas",
                    cta_href="/applications",
                    source_id=application["application_id"],
                )
            )

        for job in jobs_to_act_now:
            candidates.append(
                self._priority_candidate(
                    source="job",
                    score=job["score"],
                    title=f"Agir na vaga: {job['title']}",
                    reason=job["reason"],
                    action=job["suggested_action"],
                    cta_label="Abrir vagas",
                    cta_href="/jobs",
                    source_id=job["job_id"],
                )
            )

        for gap in resume_gaps:
            candidates.append(
                self._priority_candidate(
                    source="resume_gap",
                    score=gap["score"],
                    title=gap["title"],
                    reason=gap["impact"],
                    action=gap["guidance"],
                    cta_label="Abrir curriculos",
                    cta_href="/resumes",
                    source_id=gap["gap_type"],
                )
            )

        return candidates

    def _rank_weekly_priorities(self, candidates):
        source_limits = {
            "application": 2,
            "job": 1,
            "resume_gap": 2,
            "resume": 2,
            "setup": 3,
            "jobs": 1,
        }
        selected = []
        source_counts: dict[str, int] = {}
        sorted_candidates = sorted(
            candidates,
            key=lambda item: (-item["score"], item["source"], item["title"]),
        )

        for candidate in sorted_candidates:
            source = candidate["source"]
            source_count = source_counts.get(source, 0)
            if source_count >= source_limits.get(source, 1):
                continue
            selected.append(candidate)
            source_counts[source] = source_count + 1
            if len(selected) == 5:
                break

        if len(selected) < 3:
            for candidate in sorted_candidates:
                if candidate in selected:
                    continue
                selected.append(candidate)
                if len(selected) == 3:
                    break

        return self._with_ranks(selected)

    def _build_weekly_control_summary(
        self,
        *,
        main_priority,
        applications,
        jobs_to_act_now,
        resume_gaps,
    ) -> str:
        if main_priority is None:
            return "Nenhum bloqueio operacional forte apareceu agora; use a semana para ampliar oportunidades com calma."

        parts = [f"Comece por {main_priority['title'].lower()}."]
        if applications:
            parts.append(f"{len(applications)} candidatura(s) tem criterio objetivo de atencao.")
        if jobs_to_act_now:
            parts.append(f"{len(jobs_to_act_now)} vaga(s) tem match suficiente para decisao agora.")
        if resume_gaps:
            parts.append(f"{len(resume_gaps)} lacuna(s) do curriculo podem afetar os proximos movimentos.")
        return " ".join(parts)

    def _priority_candidate(
        self,
        *,
        source: str,
        score: int,
        title: str,
        reason: str,
        action: str,
        cta_label: str,
        cta_href: str,
        source_id=None,
    ) -> dict[str, object]:
        return {
            "source": source,
            "source_id": source_id,
            "score": score,
            "title": title,
            "reason": reason,
            "action": action,
            "cta_label": cta_label,
            "cta_href": cta_href,
        }

    def _build_match_by_job_id(self, *, match_queryset):
        match_by_job_id = {}
        for match in match_queryset:
            current = match_by_job_id.get(match.job_id)
            if current is None or match.match_score > current.match_score:
                match_by_job_id[match.job_id] = match
        return match_by_job_id

    def _build_application_missing_context(self, *, application, match):
        missing = []
        if match is None:
            missing.append("match com curriculo")
        elif not match.recommendation:
            missing.append("recomendacao de aderencia")

        if not (application.notes or "").strip():
            if application.status == JobApplicationStatus.INTERVIEW:
                missing.append("pauta da entrevista")
            elif application.status == JobApplicationStatus.OFFER:
                missing.append("criterios de decisao da oferta")
            else:
                missing.append("notas de acompanhamento")

        if application.status != JobApplicationStatus.SAVED and not application.applied_at:
            missing.append("data de aplicacao")

        if not application.job.url:
            missing.append("link original da vaga")

        return missing

    def _build_resume_gap_context(self, *, has_actionable_jobs: bool, has_hot_applications: bool) -> str:
        if has_hot_applications:
            return "Isso importa agora porque ha candidatura quente precisando de preparo."
        if has_actionable_jobs:
            return "Isso importa agora porque ha vagas boas para decidir antes de aplicar."
        return "Isso importa agora porque define a qualidade das proximas buscas."

    def _extract_top_match_gaps(self, *, match_queryset):
        extracted = []
        seen = set()
        for match in match_queryset[: self.TOP_MATCHES_LIMIT]:
            if match.match_score < self.MIN_ACTIONABLE_MATCH_SCORE:
                continue
            for gap in match.gaps or []:
                normalized = str(gap).strip()
                if not normalized or normalized.lower() in seen:
                    continue
                extracted.append(normalized)
                seen.add(normalized.lower())
                if len(extracted) >= 3:
                    return extracted
        return extracted

    def _with_ranks(self, items):
        ranked = []
        for index, item in enumerate(items, start=1):
            ranked.append({**item, "rank": index})
        return ranked

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
            structured_actions = analysis.raw_summary.get("priority_actions", [])
            if structured_actions:
                for item in structured_actions[:2]:
                    actions.append(
                        {
                            "action_type": f"{item.get('category', 'resume_improvement')}_signal",
                            "title": item.get("title", "Melhorar a qualidade do curriculo"),
                            "detail": f"{item.get('reason', '')} {item.get('impact', '')}".strip(),
                            "priority": item.get("priority_rank", 2),
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
