from __future__ import annotations

import re

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import override
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


User = get_user_model()
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


def serialize_error_list(errors) -> list[str]:
    return [str(error) for error in errors]


def serialize_field_errors(errors) -> dict[str, list[str]]:
    field_errors: dict[str, list[str]] = {}
    for field, value in errors.items():
        if isinstance(value, dict):
            nested_messages = [
                message
                for messages in serialize_field_errors(value).values()
                for message in messages
            ]
            if nested_messages:
                field_errors[field] = nested_messages
            continue

        if isinstance(value, (list, tuple)):
            field_errors[field] = [str(item) for item in value]
            continue

        field_errors[field] = [str(value)]
    return field_errors


class ProductTokenObtainPairSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        "no_active_account": "Usuario ou senha nao conferem. Revise seus dados e tente novamente.",
    }


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
        error_messages={
            "blank": "Informe um nome de usuario para continuar.",
            "max_length": "Use no maximo 150 caracteres no nome de usuario.",
        },
    )
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
        error_messages={
            "blank": "Informe uma senha para continuar.",
        },
    )
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
        error_messages={
            "blank": "Confirme sua senha para concluir o cadastro.",
        },
    )

    def validate_username(self, value: str) -> str:
        username = value.strip()
        if not USERNAME_PATTERN.fullmatch(username):
            raise serializers.ValidationError(
                "Use de 3 a 30 caracteres com letras, numeros, ponto, traco ou underscore."
            )

        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError(
                "Esse nome de usuario nao esta disponivel no momento. Tente outra variacao."
            )

        return username

    def validate(self, attrs):
        password = attrs["password"]
        password_confirm = attrs["password_confirm"]

        if password != password_confirm:
            raise serializers.ValidationError(
                {
                    "password_confirm": [
                        "As senhas nao coincidem. Confira e tente novamente."
                    ]
                }
            )

        user = User(username=attrs["username"])
        try:
            with override("pt-br"):
                password_validation.validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"password": serialize_error_list(exc.messages)}
            ) from exc

        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )
