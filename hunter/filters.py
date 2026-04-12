import django_filters

from .choices import JobApplicationStatus
from .models.models import Job, JobApplication, Tag


class JobFilter(django_filters.FilterSet):
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name='tags',
        queryset=Tag.objects.all(),
    )
    company_name = django_filters.CharFilter(
        field_name='company_name',
        lookup_expr='icontains',
    )
    location = django_filters.CharFilter(
        field_name='location',
        lookup_expr='icontains',
    )
    status = django_filters.CharFilter(method='filter_status')

    def filter_status(self, queryset, name, value):
        normalized = (value or '').strip().lower()
        if not normalized or normalized == 'all':
            return queryset

        request = getattr(self, 'request', None)
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return queryset

        if normalized == 'saved':
            return queryset.filter(saved_by_users__owner=user).distinct()

        if normalized == 'applied':
            return (
                queryset.filter(applications__owner=user)
                .exclude(applications__status=JobApplicationStatus.SAVED)
                .distinct()
            )

        return queryset

    class Meta:
        model = Job
        fields = ['company_name', 'location', 'status', 'tags']


class JobApplicationFilter(django_filters.FilterSet):
    job = django_filters.NumberFilter(field_name='job_id')
    company_name = django_filters.CharFilter(
        field_name='job__company_name',
        lookup_expr='icontains',
    )

    class Meta:
        model = JobApplication
        fields = ['status', 'job', 'company_name']
