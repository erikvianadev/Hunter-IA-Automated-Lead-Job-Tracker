from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


def throttle_settings(**rates):
    framework_settings = dict(settings.REST_FRAMEWORK)
    framework_settings["DEFAULT_THROTTLE_RATES"] = {
        **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        **rates,
    }
    return framework_settings


class AuthApiTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="existing-user",
            password="super-secret-123",
        )

    def test_signup_creates_user_and_returns_tokens(self) -> None:
        response = self.client.post(
            "/api/auth/signup/",
            {
                "username": "new-user",
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Conta criada com sucesso.")
        self.assertEqual(response.data["user"]["username"], "new-user")
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])
        self.assertTrue(get_user_model().objects.filter(username="new-user").exists())

    def test_signup_returns_field_errors_in_portuguese(self) -> None:
        response = self.client.post(
            "/api/auth/signup/",
            {
                "username": "novo-usuario",
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "signup_validation_failed")
        self.assertIn("Nao foi possivel concluir o cadastro", response.data["detail"])
        self.assertIn("As senhas nao coincidem", response.data["field_errors"]["password_confirm"][0])

    def test_signup_missing_fields_returns_safe_portuguese_errors(self) -> None:
        response = self.client.post("/api/auth/signup/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "signup_validation_failed")
        self.assertIn("Informe um nome de usuario", response.data["field_errors"]["username"][0])
        self.assertIn("Informe uma senha", response.data["field_errors"]["password"][0])
        self.assertIn("Confirme sua senha", response.data["field_errors"]["password_confirm"][0])

    def test_signup_validates_username_format(self) -> None:
        response = self.client.post(
            "/api/auth/signup/",
            {
                "username": "ab",
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Use de 3 a 30 caracteres", response.data["field_errors"]["username"][0])

    def test_signup_handles_unavailable_username_without_raw_backend_message(self) -> None:
        response = self.client.post(
            "/api/auth/signup/",
            {
                "username": self.user.username,
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "signup_validation_failed")
        self.assertIn("nao esta disponivel", response.data["field_errors"]["username"][0].lower())

    def test_login_invalid_credentials_returns_safe_portuguese_message(self) -> None:
        response = self.client.post(
            "/api/token/",
            {
                "username": self.user.username,
                "password": "wrong-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data["detail"],
            "Usuario ou senha nao conferem. Revise seus dados e tente novamente.",
        )

    def test_login_accepts_username_case_variation_without_leaking_lookup_state(self) -> None:
        response = self.client.post(
            "/api/token/",
            {
                "username": "EXISTING-USER",
                "password": "super-secret-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])
        self.assertEqual(response.data["user"]["username"], self.user.username)

    def test_refresh_invalid_token_returns_safe_session_message(self) -> None:
        response = self.client.post(
            "/api/token/refresh/",
            {"refresh": "not-a-token"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "session_expired")
        self.assertEqual(
            response.data["detail"],
            "Sua sessao expirou. Entre novamente para continuar.",
        )

    @override_settings(REST_FRAMEWORK=throttle_settings(auth_signup="1/min"))
    def test_signup_is_rate_limited_with_safe_portuguese_message(self) -> None:
        first_response = self.client.post("/api/auth/signup/", {}, format="json")
        second_response = self.client.post("/api/auth/signup/", {}, format="json")

        self.assertEqual(first_response.status_code, 400)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.data["code"], "rate_limited")
        self.assertIn("Muitas tentativas", second_response.data["detail"])

    @override_settings(REST_FRAMEWORK=throttle_settings(auth_login="1/min"))
    def test_login_is_rate_limited_with_safe_portuguese_message(self) -> None:
        payload = {
            "username": self.user.username,
            "password": "wrong-password",
        }

        first_response = self.client.post("/api/token/", payload, format="json")
        second_response = self.client.post("/api/token/", payload, format="json")

        self.assertEqual(first_response.status_code, 401)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.data["code"], "rate_limited")
        self.assertIn("Aguarde", second_response.data["detail"])
