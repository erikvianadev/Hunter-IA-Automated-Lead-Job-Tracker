from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from hunter.choices import BillingCycle, BillingInvoiceStatus, BillingSubscriptionStatus
from hunter.models.models import BillingInvoice, BillingSubscription
from hunter.services.billing_service import BillingService


def create_active_pro_subscription(
    *,
    owner,
    billing_cycle: str = BillingCycle.MONTHLY,
    with_invoice: bool = True,
) -> BillingSubscription:
    now = timezone.now()
    price_amount = (
        Decimal('299.00')
        if billing_cycle == BillingCycle.YEARLY
        else Decimal('29.90')
    )
    current_period_end = now + (
        timedelta(days=365)
        if billing_cycle == BillingCycle.YEARLY
        else timedelta(days=30)
    )

    subscription = BillingSubscription.objects.create(
        owner=owner,
        plan_code=BillingService.PLAN_PRO,
        billing_cycle=billing_cycle,
        status=BillingSubscriptionStatus.ACTIVE,
        price_amount=price_amount,
        currency='BRL',
        auto_renew=True,
        started_at=now,
        current_period_end=current_period_end,
        expires_at=None,
    )

    if with_invoice:
        BillingInvoice.objects.create(
            owner=owner,
            subscription=subscription,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle=billing_cycle,
            status=BillingInvoiceStatus.PAID,
            amount=price_amount,
            currency='BRL',
            issued_at=now,
            paid_at=now,
            external_reference=f'test-{owner.id}-{subscription.id}',
        )

    return subscription
