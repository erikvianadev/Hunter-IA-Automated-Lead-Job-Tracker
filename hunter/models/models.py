from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from ..choices import JobApplicationStatus


class BaseModel(models.Model):
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        abstract = True


class Tag(BaseModel):
    name = models.CharField(_('name'), max_length=120, unique=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name'], name='tag_name_idx'),
        ]
        verbose_name = _('tag')
        verbose_name_plural = _('tags')

    def __str__(self) -> str:
        return self.name


class Job(BaseModel):
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='jobs',
        verbose_name=_('owner'),
    )
    title = models.CharField(_('title'), max_length=255)
    company_name = models.CharField(_('company name'), max_length=255)
    location = models.CharField(_('location'), max_length=255)
    description = models.TextField(_('description'))
    url = models.URLField(_('url'), blank=True)
    salary = models.DecimalField(
        _('salary'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    date_posted = models.DateField(_('date posted'), null=True, blank=True)
    tags = models.ManyToManyField(
        Tag,
        verbose_name=_('tags'),
        blank=True,
        related_name='jobs',
    )

    class Meta:
        ordering = ['-created_at', 'title']
        indexes = [
            models.Index(fields=['owner', 'created_at'], name='job_owner_created_at_idx'),
        ]
        verbose_name = _('job')
        verbose_name_plural = _('jobs')

    def __str__(self) -> str:
        return f'{self.title} @ {self.company_name}'


class Lead(BaseModel):
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='leads',
        verbose_name=_('owner'),
    )
    name = models.CharField(_('name'), max_length=255)
    company = models.CharField(_('company'), max_length=255)
    email = models.EmailField(_('email'), blank=True, null=True)
    linkedin_url = models.URLField(_('linkedin url'), blank=True, null=True)

    class Meta:
        ordering = ['-created_at', 'name']
        indexes = [
            models.Index(fields=['owner', 'created_at'], name='lead_owner_created_at_idx'),
        ]
        verbose_name = _('lead')
        verbose_name_plural = _('leads')

    def __str__(self) -> str:
        return f'{self.name} — {self.company}'


class JobApplication(BaseModel):
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='job_applications',
        verbose_name=_('owner'),
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name=_('job'),
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=JobApplicationStatus.choices,
        default=JobApplicationStatus.NOT_APPLIED,
    )
    notes = models.TextField(_('notes'), blank=True)
    applied_at = models.DateTimeField(_('applied at'), null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'created_at'], name='app_owner_created_idx'),
            models.Index(fields=['job'], name='application_job_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['owner', 'job'], name='unique_owner_job'),
        ]
        verbose_name = _('job application')
        verbose_name_plural = _('job applications')

    def __str__(self) -> str:
        return f'{self.job} — {self.get_status_display()}'
