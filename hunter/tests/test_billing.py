from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hunter.services.billing_service import BillingService


class BillingApiTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="billing-user",
            password="secret",
        )
        self.other_user = get_user_model().objects.create_user(
            username="billing-other",
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

    def test_subscribe_creates_paid_subscription_and_invoice(self) -> None:
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
        self.assertEqual(response.data["status"], "active")
        self.assertTrue(response.data["auto_renew"])
        self.assertEqual(response.data["last_invoice"]["status"], "paid")
        self.assertEqual(response.data["last_invoice"]["billing_cycle"], "monthly")

    def test_cancel_marks_subscription_as_canceled_but_keeps_access_window(self) -> None:
        BillingService().subscribe(
            owner=self.user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="yearly",
        )

        response = self.client.post("/hunter/api/billing/cancel/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "canceled")
        self.assertFalse(response.data["auto_renew"])
        self.assertIsNotNone(response.data["canceled_at"])
        self.assertIsNotNone(response.data["expires_at"])

    def test_cancel_returns_error_without_paid_subscription(self) -> None:
        response = self.client.post("/hunter/api/billing/cancel/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("no paid subscription", response.data["detail"].lower())

    def test_billing_is_scoped_to_authenticated_user(self) -> None:
        BillingService().subscribe(
            owner=self.other_user,
            plan_code=BillingService.PLAN_PRO,
            billing_cycle="monthly",
        )

        response = self.client.get("/hunter/api/billing/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subscription"]["plan_code"], BillingService.PLAN_FREE)
