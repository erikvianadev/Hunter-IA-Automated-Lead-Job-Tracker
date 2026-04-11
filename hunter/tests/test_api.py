from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

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
                ProviderRunResult(provider="remoteok", success=True),
                ProviderRunResult(provider="indeed", success=False, blocked=True),
            ],
            duplicates_removed=2,
        )
        save_jobs_mock.return_value = PersistenceResult(created=1, updated=1, unchanged=0)

        response = self.client.post(
            "/hunter/api/scrape/?query=Data+Scientist&location=Remote",
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "partial_success")
        self.assertEqual(response.data["providers_run"], ["remoteok", "indeed"])
        self.assertEqual(response.data["providers_succeeded"], ["remoteok"])
        self.assertEqual(response.data["providers_failed"], ["indeed"])
        self.assertEqual(response.data["scraped"], 0)
        self.assertEqual(response.data["saved"], 2)
        self.assertEqual(response.data["duplicates_removed"], 2)
