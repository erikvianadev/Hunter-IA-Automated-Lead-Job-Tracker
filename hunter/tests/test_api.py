import shutil
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hunter.models.dto import JobResult
from hunter.services.job_aggregation_service import AggregationResult
from hunter.providers.base import ProviderRunResult
from hunter.services.job_persistence_service import PersistenceResult


class ScrapeJobsApiTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="api-user",
            password="secret",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("hunter.api.views.JobPersistenceService.save_jobs")
    @patch("hunter.api.views.JobAggregationService.aggregate")
    def test_returns_summary_payload(self, aggregate_mock, save_jobs_mock) -> None:
        aggregate_mock.return_value = AggregationResult(
            jobs=[],
            provider_results=[
                ProviderRunResult(
                    provider="remotive",
                    success=True,
                    jobs=[
                        JobResult.create(
                            title="Data Scientist",
                            company="Acme",
                            location="Remote",
                            link="https://example.com/jobs/1",
                            source="remotive",
                        )
                    ],
                ),
                ProviderRunResult(
                    provider="indeed",
                    success=False,
                    blocked=True,
                    failure_type="blocked",
                ),
                ProviderRunResult(
                    provider="remoteok",
                    success=False,
                    failure_type="invalid_response",
                ),
            ],
            duplicates_removed=2,
        )
        save_jobs_mock.return_value = PersistenceResult(created=1, updated=1, unchanged=0)

        response = self.client.post(
            "/hunter/api/scrape/?query=Data+Scientist&location=Remote",
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.data.keys()),
            [
                "status",
                "providers_run",
                "providers_succeeded",
                "providers_failed",
                "providers_blocked",
                "providers_invalid_response",
                "provider_job_counts",
                "raw_scraped",
                "scraped",
                "saved",
                "duplicates_removed",
            ],
        )
        self.assertEqual(response.data["status"], "partial_success")
        self.assertEqual(response.data["providers_run"], ["remotive", "indeed", "remoteok"])
        self.assertEqual(response.data["providers_succeeded"], ["remotive"])
        self.assertEqual(response.data["providers_failed"], ["indeed", "remoteok"])
        self.assertEqual(response.data["providers_blocked"], ["indeed"])
        self.assertEqual(response.data["providers_invalid_response"], ["remoteok"])
        self.assertEqual(response.data["provider_job_counts"], {"remotive": 1, "indeed": 0, "remoteok": 0})
        self.assertEqual(response.data["raw_scraped"], 1)
        self.assertEqual(response.data["scraped"], 0)
        self.assertEqual(response.data["saved"], 2)
        self.assertEqual(response.data["duplicates_removed"], 2)


class ProjectHealthEndpointsTests(TestCase):
    @override_settings(SERVE_FRONTEND=False)
    def test_root_endpoint_returns_lightweight_json(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "status": "ok",
                "service": "ia-hunter",
                "database": "ok",
                "frontend": "not_required",
            },
        )

    @override_settings(SERVE_FRONTEND=False)
    def test_health_endpoint_returns_ok_payload(self) -> None:
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "status": "ok",
                "service": "ia-hunter",
                "database": "ok",
                "frontend": "not_required",
            },
        )

    @override_settings(
        SERVE_FRONTEND=True,
        FRONTEND_INDEX_FILE=Path("frontend-build-missing-for-test/index.html"),
    )
    def test_readiness_endpoint_reports_missing_frontend_build(self) -> None:
        response = self.client.get("/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertJSONEqual(
            response.content,
            {
                "status": "error",
                "service": "ia-hunter",
                "database": "ok",
                "frontend": "missing",
            },
        )

    def test_spa_route_serves_built_frontend_when_present(self) -> None:
        workspace_temp_root = Path(__file__).resolve().parents[2] / "tmp_test_frontend_build"
        workspace_temp_root.mkdir(exist_ok=True)
        build_dir = workspace_temp_root / f"build_{uuid4().hex}"
        build_dir.mkdir()
        index_file = build_dir / "index.html"

        try:
            index_file.write_text("<!doctype html><html><body><div id='root'>ok</div></body></html>", encoding="utf-8")

            with override_settings(
                SERVE_FRONTEND=True,
                FRONTEND_BUILD_DIR=build_dir,
                FRONTEND_INDEX_FILE=index_file,
                FRONTEND_ASSETS_DIR=build_dir / "assets",
            ):
                response = self.client.get("/dashboard")
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)
            if workspace_temp_root.exists() and not any(workspace_temp_root.iterdir()):
                workspace_temp_root.rmdir()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<div id='root'>ok</div>", html=False)
