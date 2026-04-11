from django.db import models
from django.utils.translation import gettext_lazy as _


class JobApplicationStatus(models.TextChoices):
    APPLIED = 'APPLIED', _('Applied')
    NOT_APPLIED = 'NOT_APPLIED', _('Not Applied')
    INTERVIEW = 'INTERVIEW', _('Interview')
    OFFER = 'OFFER', _('Offer')
    REJECTED = 'REJECTED', _('Rejected')


class ResumeParseStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    PROCESSING = 'processing', _('Processing')
    COMPLETED = 'completed', _('Completed')
    FAILED = 'failed', _('Failed')
