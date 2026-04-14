from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from hunter.choices import BillingCycle, BillingInvoiceStatus, BillingSubscriptionStatus
from hunter.models.models import BillingInvoice, BillingSubscription

from .stripe_gateway_service import StripeBillingGatewayService, StripeGatewayError


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

    def __init__(self, *, stripe_gateway: StripeBillingGatewayService | None = None) -> None:
        self.stripe_gateway = stripe_gateway or StripeBillingGatewayService()

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

    def subscribe(self, *, owner, plan_code: str, billing_cycle: str) -> dict[str, object]:
        plan = self._get_plan(plan_code=plan_code, billing_cycle=billing_cycle)
        if plan.code == self.PLAN_FREE:
            raise BillingError('O plano gratuito nao precisa de checkout.')
        if not self.stripe_gateway.is_configured():
            raise BillingError('O faturamento online nao esta configurado neste ambiente.')

        price_id = self.stripe_gateway.get_price_id(
            plan_code=plan.code,
            billing_cycle=plan.billing_cycle,
        )
        if not price_id:
            raise BillingError('O preco do plano escolhido nao esta configurado neste ambiente.')

        existing_customer_id = self._get_latest_customer_id(owner=owner)
        try:
            checkout_session = self.stripe_gateway.create_checkout_session(
                owner=owner,
                plan_code=plan.code,
                billing_cycle=plan.billing_cycle,
                customer_id=existing_customer_id,
            )
        except StripeGatewayError as exc:
            raise BillingError(str(exc)) from exc

        return {
            'plan_code': plan.code,
            'billing_cycle': plan.billing_cycle,
            'checkout_session_id': checkout_session.session_id,
            'checkout_url': checkout_session.url,
            'publishable_key': self.stripe_gateway.publishable_key,
            'price_id': price_id,
        }

    @transaction.atomic
    def cancel(self, *, owner) -> dict[str, object]:
        subscription = self._get_effective_subscription_record(owner=owner)
        if subscription is None or subscription.plan_code == self.PLAN_FREE:
            raise BillingError('Nao existe uma assinatura paga ativa para cancelar.')
        if subscription.status == BillingSubscriptionStatus.CANCELED:
            return self._serialize_subscription(record=subscription)

        if subscription.stripe_subscription_id:
            try:
                stripe_subscription = self.stripe_gateway.cancel_subscription(
                    subscription_id=subscription.stripe_subscription_id,
                )
            except StripeGatewayError as exc:
                raise BillingError(str(exc)) from exc
            subscription = self._sync_subscription_from_stripe_data(
                owner=owner,
                stripe_subscription=stripe_subscription,
                checkout_session_id=subscription.stripe_checkout_session_id,
            )
            return self._serialize_subscription(record=subscription)

        now = timezone.now()
        subscription.status = BillingSubscriptionStatus.CANCELED
        subscription.auto_renew = False
        subscription.canceled_at = now
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
            'Seu plano atual nao inclui este recurso. Faca upgrade para o Pro quando quiser liberar esse acesso.'
        )

    @transaction.atomic
    def handle_webhook_event(self, *, payload: bytes, signature_header: str) -> None:
        try:
            event = self.stripe_gateway.verify_and_construct_event(
                payload=payload,
                signature_header=signature_header,
            )
            event_type = event.get('type', '')
            event_object = event.get('data', {}).get('object', {})

            if event_type == 'checkout.session.completed':
                self._handle_checkout_completed(session=event_object)
                return
            if event_type == 'customer.subscription.updated':
                self._handle_subscription_updated(subscription_data=event_object)
                return
            if event_type == 'customer.subscription.deleted':
                self._handle_subscription_deleted(subscription_data=event_object)
                return
            if event_type == 'invoice.paid':
                self._handle_invoice_paid(invoice_data=event_object)
        except (StripeGatewayError, BillingError) as exc:
            raise BillingError(str(exc)) from exc

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
        last_invoice = (
            record.invoices
            .filter(owner=record.owner)
            .order_by('-issued_at', '-created_at')
            .first()
        )
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

    def _get_latest_customer_id(self, *, owner) -> str | None:
        return (
            BillingSubscription.objects
            .filter(owner=owner)
            .exclude(stripe_customer_id='')
            .order_by('-created_at')
            .values_list('stripe_customer_id', flat=True)
            .first()
        )

    def _get_plan(self, *, plan_code: str, billing_cycle: str) -> PlanDefinition:
        for plan in self.PLAN_CATALOG:
            if plan.code == plan_code and plan.billing_cycle == billing_cycle:
                return plan
        raise BillingError('A opcao de plano escolhida nao e valida.')

    def _calculate_period_end(self, *, started_at, billing_cycle: str):
        if billing_cycle == BillingCycle.MONTHLY:
            return started_at + timedelta(days=30)
        if billing_cycle == BillingCycle.YEARLY:
            return started_at + timedelta(days=365)
        return None

    def _handle_checkout_completed(self, *, session: dict[str, Any]) -> None:
        owner = self._resolve_owner_from_session(session=session)
        subscription_id = session.get('subscription')
        if owner is None or not subscription_id:
            return

        stripe_subscription = self.stripe_gateway.retrieve_subscription(
            subscription_id=subscription_id,
        )
        self._sync_subscription_from_stripe_data(
            owner=owner,
            stripe_subscription=stripe_subscription,
            checkout_session_id=session.get('id', ''),
            stripe_customer_id=session.get('customer') or stripe_subscription.get('customer', ''),
        )

    def _handle_subscription_updated(self, *, subscription_data: dict[str, Any]) -> None:
        owner = self._resolve_owner_from_subscription(subscription_data=subscription_data)
        if owner is None:
            return
        self._sync_subscription_from_stripe_data(
            owner=owner,
            stripe_subscription=subscription_data,
        )

    def _handle_subscription_deleted(self, *, subscription_data: dict[str, Any]) -> None:
        owner = self._resolve_owner_from_subscription(subscription_data=subscription_data)
        if owner is None:
            return
        self._sync_subscription_from_stripe_data(
            owner=owner,
            stripe_subscription=subscription_data,
        )

    def _handle_invoice_paid(self, *, invoice_data: dict[str, Any]) -> None:
        stripe_subscription_id = invoice_data.get('subscription', '')
        subscription = (
            BillingSubscription.objects
            .filter(stripe_subscription_id=stripe_subscription_id)
            .select_related('owner')
            .first()
        )

        if subscription is None and stripe_subscription_id:
            stripe_subscription = self.stripe_gateway.retrieve_subscription(
                subscription_id=stripe_subscription_id,
            )
            owner = self._resolve_owner_from_subscription(subscription_data=stripe_subscription)
            if owner is None:
                return
            subscription = self._sync_subscription_from_stripe_data(
                owner=owner,
                stripe_subscription=stripe_subscription,
            )

        if subscription is None:
            return

        issued_at = self._from_unix_timestamp(invoice_data.get('created')) or timezone.now()
        paid_at = (
            self._from_unix_timestamp(invoice_data.get('status_transitions', {}).get('paid_at'))
            or issued_at
        )
        amount_paid = Decimal(str(invoice_data.get('amount_paid', 0))) / Decimal('100')

        BillingInvoice.objects.update_or_create(
            owner=subscription.owner,
            subscription=subscription,
            external_reference=invoice_data.get('id', ''),
            defaults={
                'plan_code': subscription.plan_code,
                'billing_cycle': subscription.billing_cycle,
                'status': BillingInvoiceStatus.PAID,
                'amount': amount_paid,
                'currency': str(invoice_data.get('currency', subscription.currency)).upper(),
                'stripe_invoice_id': invoice_data.get('id', ''),
                'issued_at': issued_at,
                'paid_at': paid_at,
            },
        )

    def _resolve_owner_from_session(self, *, session: dict[str, Any]):
        owner_id = (
            session.get('client_reference_id')
            or session.get('metadata', {}).get('owner_id')
        )
        return self._get_owner_by_id(owner_id=owner_id)

    def _resolve_owner_from_subscription(self, *, subscription_data: dict[str, Any]):
        record = (
            BillingSubscription.objects
            .filter(stripe_subscription_id=subscription_data.get('id', ''))
            .select_related('owner')
            .first()
        )
        if record is not None:
            return record.owner

        metadata = subscription_data.get('metadata', {})
        owner_id = metadata.get('owner_id')
        if owner_id:
            return self._get_owner_by_id(owner_id=owner_id)

        customer_id = subscription_data.get('customer', '')
        record = (
            BillingSubscription.objects
            .filter(stripe_customer_id=customer_id)
            .select_related('owner')
            .order_by('-created_at')
            .first()
        )
        return record.owner if record is not None else None

    def _get_owner_by_id(self, *, owner_id):
        if not owner_id:
            return None
        try:
            return get_user_model().objects.filter(id=int(owner_id)).first()
        except (TypeError, ValueError):
            return None

    def _sync_subscription_from_stripe_data(
        self,
        *,
        owner,
        stripe_subscription: dict[str, Any],
        checkout_session_id: str = '',
        stripe_customer_id: str = '',
    ) -> BillingSubscription:
        plan_code, billing_cycle = self._resolve_plan_from_stripe_subscription(
            stripe_subscription=stripe_subscription,
        )
        plan = self._get_plan(plan_code=plan_code, billing_cycle=billing_cycle)
        started_at = self._from_unix_timestamp(stripe_subscription.get('start_date')) or timezone.now()
        current_period_end = self._from_unix_timestamp(stripe_subscription.get('current_period_end'))
        canceled_at = self._from_unix_timestamp(stripe_subscription.get('canceled_at'))
        status = self._map_stripe_subscription_status(
            stripe_status=stripe_subscription.get('status', ''),
            cancel_at_period_end=bool(stripe_subscription.get('cancel_at_period_end')),
            current_period_end=current_period_end,
        )

        defaults = {
            'plan_code': plan.code,
            'billing_cycle': plan.billing_cycle,
            'status': status,
            'price_amount': self._resolve_price_amount(
                stripe_subscription=stripe_subscription,
                fallback=plan.price_amount,
            ),
            'currency': str(stripe_subscription.get('currency', plan.currency)).upper(),
            'stripe_customer_id': stripe_customer_id or stripe_subscription.get('customer', ''),
            'stripe_checkout_session_id': checkout_session_id,
            'auto_renew': not bool(stripe_subscription.get('cancel_at_period_end')),
            'started_at': started_at,
            'current_period_end': current_period_end,
            'canceled_at': canceled_at,
            'expires_at': current_period_end if status != BillingSubscriptionStatus.ACTIVE else None,
        }
        subscription, created = BillingSubscription.objects.update_or_create(
            owner=owner,
            stripe_subscription_id=stripe_subscription.get('id', ''),
            defaults=defaults,
        )

        if created:
            self._expire_other_subscriptions(owner=owner, keep_subscription_id=subscription.id)
        else:
            self._expire_other_subscriptions(
                owner=owner,
                keep_subscription_id=subscription.id,
                keep_stripe_subscription_id=subscription.stripe_subscription_id,
            )

        return subscription

    def _expire_other_subscriptions(
        self,
        *,
        owner,
        keep_subscription_id: int,
        keep_stripe_subscription_id: str = '',
    ) -> None:
        now = timezone.now()
        records = BillingSubscription.objects.filter(owner=owner).exclude(id=keep_subscription_id)
        for record in records:
            if keep_stripe_subscription_id and record.stripe_subscription_id == keep_stripe_subscription_id:
                continue
            if record.status == BillingSubscriptionStatus.EXPIRED:
                continue
            record.status = BillingSubscriptionStatus.EXPIRED
            record.auto_renew = False
            if record.current_period_end is None or record.current_period_end > now:
                record.current_period_end = now
            if record.expires_at is None:
                record.expires_at = record.current_period_end
            if record.canceled_at is None:
                record.canceled_at = now
            record.save(
                update_fields=[
                    'status',
                    'auto_renew',
                    'current_period_end',
                    'expires_at',
                    'canceled_at',
                    'updated_at',
                ]
            )

    def _resolve_plan_from_stripe_subscription(
        self,
        *,
        stripe_subscription: dict[str, Any],
    ) -> tuple[str, str]:
        metadata = stripe_subscription.get('metadata', {})
        plan_code = metadata.get('plan_code')
        billing_cycle = metadata.get('billing_cycle')
        if plan_code and billing_cycle:
            return plan_code, billing_cycle

        items = stripe_subscription.get('items', {}).get('data', [])
        price_id = items[0].get('price', {}).get('id', '') if items else ''
        for plan in self.PLAN_CATALOG:
            configured_price_id = self.stripe_gateway.get_price_id(
                plan_code=plan.code,
                billing_cycle=plan.billing_cycle,
            )
            if configured_price_id and configured_price_id == price_id:
                return plan.code, plan.billing_cycle

        raise BillingError('Nao foi possivel associar a assinatura recebida a um plano local.')

    def _resolve_price_amount(
        self,
        *,
        stripe_subscription: dict[str, Any],
        fallback: Decimal,
    ) -> Decimal:
        items = stripe_subscription.get('items', {}).get('data', [])
        if not items:
            return fallback
        unit_amount = items[0].get('price', {}).get('unit_amount')
        if unit_amount is None:
            return fallback
        return Decimal(str(unit_amount)) / Decimal('100')

    def _map_stripe_subscription_status(
        self,
        *,
        stripe_status: str,
        cancel_at_period_end: bool,
        current_period_end,
    ) -> str:
        if stripe_status in {'active', 'trialing', 'past_due'}:
            if cancel_at_period_end:
                return BillingSubscriptionStatus.CANCELED
            return BillingSubscriptionStatus.ACTIVE
        if stripe_status == 'canceled':
            if current_period_end and current_period_end > timezone.now():
                return BillingSubscriptionStatus.CANCELED
            return BillingSubscriptionStatus.EXPIRED
        return BillingSubscriptionStatus.EXPIRED

    def _from_unix_timestamp(self, value) -> datetime | None:
        if not value:
            return None
        return datetime.fromtimestamp(int(value), tz=dt_timezone.utc)
