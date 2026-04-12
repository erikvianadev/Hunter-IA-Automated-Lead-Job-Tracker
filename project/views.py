from __future__ import annotations

from http import HTTPStatus

from django.conf import settings
from django.db import connections
from django.http import Http404, HttpResponse, JsonResponse
from django.views import View


def frontend_is_ready() -> bool:
    return settings.FRONTEND_INDEX_FILE.exists()


def database_is_ready() -> bool:
    try:
        connections["default"].ensure_connection()
    except Exception:
        return False
    return True


def build_health_payload() -> tuple[dict[str, str], bool]:
    database_ready = database_is_ready()
    frontend_ready = frontend_is_ready() if settings.SERVE_FRONTEND else False
    return (
        {
            "status": "ok" if database_ready else "error",
            "service": "ia-hunter",
            "database": "ok" if database_ready else "unavailable",
            "frontend": "ok" if frontend_ready else ("missing" if settings.SERVE_FRONTEND else "not_required"),
        },
        database_ready,
    )


def build_readiness_payload() -> tuple[dict[str, str], bool]:
    payload, database_ready = build_health_payload()
    frontend_ready = payload["frontend"] in {"ok", "not_required"}
    ready = database_ready and frontend_ready
    payload["status"] = "ok" if ready else "error"
    return (
        payload,
        ready,
    )


class FrontendAppView(View):
    def get(self, request):
        if not settings.SERVE_FRONTEND or not frontend_is_ready():
            raise Http404("Frontend build not available.")
        return HttpResponse(
            settings.FRONTEND_INDEX_FILE.read_text(encoding="utf-8"),
            content_type="text/html; charset=utf-8",
        )


class RootView(View):
    def get(self, request):
        if settings.SERVE_FRONTEND and frontend_is_ready():
            return FrontendAppView().get(request)
        payload, _ = build_health_payload()
        return JsonResponse(payload, status=HTTPStatus.OK)


class HealthView(View):
    def get(self, request):
        payload, ready = build_health_payload()
        return JsonResponse(payload, status=HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE)


class ReadinessView(View):
    def get(self, request):
        payload, ready = build_readiness_payload()
        return JsonResponse(payload, status=HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE)
