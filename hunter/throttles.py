from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle


class ProductScopedRateThrottle(ScopedRateThrottle):
    def get_rate(self):
        return settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}).get(self.scope)
