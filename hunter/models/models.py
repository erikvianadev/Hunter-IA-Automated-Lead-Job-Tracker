from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from ..choices import (
    BillingCycle,
    BillingInvoiceStatus,
    BillingSubscriptionStatus,
    JobApplicationStatus,
    ResumeParseStatus,
)


def resume_upload_to(instance, filename: str) -> str:
    return f"resumes/user_{instance.owner_id}/{filename}"


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
        default=JobApplicationStatus.SAVED,
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

class SavedJob(BaseModel):
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='saved_jobs',
        verbose_name=_('owner'),
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='saved_by_users',
        verbose_name=_('job'),
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'created_at'], name='savedjob_owner_created_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['owner', 'job'], name='unique_owner_saved_job'),
        ]
        verbose_name = _('saved job')
        verbose_name_plural = _('saved jobs')

    def __str__(self) -> str:
        return f'{self.owner_id} saved {self.job}'


class Resume(BaseModel):
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='resumes',
        verbose_name=_('owner'),
    )
    file = models.FileField(_('file'), upload_to=resume_upload_to)
    label = models.CharField(_('label'), max_length=120, blank=True, default="")
    target_role = models.CharField(_('target role'), max_length=120, blank=True, default="")
    original_filename = models.CharField(_('original filename'), max_length=255)
    extracted_text = models.TextField(_('extracted text'), blank=True)
    parse_status = models.CharField(
        _('parse status'),
        max_length=32,
        choices=ResumeParseStatus.choices,
        default=ResumeParseStatus.PENDING,
    )
    content_type = models.CharField(_('content type'), max_length=100)
    is_active = models.BooleanField(_('is active'), default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['owner', 'is_active', 'created_at'],
                name='resume_own_act_idx',
            ),
        ]
        verbose_name = _('resume')
        verbose_name_plural = _('resumes')

    def __str__(self) -> str:
        return self.original_filename

    def delete(self, using=None, keep_parents=False):
        storage = self.file.storage if self.file else None
        file_name = self.file.name if self.file else ""
        super().delete(using=using, keep_parents=keep_parents)
        if storage and file_name:
            storage.delete(file_name)


class ResumeAnalysis(BaseModel):
    resume = models.OneToOneField(
        Resume,
        on_delete=models.CASCADE,
        related_name='analysis',
        verbose_name=_('resume'),
    )
    overall_score = models.PositiveSmallIntegerField(_('overall score'), default=0)
    structure_score = models.PositiveSmallIntegerField(_('structure score'), default=0)
    clarity_score = models.PositiveSmallIntegerField(_('clarity score'), default=0)
    market_fit_score = models.PositiveSmallIntegerField(_('market fit score'), default=0)
    project_score = models.PositiveSmallIntegerField(_('project score'), default=0)
    strengths = models.JSONField(_('strengths'), default=list, blank=True)
    weaknesses = models.JSONField(_('weaknesses'), default=list, blank=True)
    recommendations = models.JSONField(_('recommendations'), default=list, blank=True)
    raw_summary = models.JSONField(_('raw summary'), default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('resume analysis')
        verbose_name_plural = _('resume analyses')

    def __str__(self) -> str:
        return f'Analysis for {self.resume.original_filename}'


class SeniorityAssessment(BaseModel):
    resume = models.OneToOneField(
        Resume,
        on_delete=models.CASCADE,
        related_name='seniority_assessment',
        verbose_name=_('resume'),
    )
    internship_score = models.PositiveSmallIntegerField(_('internship score'), default=0)
    junior_score = models.PositiveSmallIntegerField(_('junior score'), default=0)
    mid_score = models.PositiveSmallIntegerField(_('mid score'), default=0)
    senior_score = models.PositiveSmallIntegerField(_('senior score'), default=0)
    freelance_score = models.PositiveSmallIntegerField(_('freelance score'), default=0)
    recommended_track = models.CharField(_('recommended track'), max_length=32)
    reasoning = models.JSONField(_('reasoning'), default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('seniority assessment')
        verbose_name_plural = _('seniority assessments')

    def __str__(self) -> str:
        return f'Seniority for {self.resume.original_filename}'


class JobMatch(BaseModel):
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='job_matches',
        verbose_name=_('owner'),
    )
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name='job_matches',
        verbose_name=_('resume'),
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='resume_matches',
        verbose_name=_('job'),
    )
    match_score = models.PositiveSmallIntegerField(_('match score'), default=0)
    strengths = models.JSONField(_('strengths'), default=list, blank=True)
    gaps = models.JSONField(_('gaps'), default=list, blank=True)
    recommendation = models.CharField(_('recommendation'), max_length=255)
    reasoning = models.JSONField(_('reasoning'), default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'resume', 'job'],
                name='uniq_owner_resume_job_match',
            ),
        ]
        indexes = [
            models.Index(fields=['owner', 'created_at'], name='jobmatch_owner_created_idx'),
        ]
        verbose_name = _('job match')
        verbose_name_plural = _('job matches')

    def __str__(self) -> str:
        return f'{self.resume.original_filename} -> {self.job.title}'


class BillingSubscription(BaseModel):
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='billing_subscriptions',
        verbose_name=_('owner'),
    )
    plan_code = models.CharField(_('plan code'), max_length=32, default='free')
    billing_cycle = models.CharField(
        _('billing cycle'),
        max_length=16,
        choices=BillingCycle.choices,
        default=BillingCycle.FREE,
    )
    status = models.CharField(
        _('status'),
        max_length=16,
        choices=BillingSubscriptionStatus.choices,
        default=BillingSubscriptionStatus.ACTIVE,
    )
    price_amount = models.DecimalField(
        _('price amount'),
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    currency = models.CharField(_('currency'), max_length=8, default='BRL')
    auto_renew = models.BooleanField(_('auto renew'), default=True)
    started_at = models.DateTimeField(_('started at'))
    current_period_end = models.DateTimeField(_('current period end'), null=True, blank=True)
    canceled_at = models.DateTimeField(_('canceled at'), null=True, blank=True)
    expires_at = models.DateTimeField(_('expires at'), null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status', 'created_at'], name='billsub_owner_status_idx'),
        ]
        verbose_name = _('billing subscription')
        verbose_name_plural = _('billing subscriptions')

    def __str__(self) -> str:
        return f'{self.owner_id} {self.plan_code} ({self.billing_cycle})'


class BillingInvoice(BaseModel):
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='billing_invoices',
        verbose_name=_('owner'),
    )
    subscription = models.ForeignKey(
        BillingSubscription,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_('subscription'),
    )
    plan_code = models.CharField(_('plan code'), max_length=32, default='free')
    billing_cycle = models.CharField(
        _('billing cycle'),
        max_length=16,
        choices=BillingCycle.choices,
        default=BillingCycle.FREE,
    )
    status = models.CharField(
        _('status'),
        max_length=16,
        choices=BillingInvoiceStatus.choices,
        default=BillingInvoiceStatus.PAID,
    )
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(_('currency'), max_length=8, default='BRL')
    issued_at = models.DateTimeField(_('issued at'))
    paid_at = models.DateTimeField(_('paid at'), null=True, blank=True)
    external_reference = models.CharField(
        _('external reference'),
        max_length=64,
        blank=True,
        default='',
    )

    class Meta:
        ordering = ['-issued_at', '-created_at']
        indexes = [
            models.Index(fields=['owner', 'issued_at'], name='invoice_owner_issued_idx'),
        ]
        verbose_name = _('billing invoice')
        verbose_name_plural = _('billing invoices')

    def __str__(self) -> str:
        return f'{self.owner_id} {self.plan_code} invoice {self.amount}'
