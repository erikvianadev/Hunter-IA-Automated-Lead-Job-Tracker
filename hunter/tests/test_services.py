from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase

from hunter.models.dto import JobResult
from hunter.providers.base import BaseJobProvider, ProviderBlockedError
from hunter.services.job_aggregation_service import JobAggregationService
from hunter.services.job_deduplication_service import JobDeduplicationService
from hunter.services.job_persistence_service import JobPersistenceService


class StaticProvider(BaseJobProvider):
    name = "static"

    def __init__(self, jobs):
        super().__init__()
        self._jobs = jobs

    def fetch_jobs(self, *, query: str, location: str = "", max_pages: int = 1):
        return list(self._jobs)


class ClosableProvider(StaticProvider):
    def __init__(self, jobs):
        super().__init__(jobs)
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FailingProvider(BaseJobProvider):
    name = "failing"

    def fetch_jobs(self, *, query: str, location: str = "", max_pages: int = 1):
        raise ProviderBlockedError("provider unavailable")


class DeduplicationServiceTests(SimpleTestCase):
    def test_deduplicates_by_url_then_fallback_key(self) -> None:
        jobs = [
            JobResult.create(
                title="Data Scientist",
                company="Acme",
                location="Remote",
                link="https://example.com/jobs/1?b=2&a=1",
                source="remoteok",
            ),
            JobResult.create(
                title="Data Scientist",
                company="Acme",
                location="Remote",
                link="https://example.com/jobs/1?a=1&b=2",
                description="Richer description",
                source="weworkremotely",
            ),
            JobResult.create(
                title="Platform Engineer",
                company="Beta",
                location="Remote",
                link="",
                source="remoteok",
            ),
            JobResult.create(
                title="Platform Engineer",
                company="Beta",
                location="Remote",
                link="",
                description="Same role elsewhere",
                source="indeed",
            ),
        ]

        deduplicated, duplicates_removed = JobDeduplicationService().deduplicate(jobs)

        self.assertEqual(len(deduplicated), 2)
        self.assertEqual(duplicates_removed, 2)


class AggregationServiceTests(SimpleTestCase):
    def test_returns_partial_success_when_one_provider_fails(self) -> None:
        providers = [
            StaticProvider(
                [
                    JobResult.create(
                        title="Data Scientist",
                        company="Acme",
                        location="Remote",
                        link="https://example.com/jobs/1",
                        source="remoteok",
                    )
                ]
            ),
            FailingProvider(),
        ]

        result = JobAggregationService(providers=providers).aggregate(
            query="data scientist",
            location="remote",
        )

        self.assertEqual(result.status, "partial_success")
        self.assertEqual(result.providers_succeeded, ["static"])
        self.assertEqual(result.providers_failed, ["failing"])
        self.assertEqual(result.scraped, 1)

    def test_closes_provider_sessions_after_aggregation(self) -> None:
        provider = ClosableProvider(
            [
                JobResult.create(
                    title="Data Scientist",
                    company="Acme",
                    location="Remote",
                    link="https://example.com/jobs/1",
                    source="remoteok",
                )
            ]
        )

        JobAggregationService(providers=[provider]).aggregate(
            query="data scientist",
            location="remote",
        )

        self.assertTrue(provider.closed)


class PersistenceServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="tester",
            password="secret",
        )

    def test_upserts_existing_jobs_and_tracks_counts(self) -> None:
        service = JobPersistenceService()
        initial = [
            JobResult.create(
                title="Data Scientist",
                company="Acme",
                location="Remote",
                description="First description",
                link="https://example.com/jobs/1",
                source="remoteok",
            )
        ]
        first_result = service.save_jobs(owner=self.user, jobs=initial)

        updated = [
            JobResult.create(
                title="Data Scientist",
                company="Acme",
                location="Remote",
                description="Updated description",
                link="https://example.com/jobs/1",
                source="indeed",
            )
        ]
        second_result = service.save_jobs(owner=self.user, jobs=updated)

        self.assertEqual(first_result.created, 1)
        self.assertEqual(second_result.updated, 1)
        self.assertEqual(second_result.saved, 1)
        self.assertEqual(
            self.user.jobs.get(url="https://example.com/jobs/1").description,
            "Updated description",
        )

    def test_handles_preexisting_duplicate_rows_without_crashing(self) -> None:
        self.user.jobs.create(
            title="Data Scientist",
            company_name="Acme",
            location="Remote",
            description="Older copy",
            url="https://example.com/jobs/duplicate",
        )
        self.user.jobs.create(
            title="Data Scientist",
            company_name="Acme",
            location="Remote",
            description="Another copy",
            url="https://example.com/jobs/duplicate",
        )

        result = JobPersistenceService().save_jobs(
            owner=self.user,
            jobs=[
                JobResult.create(
                    title="Data Scientist",
                    company="Acme",
                    location="Remote",
                    description="Merged description",
                    link="https://example.com/jobs/duplicate",
                    source="remoteok",
                )
            ],
        )

        self.assertEqual(result.updated, 1)
        self.assertEqual(result.saved, 1)
        self.assertEqual(
            self.user.jobs.filter(url="https://example.com/jobs/duplicate").count(),
            2,
        )
        self.assertEqual(
            self.user.jobs.filter(url="https://example.com/jobs/duplicate")
            .order_by("id")
            .first()
            .description,
            "Merged description",
        )
