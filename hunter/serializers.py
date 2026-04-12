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
            'salary',
            'date_posted',
            'tags',
            'tag_ids',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']


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
