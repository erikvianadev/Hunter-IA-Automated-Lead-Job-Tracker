from __future__ import annotations

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .auth_serializers import (
    ProductTokenObtainPairSerializer,
    SignupSerializer,
    serialize_field_errors,
)


class ProductTokenObtainPairView(TokenObtainPairView):
    serializer_class = ProductTokenObtainPairSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "signup_validation_failed",
                    "detail": (
                        "Nao foi possivel concluir o cadastro com esses dados. "
                        "Revise os campos e tente novamente."
                    ),
                    "field_errors": serialize_field_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
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
