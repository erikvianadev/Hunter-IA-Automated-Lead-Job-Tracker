from django.db import models
from django.utils.translation import gettext_lazy as _


class JobApplicationStatus(models.TextChoices):
    SAVED = 'saved', _('Saved')
    APPLIED = 'applied', _('Applied')
    INTERVIEW = 'interview', _('Interview')
    REJECTED = 'rejected', _('Rejected')
    OFFER = 'offer', _('Offer')
    ARCHIVED = 'archived', _('Archived')


class ResumeParseStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    PROCESSING = 'processing', _('Processing')
    COMPLETED = 'completed', _('Completed')
    FAILED = 'failed', _('Failed')
    EMPTY_TEXT = 'empty_text', _('Empty Text')
    UNSUPPORTED_STRUCTURE = 'unsupported_structure', _('Unsupported Structure')


class BillingCycle(models.TextChoices):
    FREE = 'free', _('Free')
    MONTHLY = 'monthly', _('Monthly')
    YEARLY = 'yearly', _('Yearly')


class BillingSubscriptionStatus(models.TextChoices):
    ACTIVE = 'active', _('Active')
    CANCELED = 'canceled', _('Canceled')
    EXPIRED = 'expired', _('Expired')


class BillingInvoiceStatus(models.TextChoices):
    PAID = 'paid', _('Paid')
    VOID = 'void', _('Void')
