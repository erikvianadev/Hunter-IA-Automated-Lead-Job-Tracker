from __future__ import annotations

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .auth_serializers import (
    ProductTokenObtainPairSerializer,
    SignupSerializer,
    serialize_field_errors,
)
from hunter.services import ProductEventName, ProductObservabilityService


class ProductTokenObtainPairView(TokenObtainPairView):
    serializer_class = ProductTokenObtainPairSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


class ProductTokenRefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            return Response(
                {
                    "code": "session_refresh_missing",
                    "detail": "Nao foi possivel renovar sua sessao. Entre novamente para continuar.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (InvalidToken, TokenError):
            return Response(
                {
                    "code": "session_expired",
                    "detail": "Sua sessao expirou. Entre novamente para continuar.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            field_errors = serialize_field_errors(serializer.errors)
            ProductObservabilityService().record_journey_failure(
                event_name=ProductEventName.ACCOUNT_CREATION_FAILED,
                source="auth.signup",
                metadata={
                    "reason": "validation_failed",
                    "fields": sorted(field_errors.keys()),
                },
            )
            return Response(
                {
                    "code": "signup_validation_failed",
                    "detail": (
                        "Nao foi possivel concluir o cadastro com esses dados. "
                        "Revise os campos e tente novamente."
                    ),
                    "field_errors": field_errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            ProductObservabilityService().record_journey_failure(
                event_name=ProductEventName.ACCOUNT_CREATION_FAILED,
                source="auth.signup",
                metadata={"reason": "integrity_error"},
            )
            return Response(
                {
                    "code": "signup_unavailable",
                    "detail": (
                        "Nao foi possivel concluir o cadastro agora. "
                        "Revise os dados e tente novamente."
                    ),
                    "field_errors": {
                        "username": [
                            "Esse nome de usuario nao esta disponivel no momento. Tente outra variacao."
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        observability = ProductObservabilityService()
        observability.record_milestone(
            owner=user,
            event_name=ProductEventName.ACCOUNT_CREATED,
            source="auth.signup",
        )
        observability.record_milestone(
            owner=user,
            event_name=ProductEventName.FIRST_LOGIN,
            source="auth.signup",
        )
        return Response(
            {
                "message": "Conta criada com sucesso.",
                "user": {
                    "id": user.id,
                    "username": user.get_username(),
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )
