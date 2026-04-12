from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse


class SimpleCORSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")
        allow_origin = self._get_allow_origin(origin)

        if request.method == "OPTIONS" and allow_origin:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if allow_origin:
            response["Access-Control-Allow-Origin"] = allow_origin
            response["Vary"] = self._merge_vary_header(response.get("Vary"), "Origin")
            response["Access-Control-Allow-Methods"] = ", ".join(settings.CORS_ALLOWED_METHODS)
            response["Access-Control-Allow-Headers"] = ", ".join(settings.CORS_ALLOWED_HEADERS)
            if settings.CORS_ALLOW_CREDENTIALS:
                response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Max-Age"] = "86400"

        return response

    def _get_allow_origin(self, origin: str | None) -> str | None:
        if not origin:
            return None
        if settings.CORS_ALLOW_ALL_ORIGINS:
            return "*"
        if origin in settings.CORS_ALLOWED_ORIGINS:
            return origin
        return None

    @staticmethod
    def _merge_vary_header(existing_value: str | None, new_value: str) -> str:
        values = {part.strip() for part in (existing_value or "").split(",") if part.strip()}
        values.add(new_value)
        return ", ".join(sorted(values))
