from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .choices import JobApplicationStatus
from .filters import JobApplicationFilter, JobFilter
from .models.models import Job, JobApplication, JobMatch, Lead, Resume, SavedJob, Tag
from .pagination import HunterPagination
from .serializers import (
    BillingOverviewSerializer,
    BillingPlanSerializer,
    BillingCheckoutSessionSerializer,
    BillingSubscribeSerializer,
    BillingSubscriptionSerializer,
    DashboardSerializer,
    JobApplicationSerializer,
    JobApplicationWorkflowSerializer,
    JobMatchRequestSerializer,
    JobMatchSerializer,
    JobSerializer,
    LeadSerializer,
    ResumeAnalysisSerializer,
    ResumeComparisonSerializer,
    ResumeReportSerializer,
    ResumeSerializer,
    ResumeUploadSerializer,
    SavedJobSerializer,
    SeniorityAssessmentSerializer,
    TagSerializer,
)
from .services import (
    BillingAccessError,
    BillingError,
    BillingPortalService,
    BillingService,
    DashboardService,
    JobMatchingError,
    JobMatchingService,
    JobWorkflowError,
    JobWorkflowService,
    ResumeAnalysisError,
    ResumeAnalysisService,
    ResumeIngestionService,
    ResumeProfileService,
    ResumeReportService,
    ResumeValidationError,
    SeniorityAssessmentService,
)


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HunterPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return Tag.objects.all()


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HunterPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JobFilter
    search_fields = ['title', 'company_name', 'location', 'description']
    ordering_fields = ['title', 'company_name', 'created_at', 'updated_at', 'date_posted']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            Job.objects
            .filter(owner=self.request.user)
            .select_related('owner')
            .prefetch_related(
                'tags',
                Prefetch(
                    'saved_by_users',
                    queryset=SavedJob.objects.filter(owner=self.request.user).order_by('-created_at'),
                    to_attr='saved_records_for_owner',
                ),
                Prefetch(
                    'applications',
                    queryset=JobApplication.objects.filter(owner=self.request.user).order_by('-updated_at', '-created_at'),
                    to_attr='application_records_for_owner',
                ),
                Prefetch(
                    'resume_matches',
                    queryset=JobMatch.objects.filter(owner=self.request.user).select_related('resume').order_by('-updated_at', '-created_at'),
                    to_attr='match_records_for_owner',
                ),
            )
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post', 'delete'], url_path='save')
    def save(self, request, pk=None):
        job = self.get_object()
        service = JobWorkflowService()

        if request.method == 'DELETE':
            service.unsave_job(owner=request.user, job=job)
            return Response(status=status.HTTP_204_NO_CONTENT)

        saved_job, created = service.save_job(owner=request.user, job=job)
        serializer = SavedJobSerializer(
            saved_job,
            context=self.get_serializer_context(),
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='apply')
    def apply(self, request, pk=None):
        job = self.get_object()
        serializer = JobApplicationWorkflowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            application, created = JobWorkflowService().apply_to_job(
                owner=request.user,
                job=job,
                status=serializer.validated_data.get('status', JobApplicationStatus.APPLIED),
                notes=serializer.validated_data.get('notes'),
            )
        except JobWorkflowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = JobApplicationSerializer(
            application,
            context=self.get_serializer_context(),
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='match')
    def match(self, request, pk=None):
        job = self.get_object()
        serializer = JobMatchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        resume_id = serializer.validated_data.get('resume_id')
        resume_queryset = Resume.objects.filter(owner=request.user)
        resume = (
            resume_queryset.filter(id=resume_id).first()
            if resume_id is not None
            else resume_queryset.filter(is_active=True).order_by('-created_at').first()
        )
        if resume is None:
            return Response(
                {"detail": "A valid owned resume is required for matching."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            match = JobMatchingService().match(
                owner=request.user,
                resume=resume,
                job=job,
            )
        except (JobMatchingError, ResumeAnalysisError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            JobMatchSerializer(match, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HunterPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'company']
    ordering_fields = ['name', 'company', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            Lead.objects
            .filter(owner=self.request.user)
            .select_related('owner')
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class JobApplicationViewSet(
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HunterPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = JobApplicationFilter
    search_fields = ['job__title', 'job__company_name', 'job__description', 'notes']
    ordering_fields = ['status', 'job', 'applied_at', 'created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        return (
            JobApplication.objects
            .filter(owner=self.request.user)
            .select_related('owner', 'job')
            .prefetch_related(
                Prefetch(
                    'job__saved_by_users',
                    queryset=SavedJob.objects.filter(owner=self.request.user).order_by('-created_at'),
                    to_attr='saved_records_for_owner',
                ),
                Prefetch(
                    'job__resume_matches',
                    queryset=JobMatch.objects.filter(owner=self.request.user).select_related('resume').order_by('-updated_at', '-created_at'),
                    to_attr='match_records_for_owner',
                ),
            )
        )

    def get_serializer_class(self):
        if self.action in {'partial_update', 'update'}:
            return JobApplicationWorkflowSerializer
        return JobApplicationSerializer

    def update(self, request, *args, **kwargs):
        return self._update_application(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self._update_application(request, *args, **kwargs)

    def _update_application(self, request, *args, **kwargs):
        application = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            partial=kwargs.get('partial', request.method == 'PATCH'),
        )
        serializer.is_valid(raise_exception=True)

        updated_application = JobWorkflowService().update_application(
            application=application,
            status=serializer.validated_data.get('status'),
            notes=serializer.validated_data.get('notes'),
        )
        response_serializer = JobApplicationSerializer(
            updated_application,
            context=self.get_serializer_context(),
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ResumeViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    pagination_class = HunterPagination
    ordering = ['-created_at']

    def get_queryset(self):
        return Resume.objects.filter(owner=self.request.user).select_related('owner')

    def get_serializer_class(self):
        if self.action == 'create':
            return ResumeUploadSerializer
        return ResumeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            resume = ResumeIngestionService().ingest_with_profile(
                owner=request.user,
                uploaded_file=serializer.validated_data['file'],
                label=serializer.validated_data.get('label'),
                target_role=serializer.validated_data.get('target_role', ''),
            )
        except ResumeValidationError as exc:
            raise serializers.ValidationError({"file": [str(exc)]}) from exc

        response_serializer = ResumeSerializer(
            resume,
            context=self.get_serializer_context(),
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        payload = DashboardService().build(owner=request.user)
        serializer = DashboardSerializer(
            payload,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='compare')
    def compare(self, request):
        try:
            BillingService().require_feature(
                owner=request.user,
                feature_code=BillingService.FEATURE_RESUME_COMPARISON,
            )
        except BillingAccessError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        raw_ids = (request.query_params.get('ids') or "").strip()
        resume_ids: list[int] | None = None
        if raw_ids:
            try:
                resume_ids = [int(value.strip()) for value in raw_ids.split(',') if value.strip()]
            except ValueError as exc:
                raise serializers.ValidationError({"ids": ["Resume ids must be integers."]}) from exc

        payload = ResumeProfileService().compare(
            owner=request.user,
            resume_ids=resume_ids,
        )
        serializer = ResumeComparisonSerializer(
            payload,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='report')
    def report(self, request, pk=None):
        resume = self.get_object()
        try:
            BillingService().require_feature(
                owner=request.user,
                feature_code=BillingService.FEATURE_PREMIUM_REPORTS,
            )
        except BillingAccessError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        payload = ResumeReportService().build(resume=resume)
        serializer = ResumeReportSerializer(
            payload,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        resume = self.get_object()
        activated_resume = ResumeProfileService().activate(
            owner=request.user,
            resume=resume,
        )
        serializer = ResumeSerializer(
            activated_resume,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='analyze')
    def analyze(self, request, pk=None):
        resume = self.get_object()
        try:
            analysis = ResumeAnalysisService().analyze(resume=resume)
        except ResumeAnalysisError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ResumeAnalysisSerializer(
            analysis,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='analysis')
    def analysis(self, request, pk=None):
        resume = self.get_object()
        if not hasattr(resume, 'analysis'):
            return Response(
                {"detail": "Resume analysis does not exist yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ResumeAnalysisSerializer(
            resume.analysis,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='assess-seniority')
    def assess_seniority(self, request, pk=None):
        resume = self.get_object()
        try:
            assessment = SeniorityAssessmentService().assess(resume=resume)
        except ResumeAnalysisError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SeniorityAssessmentSerializer(
            assessment,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='seniority')
    def seniority(self, request, pk=None):
        resume = self.get_object()
        if not hasattr(resume, 'seniority_assessment'):
            return Response(
                {"detail": "Resume seniority assessment does not exist yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SeniorityAssessmentSerializer(
            resume.seniority_assessment,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class JobMatchViewSet(ListModelMixin, RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = JobMatchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HunterPagination
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            JobMatch.objects
            .filter(owner=self.request.user)
            .select_related('owner', 'resume', 'job')
        )


class SavedJobViewSet(ListModelMixin, viewsets.GenericViewSet):
    serializer_class = SavedJobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HunterPagination
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            SavedJob.objects
            .filter(owner=self.request.user)
            .select_related('owner', 'job')
            .prefetch_related('job__tags')
        )


class BillingViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='plans')
    def plans(self, request):
        payload = BillingService().list_plans(owner=request.user)
        serializer = BillingPlanSerializer(payload, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='subscription')
    def subscription(self, request):
        payload = BillingPortalService().build_overview(owner=request.user)
        serializer = BillingOverviewSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='subscribe')
    def subscribe(self, request):
        serializer = BillingSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = BillingService().subscribe(
                owner=request.user,
                plan_code=serializer.validated_data['plan_code'],
                billing_cycle=serializer.validated_data['billing_cycle'],
            )
        except BillingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = BillingCheckoutSessionSerializer(payload)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='cancel')
    def cancel(self, request):
        try:
            payload = BillingService().cancel(owner=request.user)
        except BillingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = BillingSubscriptionSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        signature_header = request.headers.get('Stripe-Signature', '')
        try:
            BillingService().handle_webhook_event(
                payload=request.body,
                signature_header=signature_header,
            )
        except BillingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"received": True}, status=status.HTTP_200_OK)
