from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone


class StripeGatewayError(Exception):
    pass


@dataclass(frozen=True)
class StripeCheckoutSession:
    session_id: str
    url: str
    customer_id: str | None
    subscription_id: str | None


class StripeBillingGatewayService:
    WEBHOOK_TOLERANCE_SECONDS = 300

    def __init__(self) -> None:
        stripe_settings = getattr(settings, 'STRIPE', {})
        self.secret_key = stripe_settings.get('SECRET_KEY', '')
        self.publishable_key = stripe_settings.get('PUBLISHABLE_KEY', '')
        self.webhook_secret = stripe_settings.get('WEBHOOK_SECRET', '')
        self.api_base_url = stripe_settings.get('API_BASE_URL', 'https://api.stripe.com').rstrip('/')
        self.success_url = stripe_settings.get('SUCCESS_URL', '')
        self.cancel_url = stripe_settings.get('CANCEL_URL', '')
        self.portal_return_url = stripe_settings.get('PORTAL_RETURN_URL', '')
        self.price_ids = stripe_settings.get('PRICE_IDS', {})

    def is_configured(self) -> bool:
        return bool(self.secret_key)

    def get_price_id(self, *, plan_code: str, billing_cycle: str) -> str:
        return self.price_ids.get(plan_code, {}).get(billing_cycle, '')

    def create_checkout_session(
        self,
        *,
        owner,
        plan_code: str,
        billing_cycle: str,
        customer_id: str | None = None,
    ) -> StripeCheckoutSession:
        price_id = self.get_price_id(plan_code=plan_code, billing_cycle=billing_cycle)
        if not price_id:
            raise StripeGatewayError('Stripe price is not configured for the selected plan.')

        payload = {
            'mode': 'subscription',
            'success_url': self.success_url,
            'cancel_url': self.cancel_url,
            'client_reference_id': str(owner.id),
            'line_items[0][price]': price_id,
            'line_items[0][quantity]': 1,
            'metadata[owner_id]': str(owner.id),
            'metadata[plan_code]': plan_code,
            'metadata[billing_cycle]': billing_cycle,
            'subscription_data[metadata][owner_id]': str(owner.id),
            'subscription_data[metadata][plan_code]': plan_code,
            'subscription_data[metadata][billing_cycle]': billing_cycle,
        }
        if owner.email:
            payload['customer_email'] = owner.email
        if customer_id:
            payload['customer'] = customer_id
            payload.pop('customer_email', None)

        response = self._request('POST', '/v1/checkout/sessions', data=payload)
        return StripeCheckoutSession(
            session_id=response['id'],
            url=response['url'],
            customer_id=response.get('customer'),
            subscription_id=response.get('subscription'),
        )

    def retrieve_subscription(self, *, subscription_id: str) -> dict[str, Any]:
        return self._request('GET', f'/v1/subscriptions/{subscription_id}')

    def cancel_subscription(self, *, subscription_id: str) -> dict[str, Any]:
        return self._request(
            'POST',
            f'/v1/subscriptions/{subscription_id}',
            data={'cancel_at_period_end': 'true'},
        )

    def verify_and_construct_event(
        self,
        *,
        payload: bytes,
        signature_header: str,
    ) -> dict[str, Any]:
        if not self.webhook_secret:
            raise StripeGatewayError('Stripe webhook secret is not configured.')
        if not signature_header:
            raise StripeGatewayError('Missing Stripe-Signature header.')

        timestamp = None
        signatures: list[str] = []
        for item in signature_header.split(','):
            key, _, value = item.partition('=')
            if key == 't':
                timestamp = value
            elif key == 'v1':
                signatures.append(value)

        if not timestamp or not signatures:
            raise StripeGatewayError('Invalid Stripe-Signature header.')

        try:
            timestamp_int = int(timestamp)
        except ValueError as exc:
            raise StripeGatewayError('Invalid Stripe signature timestamp.') from exc

        age = abs(int(timezone.now().timestamp()) - timestamp_int)
        if age > self.WEBHOOK_TOLERANCE_SECONDS:
            raise StripeGatewayError('Stripe webhook signature has expired.')

        signed_payload = f'{timestamp}.{payload.decode("utf-8")}'
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        if not any(hmac.compare_digest(expected_signature, signature) for signature in signatures):
            raise StripeGatewayError('Stripe webhook signature verification failed.')

        try:
            return json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError as exc:
            raise StripeGatewayError('Invalid Stripe webhook payload.') from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.secret_key:
            raise StripeGatewayError('Stripe secret key is not configured.')

        url = f'{self.api_base_url}{path}'
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
        }

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            else:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                response = requests.post(
                    url,
                    headers=headers,
                    data=urlencode(self._normalize_payload(data or {})),
                    timeout=15,
                )
        except requests.RequestException as exc:
            raise StripeGatewayError('Failed to communicate with Stripe.') from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise StripeGatewayError('Stripe returned an invalid response.') from exc

        if response.status_code >= 400:
            error_payload = payload.get('error', {})
            message = error_payload.get('message') or 'Stripe request failed.'
            raise StripeGatewayError(message)

        return payload

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in payload.items():
            if value is None:
                continue
            if isinstance(value, Decimal):
                normalized[key] = str(value)
            else:
                normalized[key] = str(value)
        return normalized
