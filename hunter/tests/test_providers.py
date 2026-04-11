import json
from pathlib import Path
from unittest.mock import Mock

from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from hunter.providers.base import (
    BaseJobProvider,
    ProviderBlockedError,
    ProviderInvalidResponseError,
    ProviderParseError,
)
from hunter.providers.indeed import IndeedProvider
from hunter.providers.remoteok import RemoteOKProvider
from hunter.providers.weworkremotely import WeWorkRemotelyProvider


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class ProviderParsingTests(SimpleTestCase):
    def test_remoteok_filters_and_normalizes_jobs(self) -> None:
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json; charset=utf-8"}
        response.encoding = "utf-8"
        response.apparent_encoding = "utf-8"
        response.json.return_value = json.loads(
            (FIXTURES_DIR / "remoteok.json").read_text(encoding="utf-8")
        )
        response.raise_for_status.return_value = None
        session.get.return_value = response

        provider = RemoteOKProvider(session=session)
        jobs = provider.fetch_jobs(query="data scientist", location="remote")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Data Scientist")
        self.assertEqual(jobs[0].source, "remoteok")

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
        self.assertIn("non-JSON", result.error_message)

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

    def test_indeed_detects_blocked_html(self) -> None:
        provider = IndeedProvider(session=Mock())
        html = (FIXTURES_DIR / "indeed_blocked.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        with self.assertRaisesMessage(ProviderBlockedError, "blocked page"):
            provider._extract_jobs_from_soup(soup)


class ProviderClassificationTests(SimpleTestCase):
    def test_provider_parse_error_is_handled_without_traceback_noise(self) -> None:
        class ParseFailureProvider(BaseJobProvider):
            name = "parsefailure"

            def fetch_jobs(self, *, query: str, location: str = "", max_pages: int = 1):
                raise ProviderParseError("bad provider markup")

        result = ParseFailureProvider().run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertFalse(result.blocked)
        self.assertEqual(result.error_message, "bad provider markup")

    def test_provider_invalid_response_is_handled_cleanly(self) -> None:
        class InvalidResponseProvider(BaseJobProvider):
            name = "invalidresponse"

            def fetch_jobs(self, *, query: str, location: str = "", max_pages: int = 1):
                raise ProviderInvalidResponseError("unexpected content type")

        result = InvalidResponseProvider().run(query="data scientist", location="remote")

        self.assertFalse(result.success)
        self.assertFalse(result.blocked)
        self.assertEqual(result.error_message, "unexpected content type")
