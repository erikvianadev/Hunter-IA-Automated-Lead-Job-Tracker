from __future__ import annotations

import logging
from math import ceil

from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def product_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        view_name = context.get("view").__class__.__name__ if context.get("view") else "unknown"
        logger.exception("unhandled_api_exception view=%s", view_name)
        return Response(
            {
                "code": "server_error",
                "detail": "Ocorreu um erro inesperado. Tente novamente em instantes.",
            },
            status=500,
        )

    if isinstance(exc, NotAuthenticated):
        response.data = {
            "code": "authentication_required",
            "detail": "Sua sessao nao foi reconhecida. Entre novamente para continuar.",
        }
        return response

    if isinstance(exc, AuthenticationFailed):
        if context.get("view").__class__.__name__ == "ProductTokenObtainPairView":
            return response

        response.data = {
            "code": "session_invalid",
            "detail": "Sua sessao expirou ou nao pode ser validada. Entre novamente para continuar.",
        }
        return response

    if isinstance(exc, Throttled):
        response.data = {
            "code": "rate_limited",
            "detail": "Muitas tentativas em pouco tempo. Aguarde um instante e tente novamente.",
        }
        if exc.wait is not None:
            response.data["retry_after_seconds"] = ceil(exc.wait)
        return response

    return response
