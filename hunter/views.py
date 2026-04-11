from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import JobApplicationFilter, JobFilter
from .models.models import Job, JobApplication, Lead, Resume, Tag
from .pagination import HunterPagination
from .serializers import (
    JobApplicationSerializer,
    JobSerializer,
    LeadSerializer,
    ResumeAnalysisSerializer,
    ResumeSerializer,
    ResumeUploadSerializer,
    TagSerializer,
)
from .services import (
    ResumeAnalysisError,
    ResumeAnalysisService,
    ResumeIngestionService,
    ResumeValidationError,
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
    search_fields = ['title', 'company_name']
    ordering_fields = ['title', 'company_name', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            Job.objects
            .filter(owner=self.request.user)
            .select_related('owner')
            .prefetch_related('tags')
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


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


class JobApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HunterPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = JobApplicationFilter
    ordering_fields = ['status', 'applied_at', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            JobApplication.objects
            .filter(owner=self.request.user)
            .select_related('owner', 'job')
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


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
            resume = ResumeIngestionService().ingest(
                owner=request.user,
                uploaded_file=serializer.validated_data['file'],
            )
        except ResumeValidationError as exc:
            raise serializers.ValidationError({"file": [str(exc)]}) from exc

        response_serializer = ResumeSerializer(
            resume,
            context=self.get_serializer_context(),
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='analyze')
    def analyze(self, request, pk=None):
        resume = self.get_object()
        try:
            analysis = ResumeAnalysisService().analyze(resume=resume)
        except ResumeAnalysisError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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
                {
                    "detail": "Resume analysis does not exist yet.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ResumeAnalysisSerializer(
            resume.analysis,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
