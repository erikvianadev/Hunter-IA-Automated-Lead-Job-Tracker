import json
from pathlib import Path
from unittest.mock import Mock

from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from hunter.providers.base import (
    BaseJobProvider,
    FAILURE_BLOCKED,
    FAILURE_INVALID_RESPONSE,
    FAILURE_PARSE_ERROR,
    ProviderBlockedError,
    ProviderConfig,
    ProviderInvalidResponseError,
    ProviderParseError,
)
from hunter.providers.adzuna import AdzunaProvider
from hunter.providers.ashby import AshbyProvider
from hunter.providers.greenhouse import GreenhouseProvider
from hunter.providers.indeed import IndeedProvider
from hunter.providers.lever import LeverProvider
from hunter.providers.remotive import RemotiveProvider
from hunter.providers.remoteok import RemoteOKProvider
from hunter.providers.registry import build_enabled_providers, get_configured_provider_names
from hunter.providers.weworkremotely import WeWorkRemotelyProvider


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def build_json_response(payload: str) -> Mock:
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/json; charset=utf-8"}
    response.encoding = "utf-8"
    response.apparent_encoding = "utf-8"
    response.text = payload
    response.json.return_value = json.loads(payload)
    response.raise_for_status.return_value = None
    return response


class ProviderParsingTests(SimpleTestCase):
    def test_remotive_filters_and_normalizes_jobs(self) -> None:
        payload = (FIXTURES_DIR / "remotive.json").read_text(encoding="utf-8")
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.text = payload
        response.json.return_value = json.loads(payload)
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = RemotiveProvider(session=session)
        jobs = provider.fetch_jobs(query="data scientist", location="worldwide")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Data Scientist")
        self.assertEqual(jobs[0].source, "remotive")

    def test_remotive_invalid_html_response_is_classified_cleanly(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.text = (FIXTURES_DIR / "remotive_invalid.html").read_text(
            encoding="utf-8"
        )
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = RemotiveProvider(session=session)
        result = provider.run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertEqual(result.failure_type, FAILURE_INVALID_RESPONSE)
        self.assertIn("HTML instead of JSON", result.error_message)

    def test_remoteok_filters_and_normalizes_jobs(self) -> None:
        payload = (FIXTURES_DIR / "remoteok.json").read_text(encoding="utf-8")
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.text = payload
        response.json.return_value = json.loads(payload)
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = RemoteOKProvider(session=session)
        jobs = provider.fetch_jobs(query="data scientist", location="remote")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Data Scientist")
        self.assertEqual(jobs[0].source, "remoteok")

    def test_remoteok_accepts_prefixed_json_payloads(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.text = (FIXTURES_DIR / "remoteok_prefixed.json").read_text(
            encoding="utf-8"
        )
        response.json.side_effect = ValueError("invalid json")
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = RemoteOKProvider(session=session)
        jobs = provider.fetch_jobs(query="data scientist", location="remote")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Acme")

    def test_remoteok_invalid_json_response_is_classified_cleanly(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.text = "<html><body>temporarily unavailable</body></html>"
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = RemoteOKProvider(session=session)
        result = provider.run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertFalse(result.blocked)
        self.assertEqual(result.failure_type, FAILURE_INVALID_RESPONSE)
        self.assertIn("non-JSON", result.error_message)

    def test_remoteok_blocked_html_is_classified_cleanly(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.text = "<html><body>Just a moment... verify you are a human</body></html>"
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = RemoteOKProvider(session=session)
        result = provider.run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertTrue(result.blocked)
        self.assertEqual(result.failure_type, FAILURE_BLOCKED)

    def test_weworkremotely_parses_listing_html(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.text = (FIXTURES_DIR / "weworkremotely.html").read_text(encoding="utf-8")
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = WeWorkRemotelyProvider(session=session)
        jobs = provider.fetch_jobs(query="data scientist", location="remote")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Acme")
        self.assertIn("weworkremotely.com", jobs[0].link)

    def test_weworkremotely_403_is_reported_as_blocked(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 403
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        session.get.return_value = response

        provider = WeWorkRemotelyProvider(session=session)
        result = provider.run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertTrue(result.blocked)
        self.assertEqual(result.provider, "weworkremotely")
        self.assertEqual(result.failure_type, FAILURE_BLOCKED)

    def test_indeed_returns_blocked_result_on_403(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 403
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.apparent_encoding = "utf-8"
        response.encoding = "utf-8"
        session.get.return_value = response

        provider = IndeedProvider(session=session)
        result = provider.run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertTrue(result.blocked)
        self.assertEqual(result.provider, "indeed")
        self.assertEqual(result.failure_type, FAILURE_BLOCKED)

    def test_indeed_detects_blocked_html(self) -> None:
        provider = IndeedProvider(session=Mock())
        html = (FIXTURES_DIR / "indeed_blocked.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        with self.assertRaisesMessage(ProviderBlockedError, "blocked page"):
            provider._extract_jobs_from_soup(soup)

    def test_greenhouse_parses_structured_board_payload(self) -> None:
        payload = (FIXTURES_DIR / "greenhouse.json").read_text(encoding="utf-8")
        session = Mock()
        session.get.return_value = build_json_response(payload)

        provider = GreenhouseProvider(
            session=session,
            config=ProviderConfig(
                options={
                    "board_tokens": [
                        {"token": "canonical", "company": "Canonical"},
                    ]
                }
            ),
        )
        jobs = provider.fetch_jobs(query="backend python engineer", location="remote")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Backend Python Engineer")
        self.assertEqual(jobs[0].company, "Canonical")
        self.assertEqual(jobs[0].source, "greenhouse")

    def test_lever_parses_structured_site_payload(self) -> None:
        payload = (FIXTURES_DIR / "lever.json").read_text(encoding="utf-8")
        session = Mock()
        session.get.return_value = build_json_response(payload)

        provider = LeverProvider(
            session=session,
            config=ProviderConfig(
                max_retries=1,
                options={
                    "sites": [
                        {"site": "bighealth", "company": "Big Health"},
                    ]
                }
            ),
        )
        jobs = provider.fetch_jobs(query="backend engineer python", location="remote")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Platform Backend Engineer")
        self.assertEqual(jobs[0].company, "Big Health")
        self.assertEqual(jobs[0].source, "lever")

    def test_ashby_parses_structured_board_payload(self) -> None:
        payload = (FIXTURES_DIR / "ashby.json").read_text(encoding="utf-8")
        session = Mock()
        session.get.return_value = build_json_response(payload)

        provider = AshbyProvider(
            session=session,
            config=ProviderConfig(
                options={
                    "job_boards": [
                        {"board": "openai", "company": "OpenAI"},
                    ]
                }
            ),
        )
        jobs = provider.fetch_jobs(query="backend engineer billing", location="remote")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Backend Engineer, Billing Platform")
        self.assertEqual(jobs[0].company, "OpenAI")
        self.assertEqual(jobs[0].source, "ashby")

    def test_lever_isolates_site_failures_and_returns_partial_results(self) -> None:
        payload = (FIXTURES_DIR / "lever.json").read_text(encoding="utf-8")
        good_response = build_json_response(payload)
        blocked_response = Mock()
        blocked_response.status_code = 429
        blocked_response.headers = {"Content-Type": "application/json; charset=utf-8"}
        blocked_response.encoding = "utf-8"
        blocked_response.apparent_encoding = "utf-8"
        blocked_response.text = '{"error":"rate limited"}'

        session = Mock()
        session.get.side_effect = [good_response, blocked_response]

        provider = LeverProvider(
            session=session,
            config=ProviderConfig(
                max_retries=1,
                options={
                    "sites": [
                        {"site": "bighealth", "company": "Big Health"},
                        {"site": "dnb", "company": "Dun & Bradstreet"},
                    ]
                }
            ),
        )

        result = provider.run(query="backend engineer", location="remote")

        self.assertTrue(result.success)
        self.assertEqual(result.provider, "lever")
        self.assertEqual(result.count, 1)
        self.assertEqual(result.jobs[0].company, "Big Health")


class ProviderClassificationTests(SimpleTestCase):
    def test_provider_parse_error_is_handled_without_traceback_noise(self) -> None:
        class ParseFailureProvider(BaseJobProvider):
            name = "parsefailure"

            def fetch_jobs(self, *, query: str, location: str = "", max_pages: int = 1):
                raise ProviderParseError("bad provider markup")

        result = ParseFailureProvider().run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertFalse(result.blocked)
        self.assertEqual(result.failure_type, FAILURE_PARSE_ERROR)
        self.assertEqual(result.error_message, "bad provider markup")

    def test_provider_invalid_response_is_handled_cleanly(self) -> None:
        class InvalidResponseProvider(BaseJobProvider):
            name = "invalidresponse"

            def fetch_jobs(self, *, query: str, location: str = "", max_pages: int = 1):
                raise ProviderInvalidResponseError("unexpected content type")

        result = InvalidResponseProvider().run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertFalse(result.blocked)
        self.assertEqual(result.failure_type, FAILURE_INVALID_RESPONSE)
        self.assertEqual(result.error_message, "unexpected content type")


class AdzunaProviderTests(SimpleTestCase):
    def test_adzuna_returns_empty_when_credentials_absent(self) -> None:
        provider = AdzunaProvider(config=ProviderConfig(options={}))
        jobs = provider.fetch_jobs(query="data scientist", location="remote")
        self.assertEqual(jobs, [])

    def test_adzuna_filters_and_normalizes_jobs(self) -> None:
        payload = (FIXTURES_DIR / "adzuna.json").read_text(encoding="utf-8")
        session = Mock()
        session.get.return_value = build_json_response(payload)

        provider = AdzunaProvider(
            session=session,
            config=ProviderConfig(
                options={
                    "app_id": "test_app_id",
                    "app_key": "test_app_key",
                    "countries": ["us"],
                }
            ),
        )
        jobs = provider.fetch_jobs(query="data scientist", location="remote")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Data Scientist")
        self.assertEqual(jobs[0].company, "Acme Analytics")
        self.assertEqual(jobs[0].source, "adzuna")
        self.assertIn("adzuna.com", jobs[0].link)

    def test_adzuna_skips_non_matching_jobs(self) -> None:
        payload = (FIXTURES_DIR / "adzuna.json").read_text(encoding="utf-8")
        session = Mock()
        session.get.return_value = build_json_response(payload)

        provider = AdzunaProvider(
            session=session,
            config=ProviderConfig(
                options={
                    "app_id": "test_app_id",
                    "app_key": "test_app_key",
                    "countries": ["us"],
                }
            ),
        )
        jobs = provider.fetch_jobs(query="frontend engineer", location="")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Frontend Engineer")

    def test_adzuna_run_classifies_failure_cleanly(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.text = "<html><body>Service Unavailable</body></html>"
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = AdzunaProvider(
            session=session,
            config=ProviderConfig(
                options={
                    "app_id": "test_app_id",
                    "app_key": "test_app_key",
                    "countries": ["us"],
                }
            ),
        )
        result = provider.run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertEqual(result.failure_type, FAILURE_INVALID_RESPONSE)


class ProviderRegistryTests(SimpleTestCase):
    def test_default_provider_order_prioritizes_reliable_sources(self) -> None:
        self.assertEqual(
            get_configured_provider_names(),
            ["remotive", "adzuna", "greenhouse", "lever", "remoteok", "ashby", "weworkremotely", "indeed"],
        )

    def test_disabled_providers_are_skipped(self) -> None:
        # adzuna is disabled when ADZUNA_APP_ID env var is not set (default in CI/local).
        # ashby and weworkremotely are paused in beta. indeed stays disabled.
        providers = build_enabled_providers()

        self.assertEqual(
            [provider.name for provider in providers],
            ["remotive", "greenhouse", "lever", "remoteok"],
        )
