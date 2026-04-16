from __future__ import annotations

from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.views import exception_handler


def product_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

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

    return response
