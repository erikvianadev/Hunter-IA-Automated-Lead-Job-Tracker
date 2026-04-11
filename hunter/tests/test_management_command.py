from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from hunter.models.dto import JobResult
from hunter.services.job_aggregation_service import AggregationResult
from hunter.services.job_persistence_service import PersistenceResult


class ScrapeJobsCommandTests(TestCase):
    def setUp(self) -> None:
        get_user_model().objects.create_user(username="command-user", password="secret")

    @patch("hunter.management.commands.scrape_jobs.JobPersistenceService.save_jobs")
    @patch("hunter.management.commands.scrape_jobs.JobAggregationService.aggregate")
    def test_command_exits_cleanly_on_partial_failure(self, aggregate_mock, save_jobs_mock) -> None:
        aggregate_mock.return_value = AggregationResult(
            jobs=[
                JobResult.create(
                    title="Data Scientist",
                    company="Acme",
                    location="Remote",
                    link="https://example.com/jobs/1",
                    source="remoteok",
                )
            ],
            duplicates_removed=1,
        )
        save_jobs_mock.return_value = PersistenceResult(created=1, updated=0, unchanged=0)
        output = StringIO()

        call_command(
            "scrape_jobs",
            query="Data Scientist",
            location="Remote",
            stdout=output,
        )

        self.assertIn("saved=1", output.getvalue())
