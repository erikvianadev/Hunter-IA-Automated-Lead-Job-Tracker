import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from hunter.models.models import BillingInvoice, BillingSubscription
from hunter.services.billing_service import BillingService
from hunter.services.stripe_gateway_service import StripeBillingGatewayService, StripeGatewayError


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
            "trial_15": "price_trial_15_123",
            "trial_30": "price_trial_30_123",
            "trial_90": "price_trial_90_123",
        },
    },
}


def throttle_settings(**rates):
    framework_settings = dict(settings.REST_FRAMEWORK)
    framework_settings["DEFAULT_THROTTLE_RATES"] = {
        **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        **rates,
    }
    return framework_settings


@override_settings(STRIPE=STRIPE_TEST_SETTINGS)
class BillingApiTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
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

    def test_list_plans_returns_only_timed_access_options_for_new_user(self) -> None:
        response = self.client.get("/hunter/api/billing/plans/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(
            [plan["billing_cycle"] for plan in response.data],
            ["trial_15", "trial_30", "trial_90"],
        )
        self.assertTrue(all(plan["code"] == BillingService.PLAN_PRO for plan in response.data))
        self.assertFalse(any(plan["is_current"] for plan in response.data))

    def test_subscription_overview_returns_free_plan_when_user_has_no_subscription(self) -> None:
        response = self.client.get("/hunter/api/billing/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subscription"]["plan_code"], BillingService.PLAN_FREE)
        self.assertEqual(response.data["subscription"]["billing_cycle"], "free")
        self.assertTrue(response.data["subscription"]["is_entitled"])
        self.assertEqual(response.data["subscription"]["access_state"], "active")
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
                "billing_cycle": "trial_30",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["plan_code"], BillingService.PLAN_PRO)
        self.assertEqual(response.data["billing_cycle"], "trial_30")
        self.assertEqual(response.data["checkout_session_id"], "cs_test_123")
        self.assertEqual(
            response.data["checkout_url"],
            "https://checkout.stripe.com/pay/cs_test_123",
        )
        self.assertEqual(response.data["price_id"], "price_trial_30_123")
        self.assertFalse(BillingSubscription.objects.filter(owner=self.user).exists())

    @patch("hunter.services.stripe_gateway_service.requests.post")
    def test_stripe_checkout_for_timed_access_uses_one_time_payment_mode(self, mock_post) -> None:
        mock_post.return_value = type(
            "StripeResponse",
            (),
            {
                "status_code": 200,
                "json": lambda self: {
                    "id": "cs_test_123",
                    "url": "https://checkout.stripe.com/pay/cs_test_123",
                    "customer": "cus_test_123",
                    "subscription": None,
                },
            },
        )()

        gateway = StripeBillingGatewayService()
        gateway.create_checkout_session(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
        )

        request_payload = parse_qs(mock_post.call_args.kwargs["data"])
        self.assertEqual(request_payload["mode"], ["payment"])
        self.assertEqual(request_payload["line_items[0][price]"], ["price_trial_30_123"])
        self.assertEqual(
            request_payload["payment_intent_data[metadata][billing_cycle]"],
            ["trial_30"],
        )
        self.assertNotIn("subscription_data[metadata][billing_cycle]", request_payload)

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
        self.assertEqual(response.data["code"], "billing_action_unavailable")
        self.assertIn("nao precisa de checkout", response.data["detail"].lower())

    @patch("hunter.services.billing_service.StripeBillingGatewayService.create_checkout_session")
    def test_subscribe_hides_raw_gateway_errors(self, mock_create_checkout_session) -> None:
        mock_create_checkout_session.side_effect = StripeGatewayError("Failed to communicate with Stripe.")

        response = self.client.post(
            "/hunter/api/billing/subscribe/",
            {
                "plan_code": BillingService.PLAN_PRO,
                "billing_cycle": "trial_30",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "billing_action_unavailable")
        self.assertIn("Nao foi possivel falar com o checkout", response.data["detail"])
        self.assertNotIn("Stripe", response.data["detail"])

    def test_subscribe_blocks_duplicate_checkout_for_current_plan(self) -> None:
        BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
            status="active",
            price_amount="24.90",
            currency="BRL",
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
            auto_renew=True,
            started_at=timezone.now() - timedelta(days=3),
            current_period_end=timezone.now() + timedelta(days=27),
        )

        response = self.client.post(
            "/hunter/api/billing/subscribe/",
            {
                "plan_code": BillingService.PLAN_PRO,
                "billing_cycle": "trial_30",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "billing_action_unavailable")
        self.assertIn("ja esta ativo", response.data["detail"].lower())

    @patch("hunter.services.billing_service.StripeBillingGatewayService.cancel_subscription")
    def test_cancel_marks_remote_subscription_as_canceled_but_keeps_access_window(
        self,
        mock_cancel_subscription,
    ) -> None:
        subscription = BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_90",
            status="active",
            price_amount="59.90",
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
                "billing_cycle": "trial_90",
            },
            "items": {
                "data": [
                    {
                        "price": {
                            "id": "price_trial_90_123",
                            "unit_amount": 5990,
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
        self.assertIn("nao existe um acesso pago ativo", response.data["detail"].lower())

    @override_settings(REST_FRAMEWORK=throttle_settings(billing_action="1/min"))
    def test_billing_actions_are_rate_limited(self) -> None:
        first_response = self.client.post("/hunter/api/billing/cancel/", {}, format="json")
        second_response = self.client.post("/hunter/api/billing/cancel/", {}, format="json")

        self.assertEqual(first_response.status_code, 400)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.data["code"], "rate_limited")

    def test_billing_is_scoped_to_authenticated_user(self) -> None:
        BillingSubscription.objects.create(
            owner=self.other_user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
            status="active",
            price_amount="24.90",
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

    def test_expired_active_subscription_falls_back_to_free_entitlement(self) -> None:
        BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
            status="active",
            price_amount="24.90",
            currency="BRL",
            stripe_customer_id="cus_test_expired",
            stripe_subscription_id="sub_test_expired",
            auto_renew=True,
            started_at=timezone.now() - timedelta(days=60),
            current_period_end=timezone.now() - timedelta(days=30),
        )

        response = self.client.get("/hunter/api/billing/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subscription"]["plan_code"], BillingService.PLAN_FREE)
        self.assertEqual(response.data["subscription"]["features"], [
            "resume_upload",
            "resume_analysis",
            "seniority_assessment",
            "job_matching",
            "dashboard",
        ])

    def test_subscription_overview_ignores_invoice_owned_by_another_user(self) -> None:
        subscription = BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
            status="active",
            price_amount="24.90",
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
            billing_cycle="trial_30",
            status="paid",
            amount="24.90",
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
    def test_webhook_checkout_completion_creates_timed_access_subscription(
        self,
        mock_retrieve_subscription,
    ) -> None:
        payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "mode": "payment",
                    "payment_status": "paid",
                    "client_reference_id": str(self.user.id),
                    "customer": "cus_test_checkout",
                    "payment_intent": "pi_test_checkout",
                    "amount_total": 2490,
                    "currency": "brl",
                    "created": 1775808000,
                    "metadata": {
                        "owner_id": str(self.user.id),
                        "plan_code": BillingService.PLAN_PRO,
                        "billing_cycle": "trial_30",
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
        self.assertEqual(subscription.billing_cycle, "trial_30")
        self.assertEqual(subscription.stripe_subscription_id, "")
        self.assertEqual(subscription.stripe_checkout_session_id, "cs_test_123")
        self.assertFalse(subscription.auto_renew)
        self.assertIsNotNone(subscription.current_period_end)
        self.assertTrue(BillingInvoice.objects.filter(external_reference="pi_test_checkout").exists())
        mock_retrieve_subscription.assert_not_called()

    def test_webhook_invoice_paid_creates_local_invoice(self) -> None:
        subscription = BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
            status="active",
            price_amount="24.90",
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
                    "amount_paid": 2490,
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
        self.assertEqual(str(invoice.amount), "24.90")
        self.assertEqual(invoice.status, "paid")

    @patch("hunter.services.billing_service.StripeBillingGatewayService.retrieve_subscription")
    def test_webhook_invoice_without_subscription_id_does_not_attach_blank_local_subscription(
        self,
        mock_retrieve_subscription,
    ) -> None:
        BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
            status="active",
            price_amount="24.90",
            currency="BRL",
            stripe_customer_id="",
            stripe_subscription_id="",
            auto_renew=True,
            started_at=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        payload = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_without_subscription",
                    "amount_paid": 2490,
                    "currency": "brl",
                    "created": 1775900000,
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
        self.assertFalse(BillingInvoice.objects.filter(stripe_invoice_id="in_without_subscription").exists())
        mock_retrieve_subscription.assert_not_called()

    def test_subscription_webhook_without_customer_does_not_match_blank_customer_record(self) -> None:
        BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
            status="active",
            price_amount="24.90",
            currency="BRL",
            stripe_customer_id="",
            stripe_subscription_id="sub_existing_blank_customer",
            auto_renew=True,
            started_at=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_unrelated_no_customer",
                    "status": "active",
                    "cancel_at_period_end": False,
                    "current_period_end": 1778400000,
                    "start_date": 1775808000,
                    "currency": "brl",
                    "metadata": {
                        "plan_code": BillingService.PLAN_PRO,
                        "billing_cycle": "trial_30",
                    },
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_trial_30_123",
                                    "unit_amount": 2490,
                                }
                            }
                        ]
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
        self.assertFalse(
            BillingSubscription.objects.filter(stripe_subscription_id="sub_unrelated_no_customer").exists()
        )

    def test_subscription_webhook_without_subscription_id_is_ignored(self) -> None:
        BillingSubscription.objects.create(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="trial_30",
            status="active",
            price_amount="24.90",
            currency="BRL",
            stripe_customer_id="cus_existing_blank_subscription",
            stripe_subscription_id="",
            auto_renew=True,
            started_at=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": "cus_existing_blank_subscription",
                    "status": "active",
                    "cancel_at_period_end": False,
                    "current_period_end": 1778400000,
                    "start_date": 1775808000,
                    "currency": "brl",
                    "metadata": {
                        "owner_id": str(self.user.id),
                        "plan_code": BillingService.PLAN_PRO,
                        "billing_cycle": "trial_30",
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
        self.assertEqual(BillingSubscription.objects.filter(owner=self.user).count(), 1)

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
