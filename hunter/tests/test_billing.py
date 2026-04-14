import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from hunter.models.models import BillingInvoice, BillingSubscription
from hunter.services.billing_service import BillingService


STRIPE_TEST_SETTINGS = {
    "SECRET_KEY": "sk_test_123",
    "PUBLISHABLE_KEY": "pk_test_123",
    "WEBHOOK_SECRET": "whsec_test_123",
    "API_BASE_URL": "https://api.stripe.com",
    "SUCCESS_URL": "https://frontend.example.com/billing/success?session_id={CHECKOUT_SESSION_ID}",
    "CANCEL_URL": "https://frontend.example.com/billing/cancel",
    "PORTAL_RETURN_URL": "https://frontend.example.com/settings/billing",
    "PRICE_IDS": {
        "pro": {
            "monthly": "price_monthly_123",
            "yearly": "price_yearly_123",
        },
    },
}


@override_settings(STRIPE=STRIPE_TEST_SETTINGS)
class BillingApiTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="billing-user",
            email="billing-user@example.com",
            password="secret",
        )
        self.other_user = get_user_model().objects.create_user(
            username="billing-other",
            email="billing-other@example.com",
            password="secret",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_plans_marks_current_free_plan_for_new_user(self) -> None:
        response = self.client.get("/hunter/api/billing/plans/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        current_plans = [plan for plan in response.data if plan["is_current"]]
        self.assertEqual(len(current_plans), 1)
        self.assertEqual(current_plans[0]["code"], BillingService.PLAN_FREE)

    def test_subscription_overview_returns_free_plan_when_user_has_no_subscription(self) -> None:
        response = self.client.get("/hunter/api/billing/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subscription"]["plan_code"], BillingService.PLAN_FREE)
        self.assertEqual(response.data["subscription"]["billing_cycle"], "free")
        self.assertIsNone(response.data["subscription"]["last_invoice"])
        self.assertEqual(len(response.data["plans"]), 3)

    @patch("hunter.services.billing_service.StripeBillingGatewayService.create_checkout_session")
    def test_subscribe_creates_checkout_session_for_paid_plan(self, mock_create_checkout_session) -> None:
        mock_create_checkout_session.return_value = type(
            "CheckoutSession",
            (),
            {
                "session_id": "cs_test_123",
                "url": "https://checkout.stripe.com/pay/cs_test_123",
                "customer_id": "cus_test_123",
                "subscription_id": None,
            },
        )()

        response = self.client.post(
            "/hunter/api/billing/subscribe/",
            {
                "plan_code": BillingService.PLAN_PRO,
                "billing_cycle": "monthly",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["plan_code"], BillingService.PLAN_PRO)
        self.assertEqual(response.data["billing_cycle"], "monthly")
        self.assertEqual(response.data["checkout_session_id"], "cs_test_123")
        self.assertEqual(
            response.data["checkout_url"],
            "https://checkout.stripe.com/pay/cs_test_123",
        )
        self.assertEqual(response.data["price_id"], "price_monthly_123")
        self.assertFalse(BillingSubscription.objects.filter(owner=self.user).exists())

    def test_subscribe_returns_error_when_free_plan_is_requested(self) -> None:
        response = self.client.post(
            "/hunter/api/billing/subscribe/",
            {
                "plan_code": BillingService.PLAN_FREE,
                "billing_cycle": "free",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nao precisa de checkout", response.data["detail"].lower())

    @patch("hunter.services.billing_service.StripeBillingGatewayService.cancel_subscription")
    def test_cancel_marks_remote_subscription_as_canceled_but_keeps_access_window(
        self,
        mock_cancel_subscription,
    ) -> None:
        subscription = BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="yearly",
            status="active",
            price_amount="299.00",
            currency="BRL",
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
            auto_renew=True,
            started_at="2026-04-10T10:00:00Z",
            current_period_end="2027-04-10T10:00:00Z",
        )
        mock_cancel_subscription.return_value = {
            "id": "sub_test_123",
            "customer": "cus_test_123",
            "status": "active",
            "cancel_at_period_end": True,
            "current_period_end": 1807344000,
            "canceled_at": 1775805600,
            "start_date": 1773213600,
            "currency": "brl",
            "metadata": {
                "owner_id": str(self.user.id),
                "plan_code": BillingService.PLAN_PRO,
                "billing_cycle": "yearly",
            },
            "items": {
                "data": [
                    {
                        "price": {
                            "id": "price_yearly_123",
                            "unit_amount": 29900,
                        }
                    }
                ]
            },
        }

        response = self.client.post("/hunter/api/billing/cancel/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], subscription.id)
        self.assertEqual(response.data["status"], "canceled")
        self.assertFalse(response.data["auto_renew"])
        self.assertIsNotNone(response.data["canceled_at"])
        self.assertIsNotNone(response.data["expires_at"])

    def test_cancel_returns_error_without_paid_subscription(self) -> None:
        response = self.client.post("/hunter/api/billing/cancel/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("nao existe uma assinatura paga ativa", response.data["detail"].lower())

    def test_billing_is_scoped_to_authenticated_user(self) -> None:
        BillingSubscription.objects.create(
            owner=self.other_user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="monthly",
            status="active",
            price_amount="29.90",
            currency="BRL",
            stripe_customer_id="cus_other_123",
            stripe_subscription_id="sub_other_123",
            auto_renew=True,
            started_at="2026-04-10T10:00:00Z",
            current_period_end="2026-05-10T10:00:00Z",
        )

        response = self.client.get("/hunter/api/billing/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subscription"]["plan_code"], BillingService.PLAN_FREE)

    def test_subscription_overview_ignores_invoice_owned_by_another_user(self) -> None:
        subscription = BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="monthly",
            status="active",
            price_amount="29.90",
            currency="BRL",
            stripe_customer_id="cus_test_456",
            stripe_subscription_id="sub_test_456",
            auto_renew=True,
            started_at="2026-04-10T10:00:00Z",
            current_period_end="2026-05-10T10:00:00Z",
        )
        BillingInvoice.objects.create(
            owner=self.other_user,
            subscription=subscription,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="monthly",
            status="paid",
            amount="29.90",
            currency="BRL",
            stripe_invoice_id="in_foreign_123",
            issued_at="2026-04-10T10:00:00Z",
            paid_at="2026-04-10T10:05:00Z",
            external_reference="foreign-invoice",
        )

        response = self.client.get("/hunter/api/billing/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subscription"]["id"], subscription.id)
        self.assertIsNone(response.data["subscription"]["last_invoice"])

    @patch("hunter.services.billing_service.StripeBillingGatewayService.retrieve_subscription")
    def test_webhook_checkout_completion_creates_local_subscription(
        self,
        mock_retrieve_subscription,
    ) -> None:
        mock_retrieve_subscription.return_value = {
            "id": "sub_test_checkout",
            "customer": "cus_test_checkout",
            "status": "active",
            "cancel_at_period_end": False,
            "current_period_end": 1778400000,
            "canceled_at": None,
            "start_date": 1775808000,
            "currency": "brl",
            "metadata": {
                "owner_id": str(self.user.id),
                "plan_code": BillingService.PLAN_PRO,
                "billing_cycle": "monthly",
            },
            "items": {
                "data": [
                    {
                        "price": {
                            "id": "price_monthly_123",
                            "unit_amount": 2990,
                        }
                    }
                ]
            },
        }
        payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "client_reference_id": str(self.user.id),
                    "customer": "cus_test_checkout",
                    "subscription": "sub_test_checkout",
                    "metadata": {
                        "owner_id": str(self.user.id),
                        "plan_code": BillingService.PLAN_PRO,
                        "billing_cycle": "monthly",
                    },
                }
            },
        }

        response = self.client.post(
            "/hunter/api/billing/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            **{"HTTP_STRIPE_SIGNATURE": self._build_signature(payload)},
        )

        self.assertEqual(response.status_code, 200)
        subscription = BillingSubscription.objects.get(owner=self.user)
        self.assertEqual(subscription.plan_code, BillingService.PLAN_PRO)
        self.assertEqual(subscription.billing_cycle, "monthly")
        self.assertEqual(subscription.stripe_subscription_id, "sub_test_checkout")
        self.assertEqual(subscription.stripe_checkout_session_id, "cs_test_123")

    def test_webhook_invoice_paid_creates_local_invoice(self) -> None:
        subscription = BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="monthly",
            status="active",
            price_amount="29.90",
            currency="BRL",
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
            auto_renew=True,
            started_at="2026-04-10T10:00:00Z",
            current_period_end="2026-05-10T10:00:00Z",
        )
        payload = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_test_123",
                    "subscription": "sub_test_123",
                    "amount_paid": 2990,
                    "currency": "brl",
                    "created": 1775900000,
                    "status_transitions": {
                        "paid_at": 1775900100,
                    },
                }
            },
        }

        response = self.client.post(
            "/hunter/api/billing/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            **{"HTTP_STRIPE_SIGNATURE": self._build_signature(payload)},
        )

        self.assertEqual(response.status_code, 200)
        invoice = BillingInvoice.objects.get(subscription=subscription)
        self.assertEqual(invoice.external_reference, "in_test_123")
        self.assertEqual(invoice.stripe_invoice_id, "in_test_123")
        self.assertEqual(str(invoice.amount), "29.90")
        self.assertEqual(invoice.status, "paid")

    def test_webhook_rejects_invalid_signature(self) -> None:
        payload = {
            "type": "invoice.paid",
            "data": {"object": {"id": "in_test_invalid"}},
        }

        response = self.client.post(
            "/hunter/api/billing/webhook/",
            data=json.dumps(payload),
            content_type="application/json",
            **{"HTTP_STRIPE_SIGNATURE": "t=1,v1=invalid"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("signature", response.data["detail"].lower())

    def _build_signature(self, payload: dict) -> str:
        timestamp = str(int(timezone.now().timestamp()))
        body = json.dumps(payload)
        signed_payload = f"{timestamp}.{body}"
        signature = hmac.new(
            STRIPE_TEST_SETTINGS["WEBHOOK_SECRET"].encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"t={timestamp},v1={signature}"
