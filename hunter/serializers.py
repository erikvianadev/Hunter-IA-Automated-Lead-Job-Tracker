from urllib.parse import urlparse

from rest_framework import serializers

from .choices import JobApplicationStatus

from .models.models import (
    Job,
    JobApplication,
    JobMatch,
    Lead,
    Resume,
    ResumeAnalysis,
    SavedJob,
    SeniorityAssessment,
    Tag,
)

SOURCE_LABELS = {
    'ashbyhq.com': 'Ashby',
    'boards.greenhouse.io': 'Greenhouse',
    'greenhouse.io': 'Greenhouse',
    'jobs.ashbyhq.com': 'Ashby',
    'jobs.lever.co': 'Lever',
    'lever.co': 'Lever',
    'remotive.com': 'Remotive',
    'remoteok.com': 'RemoteOK',
    'weworkremotely.com': 'We Work Remotely',
    'indeed.com': 'Indeed',
}

APPLICATION_STAGE_PRESENTATIONS = {
    JobApplicationStatus.SAVED: {
        'label': 'Salva',
        'tone': 'muted',
        'title': 'No radar',
        'summary': 'Vaga separada para decidir se vale entrar no pipeline.',
    },
    JobApplicationStatus.APPLIED: {
        'label': 'Aplicada',
        'tone': 'good',
        'title': 'Aplicacao enviada',
        'summary': 'Agora o foco e acompanhar retorno e registrar atualizacoes.',
    },
    JobApplicationStatus.INTERVIEW: {
        'label': 'Entrevista',
        'tone': 'medium',
        'title': 'Conversa ativa',
        'summary': 'Use este espaco para preparar a conversa e guardar observacoes.',
    },
    JobApplicationStatus.REJECTED: {
        'label': 'Rejeitada',
        'tone': 'low',
        'title': 'Processo encerrado',
        'summary': 'Registre aprendizados uteis antes de arquivar ou seguir adiante.',
    },
    JobApplicationStatus.OFFER: {
        'label': 'Oferta',
        'tone': 'good',
        'title': 'Decisao em aberto',
        'summary': 'Compare proposta, contexto e sinais antes de decidir.',
    },
    JobApplicationStatus.ARCHIVED: {
        'label': 'Arquivada',
        'tone': 'muted',
        'title': 'Fora do foco atual',
        'summary': 'Mantida no historico para consulta, sem exigir acao agora.',
    },
}


def get_application_stage_presentation(status_value: str) -> dict:
    return APPLICATION_STAGE_PRESENTATIONS.get(
        status_value,
        {
            'label': status_value,
            'tone': 'muted',
            'title': 'Etapa registrada',
            'summary': 'Acompanhe esta candidatura pelo status atual.',
        },
    )


def get_note_highlights(notes: str, *, limit: int = 3) -> list[str]:
    if not notes or not notes.strip():
        return []

    highlights: list[str] = []
    for raw_line in notes.splitlines():
        line = raw_line.strip().lstrip('-*').strip()
        if not line:
            continue
        highlights.append(line if len(line) <= 160 else f'{line[:157].rstrip()}...')
        if len(highlights) >= limit:
            break

    if highlights:
        return highlights

    clean = notes.strip()
    return [clean if len(clean) <= 160 else f'{clean[:157].rstrip()}...']


