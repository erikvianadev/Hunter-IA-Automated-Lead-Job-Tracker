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
    features = serializers.ListField(child=serializers.CharField(), read_only=True)
    last_invoice = BillingInvoiceSerializer(read_only=True, allow_null=True)


class BillingOverviewSerializer(serializers.Serializer):
    subscription = BillingSubscriptionSerializer(read_only=True)
    plans = BillingPlanSerializer(many=True, read_only=True)


class BillingSubscribeSerializer(serializers.Serializer):
    plan_code = serializers.CharField(max_length=32)
    billing_cycle = serializers.CharField(max_length=16)


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


class ResumeSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Resume
        fields = [
            'id',
            'owner',
            'file',
            'file_url',
            'label',
            'target_role',
            'original_filename',
            'extracted_text',
            'extraction_diagnostics',
            'parse_status',
            'content_type',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'owner',
            'original_filename',
            'extracted_text',
            'extraction_diagnostics',
            'parse_status',
            'content_type',
            'is_active',
            'created_at',
            'updated_at',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not obj.file:
            return None
        if request is None:
            return obj.file.url
        return request.build_absolute_uri(obj.file.url)


class ResumeAnalysisSerializer(serializers.ModelSerializer):
    resume = serializers.PrimaryKeyRelatedField(read_only=True)

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
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


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
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


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


class DashboardSerializer(serializers.Serializer):
    summary = DashboardSummarySerializer(read_only=True)
    active_resume = ResumeSerializer(read_only=True, allow_null=True)
    analysis = ResumeAnalysisSerializer(read_only=True, allow_null=True)
    seniority_assessment = SeniorityAssessmentSerializer(read_only=True, allow_null=True)
    top_matches = DashboardJobMatchSerializer(many=True, read_only=True)
    recommended_jobs = DashboardRecommendedJobSerializer(many=True, read_only=True)
    priority_actions = DashboardPriorityActionSerializer(many=True, read_only=True)
    profile_insights = DashboardProfileInsightsSerializer(read_only=True)
    best_resume_summary = DashboardBestResumeSummarySerializer(read_only=True, allow_null=True)
    resume_report_preview = DashboardResumeReportPreviewSerializer(read_only=True, allow_null=True)
    comparison_available = serializers.BooleanField(read_only=True)


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
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ResumeComparisonAreaWinnersSerializer(serializers.Serializer):
    structure = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    clarity = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    projects = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    market_fit = ResumeComparisonItemSerializer(read_only=True, allow_null=True)


class ResumeComparisonSerializer(serializers.Serializer):
    compared_resumes = ResumeComparisonItemSerializer(many=True, read_only=True)
    best_resume_by_score = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    best_resume_for_likely_target = ResumeComparisonItemSerializer(read_only=True, allow_null=True)
    likely_target_role = serializers.CharField(read_only=True, allow_null=True)
    comparison_summary = serializers.CharField(read_only=True)
    main_differences = serializers.ListField(child=serializers.CharField(), read_only=True)
    stronger_areas = ResumeComparisonAreaWinnersSerializer(read_only=True)


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
        hostname = urlparse(obj.url or '').netloc.lower().replace('www.', '')
        if not hostname:
            return ''
        for domain, label in self.SOURCE_LABELS.items():
            if hostname == domain or hostname.endswith(f'.{domain}'):
                return label
        return hostname

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
        if not records:
            return None

        preferred = next((record for record in records if getattr(record.resume, 'is_active', False)), records[0])
        return {
            'id': preferred.id,
            'resume_id': preferred.resume_id,
            'resume_label': preferred.resume.label or preferred.resume.original_filename,
            'match_score': preferred.match_score,
            'gaps': preferred.gaps,
            'strengths': preferred.strengths,
            'recommendation': preferred.recommendation,
            'updated_at': preferred.updated_at,
        }


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

    class Meta:
        model = JobApplication
        fields = [
            'id',
            'owner',
            'job',
            'job_title',
            'company_name',
            'status',
            'notes',
            'applied_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']


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
