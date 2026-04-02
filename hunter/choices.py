from django.db import models
from django.utils.translation import gettext_lazy as _


class JobApplicationStatus(models.TextChoices):
    APPLIED = 'APPLIED', _('Applied')
    NOT_APPLIED = 'NOT_APPLIED', _('Not Applied')
    INTERVIEW = 'INTERVIEW', _('Interview')
    OFFER = 'OFFER', _('Offer')
    REJECTED = 'REJECTED', _('Rejected')