def build_application_next_action(application, current_match=None) -> dict:
    has_notes = bool((application.notes or '').strip())
    has_match = bool(current_match)
    match_score = current_match.get('match_score') if current_match else None
    decision_label = current_match.get('decision_label') if current_match else ''

    if application.status == JobApplicationStatus.SAVED:
        if has_match:
            return {
                'title': 'Decidir se esta vaga vira candidatura',
                'detail': (
                    f'Revise a aderencia de {match_score}/100'
                    f'{f" e a recomendacao {decision_label}" if decision_label else ""}. '
                    'Se fizer sentido, marque como aplicada.'
                ),
                'cta_label': 'Marcar como aplicada',
                'tone': 'medium',
            }
        return {
            'title': 'Avaliar aderencia antes de aplicar',
            'detail': 'Atualize o match com curriculo ou registre por que esta vaga merece entrar no pipeline.',
            'cta_label': 'Revisar contexto',
            'tone': 'warning',
        }

    if application.status == JobApplicationStatus.APPLIED:
        if has_notes:
            return {
                'title': 'Aguardar retorno e registrar atualizacao',
                'detail': 'A candidatura ja tem contexto salvo. Mantenha notas de retorno, follow-up ou mudanca de etapa.',
                'cta_label': 'Registrar atualizacao',
                'tone': 'medium',
            }
        return {
            'title': 'Registrar contexto do envio',
            'detail': 'Salve canal, contato, data combinada ou qualquer sinal que ajude no proximo follow-up.',
            'cta_label': 'Salvar notas',
            'tone': 'warning',
        }

    if application.status == JobApplicationStatus.INTERVIEW:
        if has_notes:
            return {
                'title': 'Preparar a proxima conversa',
                'detail': 'Use as notas existentes para acompanhar pauta, perguntas abertas, feedback e proximos combinados.',
                'cta_label': 'Atualizar observacoes',
                'tone': 'medium',
            }
        return {
            'title': 'Preparar conversa e registrar pauta',
            'detail': 'Anote quem participa, objetivo da entrevista, requisitos a validar e pontos fortes para reforcar.',
            'cta_label': 'Adicionar pauta',
            'tone': 'warning',
        }

    if application.status == JobApplicationStatus.OFFER:
        return {
            'title': 'Revisar decisao da oferta',
            'detail': 'Compare proposta, escopo, salario, riscos e motivos para aceitar, negociar ou recusar.',
            'cta_label': 'Registrar decisao',
            'tone': 'good',
        }

    if application.status == JobApplicationStatus.REJECTED:
        return {
            'title': 'Arquivar aprendizado e seguir',
            'detail': 'Se houver feedback, registre o motivo e o que ajustar antes de tirar esta candidatura do foco.',
            'cta_label': 'Arquivar',
            'tone': 'low',
        }

    if application.status == JobApplicationStatus.ARCHIVED:
        return {
            'title': 'Manter no historico',
            'detail': 'Nada exige acao agora. Restaure somente se a oportunidade voltar a fazer sentido.',
            'cta_label': 'Restaurar se necessario',
            'tone': 'muted',
        }

    return {
        'title': 'Revisar candidatura',
        'detail': 'Confira etapa, contexto e notas para definir a proxima acao.',
        'cta_label': 'Atualizar contexto',
        'tone': 'medium',
    }


def get_source_label(url: str) -> str:
    hostname = urlparse(url or '').netloc.lower().replace('www.', '')
    if not hostname:
        return ''
    for domain, label in SOURCE_LABELS.items():
        if hostname == domain or hostname.endswith(f'.{domain}'):
            return label
    return hostname


def serialize_preferred_match(records):
    if not records:
        return None

    preferred = next((record for record in records if getattr(record.resume, 'is_active', False)), records[0])
    reasoning = preferred.reasoning or {}
    return {
        'id': preferred.id,
        'resume_id': preferred.resume_id,
        'resume_label': preferred.resume.label or preferred.resume.original_filename,
        'match_score': preferred.match_score,
        'gaps': preferred.gaps,
        'strengths': preferred.strengths,
        'recommendation': preferred.recommendation,
        'decision_class': reasoning.get('decision_class'),
        'decision_label': reasoning.get('decision_label'),
        'evidence_signals': reasoning.get('evidence_signals', []),
        'seniority_context': reasoning.get('seniority_context', {}),
        'updated_at': preferred.updated_at,
    }


class ScrapeJobsRequestSerializer(serializers.Serializer):
    query = serializers.CharField(required=False, default="Data Scientist", max_length=255)
    location = serializers.CharField(required=False, default="Remote", max_length=255)


class BillingPlanSerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    billing_cycle = serializers.CharField(read_only=True)
    price_amount = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    currency = serializers.CharField(read_only=True)
    features = serializers.ListField(child=serializers.CharField(), read_only=True)
    highlighted = serializers.BooleanField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)


class BillingInvoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    plan_code = serializers.CharField(read_only=True)
    billing_cycle = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    currency = serializers.CharField(read_only=True)
    issued_at = serializers.DateTimeField(read_only=True)
    paid_at = serializers.DateTimeField(read_only=True, allow_null=True)
    external_reference = serializers.CharField(read_only=True)


class BillingSubscriptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True, allow_null=True)
    plan_code = serializers.CharField(read_only=True)
    plan_name = serializers.CharField(read_only=True)
    billing_cycle = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    price_amount = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    currency = serializers.CharField(read_only=True)
    auto_renew = serializers.BooleanField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)
    current_period_end = serializers.DateTimeField(read_only=True, allow_null=True)
    canceled_at = serializers.DateTimeField(read_only=True, allow_null=True)
    expires_at = serializers.DateTimeField(read_only=True, allow_null=True)
    access_until = serializers.DateTimeField(read_only=True, allow_null=True)
    is_entitled = serializers.BooleanField(read_only=True)
    access_state = serializers.CharField(read_only=True)
    features = serializers.ListField(child=serializers.CharField(), read_only=True)
    last_invoice = BillingInvoiceSerializer(read_only=True, allow_null=True)


class BillingOverviewSerializer(serializers.Serializer):
    subscription = BillingSubscriptionSerializer(read_only=True)
    plans = BillingPlanSerializer(many=True, read_only=True)


class BillingSubscribeSerializer(serializers.Serializer):
    plan_code = serializers.CharField(
        max_length=32,
        trim_whitespace=True,
        error_messages={
            "blank": "Escolha um plano para continuar.",
            "required": "Escolha um plano para continuar.",
            "max_length": "A opcao de plano informada nao e valida.",
        },
    )
    billing_cycle = serializers.CharField(
        max_length=16,
        trim_whitespace=True,
        error_messages={
            "blank": "Escolha um ciclo de cobranca para continuar.",
            "required": "Escolha um ciclo de cobranca para continuar.",
            "max_length": "O ciclo de cobranca informado nao e valido.",
        },
    )

    def validate(self, attrs):
        attrs["plan_code"] = attrs["plan_code"].lower()
        attrs["billing_cycle"] = attrs["billing_cycle"].lower()
        return attrs


class BillingCheckoutSessionSerializer(serializers.Serializer):
    plan_code = serializers.CharField(read_only=True)
    billing_cycle = serializers.CharField(read_only=True)
    checkout_session_id = serializers.CharField(read_only=True)
    checkout_url = serializers.URLField(read_only=True)
    publishable_key = serializers.CharField(read_only=True)
    price_id = serializers.CharField(read_only=True)


class ResumeUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    label = serializers.CharField(required=False, allow_blank=True, max_length=120)
    target_role = serializers.CharField(required=False, allow_blank=True, max_length=120)


RESUME_PARSE_STATUS_DETAILS = {
    'pending': 'Seu curriculo entrou na fila de processamento.',
    'processing': 'Estamos preparando seu curriculo para liberar os proximos recursos.',
    'completed': 'Curriculo pronto para analise, senioridade e aderencia com vagas.',
    'upload_too_large': 'O arquivo enviado passou do limite permitido.',
    'invalid_file': 'Nao conseguimos validar esse arquivo como um curriculo PDF ou DOCX confiavel.',
    'unsupported_file_type': 'Envie um curriculo em PDF ou DOCX.',
    'parsing_failed': 'Nao foi possivel ler esse curriculo agora. Tente enviar uma nova versao.',
    'parsing_timeout_or_budget_exceeded': 'Nao foi possivel concluir a leitura dentro do limite seguro.',
    'empty_text': 'Nao encontramos texto suficiente nesse arquivo.',
    'insufficient_text': 'O arquivo tem pouco texto para liberar uma leitura confiavel.',
    'scanned_or_image_pdf': 'O PDF parece ser uma imagem. Envie um PDF com texto selecionavel ou um DOCX.',
    'unsupported_or_unsafe_structure': 'A estrutura do arquivo nao passou nas validacoes de seguranca.',
    'quarantined_or_blocked_by_policy': 'O arquivo nao pode ser processado com seguranca.',
    'failed': 'Nao foi possivel processar esse curriculo agora.',
    'unsupported_structure': 'A estrutura do arquivo nao e suportada.',
    'document_not_resume_like': 'O arquivo nao parece um curriculo utilizavel. Envie um CV real.',
    'insufficient_resume_signals': 'Curriculo identificado com sinais limitados; analise liberada com leitura cautelosa.',
    'blocked_for_low_resume_confidence': 'Baixa confianca de curriculo; envie um CV com sinais profissionais mais claros.',
}


