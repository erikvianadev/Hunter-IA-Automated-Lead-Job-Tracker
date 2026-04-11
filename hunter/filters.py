import django_filters

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

    class Meta:
        model = Job
        fields = ['company_name', 'tags']


class JobApplicationFilter(django_filters.FilterSet):
    job = django_filters.NumberFilter(field_name='job_id')

    class Meta:
        model = JobApplication
        fields = ['status', 'job']
