from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from .filters import JobApplicationFilter, JobFilter
from .models.models import Job, JobApplication, Lead, Tag
from .pagination import HunterPagination
from .serializers import (
    JobApplicationSerializer,
    JobSerializer,
    LeadSerializer,
    TagSerializer,
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