class ResumeSerializer(serializers.ModelSerializer):
    parse_status_detail = serializers.SerializerMethodField()

    class Meta:
        model = Resume
        fields = [
            'id',
            'label',
            'target_role',
            'original_filename',
            'parse_status',
            'parse_status_detail',
            'is_active',
            'extraction_diagnostics',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'original_filename',
            'parse_status',
            'parse_status_detail',
            'is_active',
            'created_at',
            'updated_at',
        ]

    def get_parse_status_detail(self, obj):
        return RESUME_PARSE_STATUS_DETAILS.get(
            obj.parse_status,
            'Acompanhe o status do curriculo antes de continuar.',
        )


class DashboardResumeSerializer(ResumeSerializer):
    class Meta(ResumeSerializer.Meta):
        fields = [
            field
            for field in ResumeSerializer.Meta.fields
            if field != 'extraction_diagnostics'
        ]


class ResumeAnalysisSerializer(serializers.ModelSerializer):
    resume = serializers.PrimaryKeyRelatedField(read_only=True)
    working_signals = serializers.SerializerMethodField()
    missing_signals = serializers.SerializerMethodField()
    priority_actions = serializers.SerializerMethodField()
    priority_summary = serializers.SerializerMethodField()

    class Meta:
        model = ResumeAnalysis
        fields = [
            'id',
            'resume',
            'overall_score',
            'structure_score',
            'clarity_score',
            'market_fit_score',
            'project_score',
            'strengths',
            'weaknesses',
            'recommendations',
            'raw_summary',
            'working_signals',
            'missing_signals',
            'priority_actions',
            'priority_summary',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_working_signals(self, obj):
        return obj.raw_summary.get('what_is_working', [])

    def get_missing_signals(self, obj):
        return obj.raw_summary.get('what_is_missing', [])

    def get_priority_actions(self, obj):
        return obj.raw_summary.get('priority_actions', [])

    def get_priority_summary(self, obj):
        return obj.raw_summary.get('priority_summary', {})


class SeniorityAssessmentSerializer(serializers.ModelSerializer):
    resume = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = SeniorityAssessment
        fields = [
            'id',
            'resume',
            'internship_score',
            'junior_score',
            'mid_score',
            'senior_score',
            'freelance_score',
            'recommended_track',
            'reasoning',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class JobMatchRequestSerializer(serializers.Serializer):
    resume_id = serializers.IntegerField(required=False)


class JobMatchSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    resume = serializers.PrimaryKeyRelatedField(read_only=True)
    job = serializers.PrimaryKeyRelatedField(read_only=True)
    decision_class = serializers.SerializerMethodField()
    decision_label = serializers.SerializerMethodField()
    evidence_signals = serializers.SerializerMethodField()
    seniority_context = serializers.SerializerMethodField()

    class Meta:
        model = JobMatch
        fields = [
            'id',
            'owner',
            'resume',
            'job',
            'match_score',
            'strengths',
            'gaps',
            'recommendation',
            'reasoning',
            'decision_class',
            'decision_label',
            'evidence_signals',
            'seniority_context',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_decision_class(self, obj):
        return obj.reasoning.get('decision_class')

    def get_decision_label(self, obj):
        return obj.reasoning.get('decision_label')

    def get_evidence_signals(self, obj):
        return obj.reasoning.get('evidence_signals', [])

    def get_seniority_context(self, obj):
        return obj.reasoning.get('seniority_context', {})


class DashboardSummarySerializer(serializers.Serializer):
    total_resumes = serializers.IntegerField(read_only=True)
    total_saved_jobs = serializers.IntegerField(read_only=True)
    total_applications = serializers.IntegerField(read_only=True)
    total_matches = serializers.IntegerField(read_only=True)
    active_resume_label = serializers.CharField(read_only=True, allow_null=True)
    active_resume_target_role = serializers.CharField(read_only=True, allow_null=True)
    active_resume_status = serializers.CharField(read_only=True)
    average_match_score = serializers.FloatField(read_only=True, allow_null=True)
    top_match_score = serializers.IntegerField(read_only=True, allow_null=True)
    analysis_ready = serializers.BooleanField(read_only=True)
    seniority_ready = serializers.BooleanField(read_only=True)


class DashboardPriorityActionSerializer(serializers.Serializer):
    action_type = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    detail = serializers.CharField(read_only=True)
    priority = serializers.IntegerField(read_only=True)


class DashboardProfileInsightsSerializer(serializers.Serializer):
    recommended_track = serializers.CharField(read_only=True, allow_null=True)
    competitiveness_level = serializers.CharField(read_only=True, allow_null=True)
    top_gap_area = serializers.CharField(read_only=True, allow_null=True)


class DashboardActivationStepSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    detail = serializers.CharField(read_only=True)
    completed = serializers.BooleanField(read_only=True)
    current = serializers.BooleanField(read_only=True)


class DashboardNextBestActionSerializer(serializers.Serializer):
    action_type = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    detail = serializers.CharField(read_only=True)
    cta_label = serializers.CharField(read_only=True)
    cta_href = serializers.CharField(read_only=True)


class DashboardActivationSerializer(serializers.Serializer):
    completed_steps = serializers.IntegerField(read_only=True)
    total_steps = serializers.IntegerField(read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)
    is_complete = serializers.BooleanField(read_only=True)
    headline = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    checklist = DashboardActivationStepSerializer(many=True, read_only=True)
    next_best_action = DashboardNextBestActionSerializer(read_only=True)


class DashboardBestResumeSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    label = serializers.CharField(read_only=True)
    target_role = serializers.CharField(read_only=True, allow_blank=True)
    overall_score = serializers.IntegerField(read_only=True, allow_null=True)
    recommended_track = serializers.CharField(read_only=True, allow_null=True)


class DashboardResumeReportPreviewSerializer(serializers.Serializer):
    resume_id = serializers.IntegerField(read_only=True)
    executive_summary = serializers.CharField(read_only=True)
    top_gap = serializers.CharField(read_only=True, allow_null=True)
    top_priority_action = serializers.CharField(read_only=True, allow_null=True)
    average_match_score = serializers.FloatField(read_only=True, allow_null=True)


class DashboardPremiumFeatureStateSerializer(serializers.Serializer):
    available = serializers.BooleanField(read_only=True)
    locked = serializers.BooleanField(read_only=True)
    detail = serializers.CharField(read_only=True)


class DashboardPremiumFeaturesSerializer(serializers.Serializer):
    resume_report = DashboardPremiumFeatureStateSerializer(read_only=True)
    resume_comparison = DashboardPremiumFeatureStateSerializer(read_only=True)


class DashboardJobMatchSerializer(serializers.ModelSerializer):
    job_id = serializers.IntegerField(source='job.id', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    company_name = serializers.CharField(source='job.company_name', read_only=True)

    class Meta:
        model = JobMatch
        fields = [
            'id',
            'resume',
            'job_id',
            'job_title',
            'company_name',
            'match_score',
            'recommendation',
            'strengths',
            'gaps',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class DashboardRecommendedJobSerializer(serializers.Serializer):
    match_id = serializers.IntegerField(read_only=True)
    job_id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    company_name = serializers.CharField(read_only=True)
    location = serializers.CharField(read_only=True)
    url = serializers.CharField(read_only=True)
    match_score = serializers.IntegerField(read_only=True)
    recommendation = serializers.CharField(read_only=True)


class DashboardWeeklyPrioritySerializer(serializers.Serializer):
    rank = serializers.IntegerField(read_only=True)
    source = serializers.CharField(read_only=True)
    source_id = serializers.JSONField(read_only=True, allow_null=True)
    score = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    reason = serializers.CharField(read_only=True)
    action = serializers.CharField(read_only=True)
    cta_label = serializers.CharField(read_only=True)
    cta_href = serializers.CharField(read_only=True)


class DashboardApplicationAttentionSerializer(serializers.Serializer):
    rank = serializers.IntegerField(read_only=True)
    application_id = serializers.IntegerField(read_only=True)
    job_id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    company_name = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    status_label = serializers.CharField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    days_since_update = serializers.IntegerField(read_only=True)
    reason = serializers.CharField(read_only=True)
    suggested_action = serializers.CharField(read_only=True)
    missing_context = serializers.ListField(child=serializers.CharField(), read_only=True)
    objective_criteria = serializers.ListField(child=serializers.CharField(), read_only=True)
    score = serializers.IntegerField(read_only=True)


class DashboardJobToActSerializer(DashboardRecommendedJobSerializer):
    rank = serializers.IntegerField(read_only=True)
    reason = serializers.CharField(read_only=True)
    suggested_action = serializers.CharField(read_only=True)
    score = serializers.IntegerField(read_only=True)


class DashboardResumeGapSerializer(serializers.Serializer):
    rank = serializers.IntegerField(read_only=True)
    gap_type = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    impact = serializers.CharField(read_only=True)
    guidance = serializers.CharField(read_only=True)
    score = serializers.IntegerField(read_only=True)


class DashboardWeeklyControlSerializer(serializers.Serializer):
    headline = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    main_priority = DashboardWeeklyPrioritySerializer(read_only=True, allow_null=True)
    secondary_priorities = DashboardWeeklyPrioritySerializer(many=True, read_only=True)
    applications_needing_attention = DashboardApplicationAttentionSerializer(many=True, read_only=True)
    jobs_to_act_now = DashboardJobToActSerializer(many=True, read_only=True)
    resume_gaps = DashboardResumeGapSerializer(many=True, read_only=True)


class DashboardSerializer(serializers.Serializer):
    summary = DashboardSummarySerializer(read_only=True)
    active_resume = DashboardResumeSerializer(read_only=True, allow_null=True)
    analysis = ResumeAnalysisSerializer(read_only=True, allow_null=True)
    seniority_assessment = SeniorityAssessmentSerializer(read_only=True, allow_null=True)
    top_matches = DashboardJobMatchSerializer(many=True, read_only=True)
    recommended_jobs = DashboardRecommendedJobSerializer(many=True, read_only=True)
    weekly_control = DashboardWeeklyControlSerializer(read_only=True)
    priority_actions = DashboardPriorityActionSerializer(many=True, read_only=True)
    profile_insights = DashboardProfileInsightsSerializer(read_only=True)
    activation = DashboardActivationSerializer(read_only=True)
    best_resume_summary = DashboardBestResumeSummarySerializer(read_only=True, allow_null=True)
    resume_report_preview = DashboardResumeReportPreviewSerializer(read_only=True, allow_null=True)
    comparison_available = serializers.BooleanField(read_only=True)
    premium_features = DashboardPremiumFeaturesSerializer(read_only=True)


class ResumeReportCategoryScoresSerializer(serializers.Serializer):
    overall = serializers.IntegerField(read_only=True, allow_null=True)
    structure = serializers.IntegerField(read_only=True, allow_null=True)
    clarity = serializers.IntegerField(read_only=True, allow_null=True)
    market_fit = serializers.IntegerField(read_only=True, allow_null=True)
    projects = serializers.IntegerField(read_only=True, allow_null=True)


class ResumeReportMatchSummarySerializer(serializers.Serializer):
    total_matches = serializers.IntegerField(read_only=True)
    average_match_score = serializers.FloatField(read_only=True, allow_null=True)
    best_match_score = serializers.IntegerField(read_only=True, allow_null=True)
    top_recommendation = serializers.CharField(read_only=True, allow_null=True)


class ResumeReportSerializer(serializers.Serializer):
    resume_id = serializers.IntegerField(read_only=True)
    label = serializers.CharField(read_only=True)
    target_role = serializers.CharField(read_only=True, allow_blank=True)
    parse_status = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    category_scores = ResumeReportCategoryScoresSerializer(read_only=True)
    recommended_track = serializers.CharField(read_only=True, allow_null=True)
    strengths = serializers.ListField(child=serializers.CharField(), read_only=True)
    top_gaps = serializers.ListField(child=serializers.CharField(), read_only=True)
    priority_actions = serializers.ListField(child=serializers.CharField(), read_only=True)
    recent_match_summary = ResumeReportMatchSummarySerializer(read_only=True)
    executive_summary = serializers.CharField(read_only=True)
    profile_summary = serializers.CharField(read_only=True)


class ResumeComparisonItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    label = serializers.CharField(read_only=True)
    target_role = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    parse_status = serializers.CharField(read_only=True)
    overall_score = serializers.IntegerField(read_only=True, allow_null=True)
    structure_score = serializers.IntegerField(read_only=True, allow_null=True)
    clarity_score = serializers.IntegerField(read_only=True, allow_null=True)
    market_fit_score = serializers.IntegerField(read_only=True, allow_null=True)
    project_score = serializers.IntegerField(read_only=True, allow_null=True)
    recommended_track = serializers.CharField(read_only=True, allow_null=True)
    average_match_score = serializers.FloatField(read_only=True, allow_null=True)
    best_match_score = serializers.IntegerField(read_only=True, allow_null=True)
    strength_areas = serializers.ListField(child=serializers.DictField(), read_only=True)
    weak_areas = serializers.ListField(child=serializers.DictField(), read_only=True)
    use_now_for = serializers.ListField(child=serializers.CharField(), read_only=True)
    caution_for = serializers.ListField(child=serializers.CharField(), read_only=True)
    decision_note = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ResumeComparisonAreaWinnersSerializer(serializers.Serializer):
    structure = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    clarity = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    projects = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    market_fit = ResumeComparisonItemSerializer(read_only=True, allow_null=True)


class ResumeComparisonAreaDetailSerializer(serializers.Serializer):
    key = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)
    winner = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    spread = serializers.IntegerField(read_only=True, allow_null=True)
    scores = serializers.ListField(child=serializers.DictField(), read_only=True)
    decision_note = serializers.CharField(read_only=True)


class ResumeRoutingRecommendationSerializer(serializers.Serializer):
    context_key = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    recommended_resume = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    why = serializers.CharField(read_only=True)
    when_to_use = serializers.CharField(read_only=True)
    watch_out = serializers.CharField(read_only=True)
    next_step = serializers.CharField(read_only=True)
    confidence = serializers.CharField(read_only=True)


class ResumeComparisonSerializer(serializers.Serializer):
    compared_resumes = ResumeComparisonItemSerializer(many=True, read_only=True)
    best_resume_by_score = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    best_resume_for_likely_target = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    likely_target_role = serializers.CharField(read_only=True, allow_null=True)
    comparison_summary = serializers.CharField(read_only=True)
    main_differences = serializers.ListField(child=serializers.CharField(), read_only=True)
    stronger_areas = ResumeComparisonAreaWinnersSerializer(read_only=True)
    area_comparison = ResumeComparisonAreaDetailSerializer(many=True, read_only=True)
    routing_recommendations = ResumeRoutingRecommendationSerializer(many=True, read_only=True)
    use_now_recommendation = ResumeRoutingRecommendationSerializer(read_only=True, allow_null=True)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class JobSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    source = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    application_status = serializers.SerializerMethodField()
    application_id = serializers.SerializerMethodField()
    applied_at = serializers.SerializerMethodField()
    current_match = serializers.SerializerMethodField()
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        source='tags',
        write_only=True,
        required=False,
    )

    class Meta:
        model = Job
        fields = [
            'id',
            'owner',
            'title',
            'company_name',
            'location',
            'description',
            'url',
            'source',
            'salary',
            'date_posted',
            'is_saved',
            'application_status',
            'application_id',
            'applied_at',
            'current_match',
            'tags',
            'tag_ids',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']

    def _get_saved_records(self, obj):
        records = getattr(obj, 'saved_records_for_owner', None)
        if records is not None:
            return records
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return []
        return list(obj.saved_by_users.filter(owner=user).order_by('-created_at')[:1])

    def _get_application_records(self, obj):
        records = getattr(obj, 'application_records_for_owner', None)
        if records is not None:
            return records
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return []
        return list(obj.applications.filter(owner=user).order_by('-updated_at', '-created_at')[:1])

    def _get_match_records(self, obj):
        records = getattr(obj, 'match_records_for_owner', None)
        if records is not None:
            return records
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return []
        return list(
            obj.resume_matches
            .filter(owner=user)
            .select_related('resume')
            .order_by('-updated_at', '-created_at')
        )

    def get_source(self, obj):
        return get_source_label(obj.url)

    def get_is_saved(self, obj):
        return bool(self._get_saved_records(obj))

    def get_application_status(self, obj):
        records = self._get_application_records(obj)
        return records[0].status if records else None

    def get_application_id(self, obj):
        records = self._get_application_records(obj)
        return records[0].id if records else None

    def get_applied_at(self, obj):
        records = self._get_application_records(obj)
        return records[0].applied_at if records else None

    def get_current_match(self, obj):
        records = self._get_match_records(obj)
        return serialize_preferred_match(records)


class LeadSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id',
            'owner',
            'name',
            'company',
            'email',
            'linkedin_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']


class JobApplicationSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    job = serializers.PrimaryKeyRelatedField(read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    company_name = serializers.CharField(source='job.company_name', read_only=True)
    job_location = serializers.CharField(source='job.location', read_only=True)
    job_description = serializers.CharField(source='job.description', read_only=True)
    job_url = serializers.URLField(source='job.url', read_only=True)
    job_date_posted = serializers.DateField(source='job.date_posted', read_only=True)
    job_source = serializers.SerializerMethodField()
    job_is_saved = serializers.SerializerMethodField()
    current_match = serializers.SerializerMethodField()
    stage_presentation = serializers.SerializerMethodField()
    next_action = serializers.SerializerMethodField()
    recorded_context = serializers.SerializerMethodField()
    missing_context = serializers.SerializerMethodField()
    notes_highlights = serializers.SerializerMethodField()

    class Meta:
        model = JobApplication
        fields = [
            'id',
            'owner',
            'job',
            'job_title',
            'company_name',
            'job_location',
            'job_description',
            'job_url',
            'job_date_posted',
            'job_source',
            'job_is_saved',
            'status',
            'notes',
            'applied_at',
            'current_match',
            'stage_presentation',
            'next_action',
            'recorded_context',
            'missing_context',
            'notes_highlights',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']

    def _get_saved_records(self, obj):
        records = getattr(obj.job, 'saved_records_for_owner', None)
        if records is not None:
            return records
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return []
        return list(obj.job.saved_by_users.filter(owner=user).order_by('-created_at')[:1])

    def _get_match_records(self, obj):
        records = getattr(obj.job, 'match_records_for_owner', None)
        if records is not None:
            return records
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return []
        return list(
            obj.job.resume_matches
            .filter(owner=user)
            .select_related('resume')
            .order_by('-updated_at', '-created_at')
        )

    def get_job_source(self, obj):
        return get_source_label(obj.job.url)

    def get_job_is_saved(self, obj):
        return bool(self._get_saved_records(obj))

    def get_current_match(self, obj):
        return serialize_preferred_match(self._get_match_records(obj))

    def get_stage_presentation(self, obj):
        return get_application_stage_presentation(obj.status)

    def get_next_action(self, obj):
        return build_application_next_action(
            obj,
            serialize_preferred_match(self._get_match_records(obj)),
        )

    def get_recorded_context(self, obj):
        context = [
            f"Etapa atual: {get_application_stage_presentation(obj.status)['label']}",
        ]

        if obj.applied_at:
            context.append('Data de aplicacao registrada')

        source = get_source_label(obj.job.url)
        if source:
            context.append(f'Fonte da vaga: {source}')

        if self.get_job_is_saved(obj):
            context.append('Vaga salva no workspace')

        current_match = serialize_preferred_match(self._get_match_records(obj))
        if current_match:
            context.append(
                f"Match: {current_match['match_score']}/100 com {current_match['resume_label']}"
            )
            if current_match.get('decision_label'):
                context.append(f"Recomendacao: {current_match['decision_label']}")

        if (obj.notes or '').strip():
            context.append('Notas de acompanhamento registradas')

        return context

    def get_missing_context(self, obj):
        missing = []
        current_match = serialize_preferred_match(self._get_match_records(obj))

        if not current_match:
            missing.append('Match com curriculo')
        elif not current_match.get('recommendation'):
            missing.append('Recomendacao de aderencia')

        if not (obj.notes or '').strip():
            if obj.status == JobApplicationStatus.INTERVIEW:
                missing.append('Pauta ou observacoes da entrevista')
            elif obj.status == JobApplicationStatus.OFFER:
                missing.append('Criterios para decidir a oferta')
            elif obj.status == JobApplicationStatus.REJECTED:
                missing.append('Motivo ou aprendizado da rejeicao')
            else:
                missing.append('Notas de acompanhamento')

        if not get_source_label(obj.job.url):
            missing.append('Fonte da vaga')

        if not obj.job.url:
            missing.append('Link original da vaga')

        if obj.status != JobApplicationStatus.SAVED and not obj.applied_at:
            missing.append('Data de aplicacao')

        return missing

    def get_notes_highlights(self, obj):
        return get_note_highlights(obj.notes)


class JobApplicationWorkflowSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=JobApplicationStatus.choices,
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class SavedJobSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    job = JobSerializer(read_only=True)

    class Meta:
        model = SavedJob
        fields = [
            'id',
            'owner',
            'job',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
