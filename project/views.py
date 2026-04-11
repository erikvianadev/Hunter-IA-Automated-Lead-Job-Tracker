from __future__ import annotations

from django.db import connections
from django.http import JsonResponse
from django.views import View


class RootView(View):
    def get(self, request):
        return JsonResponse(
            {
                "status": "ok",
                "service": "ia-hunter",
            }
        )


class HealthView(View):
    def get(self, request):
        try:
            connections["default"].ensure_connection()
        except Exception:
            return JsonResponse(
                {
                    "status": "error",
                    "database": "unavailable",
                },
                status=503,
            )

        return JsonResponse(
            {
                "status": "ok",
                "database": "ok",
            }
        )
