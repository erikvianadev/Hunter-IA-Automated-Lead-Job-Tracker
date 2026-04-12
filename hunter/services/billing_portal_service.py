from __future__ import annotations

from .billing_service import BillingService


class BillingPortalService:
    def __init__(self, *, billing_service: BillingService | None = None) -> None:
        self.billing_service = billing_service or BillingService()

    def build_overview(self, *, owner) -> dict[str, object]:
        subscription = self.billing_service.get_subscription(owner=owner)
        plans = self.billing_service.list_plans(owner=owner)
        return {
            "subscription": subscription,
            "plans": plans,
        }
