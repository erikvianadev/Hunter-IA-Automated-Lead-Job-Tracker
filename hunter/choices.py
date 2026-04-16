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
    UPLOAD_TOO_LARGE = 'upload_too_large', _('Upload Too Large')
    INVALID_FILE = 'invalid_file', _('Invalid File')
    UNSUPPORTED_FILE_TYPE = 'unsupported_file_type', _('Unsupported File Type')
    PARSING_FAILED = 'parsing_failed', _('Parsing Failed')
    PARSING_TIMEOUT_OR_BUDGET_EXCEEDED = (
        'parsing_timeout_or_budget_exceeded',
        _('Parsing Timeout Or Budget Exceeded'),
    )
    EMPTY_TEXT = 'empty_text', _('Empty Text')
    INSUFFICIENT_TEXT = 'insufficient_text', _('Insufficient Text')
    DOCUMENT_NOT_RESUME_LIKE = (
        'document_not_resume_like',
        _('Document Not Resume Like'),
    )
    INSUFFICIENT_RESUME_SIGNALS = (
        'insufficient_resume_signals',
        _('Insufficient Resume Signals'),
    )
    BLOCKED_FOR_LOW_RESUME_CONFIDENCE = (
        'blocked_for_low_resume_confidence',
        _('Blocked For Low Resume Confidence'),
    )
    SCANNED_OR_IMAGE_PDF = 'scanned_or_image_pdf', _('Scanned Or Image PDF')
    UNSUPPORTED_OR_UNSAFE_STRUCTURE = (
        'unsupported_or_unsafe_structure',
        _('Unsupported Or Unsafe Structure'),
    )
    QUARANTINED_OR_BLOCKED_BY_POLICY = (
        'quarantined_or_blocked_by_policy',
        _('Quarantined Or Blocked By Policy'),
    )
    FAILED = 'failed', _('Failed')
    UNSUPPORTED_STRUCTURE = 'unsupported_structure', _('Unsupported Structure')


class ProductEventCategory(models.TextChoices):
    JOURNEY_MILESTONE = 'journey_milestone', _('Journey milestone')
    JOURNEY_FAILURE = 'journey_failure', _('Journey failure')
    TECHNICAL_FAILURE = 'technical_failure', _('Technical failure')


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
