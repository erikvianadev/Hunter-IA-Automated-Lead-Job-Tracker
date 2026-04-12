from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from hunter.choices import BillingCycle, BillingInvoiceStatus, BillingSubscriptionStatus
from hunter.models.models import BillingInvoice, BillingSubscription


class BillingError(Exception):
    pass


class BillingAccessError(BillingError):
    pass


@dataclass(frozen=True)
class PlanDefinition:
    code: str
    name: str
    billing_cycle: str
    price_amount: Decimal
    currency: str
    features: tuple[str, ...]
    highlighted: bool = False


class BillingService:
    PLAN_FREE = 'free'
    PLAN_PRO = 'pro'
    FEATURE_PREMIUM_REPORTS = 'premium_reports'
    FEATURE_RESUME_COMPARISON = 'resume_comparison'

    PLAN_CATALOG: tuple[PlanDefinition, ...] = (
        PlanDefinition(
            code=PLAN_FREE,
            name='Free',
            billing_cycle=BillingCycle.FREE,
            price_amount=Decimal('0.00'),
            currency='BRL',
            features=(
                'resume_upload',
                'resume_analysis',
                'seniority_assessment',
                'job_matching',
                'dashboard',
            ),
        ),
        PlanDefinition(
            code=PLAN_PRO,
            name='Pro',
            billing_cycle=BillingCycle.MONTHLY,
            price_amount=Decimal('29.90'),
            currency='BRL',
            highlighted=True,
            features=(
                'resume_upload',
                'resume_analysis',
                'seniority_assessment',
                'job_matching',
                'dashboard',
                FEATURE_PREMIUM_REPORTS,
                FEATURE_RESUME_COMPARISON,
                'priority_support',
                'multiple_resume_versions',
            ),
        ),
        PlanDefinition(
            code=PLAN_PRO,
            name='Pro Annual',
            billing_cycle=BillingCycle.YEARLY,
            price_amount=Decimal('299.00'),
            currency='BRL',
            features=(
                'resume_upload',
                'resume_analysis',
                'seniority_assessment',
                'job_matching',
                'dashboard',
                FEATURE_PREMIUM_REPORTS,
                FEATURE_RESUME_COMPARISON,
                'priority_support',
                'multiple_resume_versions',
            ),
        ),
    )

    def list_plans(self, *, owner=None) -> list[dict[str, object]]:
        current = self.get_subscription(owner=owner) if owner is not None else None
        current_plan_key = (
            (current["plan_code"], current["billing_cycle"])
            if current is not None
            else None
        )
        return [
            {
                "code": plan.code,
                "name": plan.name,
                "billing_cycle": plan.billing_cycle,
                "price_amount": plan.price_amount,
                "currency": plan.currency,
                "features": list(plan.features),
                "highlighted": plan.highlighted,
                "is_current": current_plan_key == (plan.code, plan.billing_cycle),
            }
            for plan in self.PLAN_CATALOG
        ]

    def get_subscription(self, *, owner) -> dict[str, object]:
        record = self._get_effective_subscription_record(owner=owner)
        if record is None:
            plan = self._get_plan(plan_code=self.PLAN_FREE, billing_cycle=BillingCycle.FREE)
            return self._build_free_subscription_payload(plan=plan)
        return self._serialize_subscription(record=record)

    @transaction.atomic
    def subscribe(self, *, owner, plan_code: str, billing_cycle: str) -> dict[str, object]:
        plan = self._get_plan(plan_code=plan_code, billing_cycle=billing_cycle)
        now = timezone.now()

        current_active_records = list(
            BillingSubscription.objects.filter(
                owner=owner,
                status__in=[
                    BillingSubscriptionStatus.ACTIVE,
                    BillingSubscriptionStatus.CANCELED,
                ],
            )
        )
        for record in current_active_records:
            record.status = BillingSubscriptionStatus.EXPIRED
            record.auto_renew = False
            record.expires_at = now
            if record.current_period_end is None or record.current_period_end > now:
                record.current_period_end = now
            if record.canceled_at is None:
                record.canceled_at = now
            record.save(
                update_fields=[
                    'status',
                    'auto_renew',
                    'expires_at',
                    'current_period_end',
                    'canceled_at',
                    'updated_at',
                ]
            )

        current_period_end = self._calculate_period_end(
            started_at=now,
            billing_cycle=plan.billing_cycle,
        )
        subscription = BillingSubscription.objects.create(
            owner=owner,
            plan_code=plan.code,
            billing_cycle=plan.billing_cycle,
            status=BillingSubscriptionStatus.ACTIVE,
            price_amount=plan.price_amount,
            currency=plan.currency,
            auto_renew=plan.code != self.PLAN_FREE,
            started_at=now,
            current_period_end=current_period_end,
            expires_at=current_period_end,
        )
        BillingInvoice.objects.create(
            owner=owner,
            subscription=subscription,
            plan_code=plan.code,
            billing_cycle=plan.billing_cycle,
            status=BillingInvoiceStatus.PAID,
            amount=plan.price_amount,
            currency=plan.currency,
            issued_at=now,
            paid_at=now,
            external_reference=f'{owner.id}-{subscription.id}-{plan.code}',
        )
        return self._serialize_subscription(record=subscription)

    @transaction.atomic
    def cancel(self, *, owner) -> dict[str, object]:
        subscription = self._get_effective_subscription_record(owner=owner)
        if subscription is None or subscription.plan_code == self.PLAN_FREE:
            raise BillingError('There is no paid subscription to cancel.')
        if subscription.status == BillingSubscriptionStatus.CANCELED:
            return self._serialize_subscription(record=subscription)

        subscription.status = BillingSubscriptionStatus.CANCELED
        subscription.auto_renew = False
        subscription.canceled_at = timezone.now()
        if subscription.expires_at is None:
            subscription.expires_at = subscription.current_period_end
        subscription.save(
            update_fields=[
                'status',
                'auto_renew',
                'canceled_at',
                'expires_at',
                'updated_at',
            ]
        )
        return self._serialize_subscription(record=subscription)

    def require_feature(self, *, owner, feature_code: str) -> None:
        subscription = self.get_subscription(owner=owner)
        if feature_code in subscription['features']:
            return
        raise BillingAccessError(
            f'The current plan does not include {feature_code}. Upgrade to Pro to continue.'
        )

    def _build_free_subscription_payload(self, *, plan: PlanDefinition) -> dict[str, object]:
        return {
            "id": None,
            "plan_code": plan.code,
            "plan_name": plan.name,
            "billing_cycle": plan.billing_cycle,
            "status": BillingSubscriptionStatus.ACTIVE,
            "price_amount": plan.price_amount,
            "currency": plan.currency,
            "auto_renew": False,
            "started_at": None,
            "current_period_end": None,
            "canceled_at": None,
            "expires_at": None,
            "features": list(plan.features),
            "last_invoice": None,
        }

    def _serialize_subscription(self, *, record: BillingSubscription) -> dict[str, object]:
        plan = self._get_plan(plan_code=record.plan_code, billing_cycle=record.billing_cycle)
        last_invoice = record.invoices.order_by('-issued_at', '-created_at').first()
        return {
            "id": record.id,
            "plan_code": record.plan_code,
            "plan_name": plan.name,
            "billing_cycle": record.billing_cycle,
            "status": record.status,
            "price_amount": record.price_amount,
            "currency": record.currency,
            "auto_renew": record.auto_renew,
            "started_at": record.started_at,
            "current_period_end": record.current_period_end,
            "canceled_at": record.canceled_at,
            "expires_at": record.expires_at,
            "features": list(plan.features),
            "last_invoice": (
                {
                    "id": last_invoice.id,
                    "plan_code": last_invoice.plan_code,
                    "billing_cycle": last_invoice.billing_cycle,
                    "status": last_invoice.status,
                    "amount": last_invoice.amount,
                    "currency": last_invoice.currency,
                    "issued_at": last_invoice.issued_at,
                    "paid_at": last_invoice.paid_at,
                    "external_reference": last_invoice.external_reference,
                }
                if last_invoice is not None
                else None
            ),
        }

    def _get_effective_subscription_record(self, *, owner) -> BillingSubscription | None:
        now = timezone.now()
        records = (
            BillingSubscription.objects
            .filter(owner=owner)
            .prefetch_related('invoices')
            .order_by('-created_at')
        )
        for record in records:
            if record.status == BillingSubscriptionStatus.ACTIVE:
                return record
            if (
                record.status == BillingSubscriptionStatus.CANCELED
                and record.expires_at is not None
                and record.expires_at > now
            ):
                return record
        return None

    def _get_plan(self, *, plan_code: str, billing_cycle: str) -> PlanDefinition:
        for plan in self.PLAN_CATALOG:
            if plan.code == plan_code and plan.billing_cycle == billing_cycle:
                return plan
        raise BillingError('Invalid billing plan selection.')

    def _calculate_period_end(self, *, started_at, billing_cycle: str):
        if billing_cycle == BillingCycle.MONTHLY:
            return started_at + timedelta(days=30)
        if billing_cycle == BillingCycle.YEARLY:
            return started_at + timedelta(days=365)
        return None
