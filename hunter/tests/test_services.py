from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase

from hunter.models.dto import JobResult
from hunter.providers.base import (
    BaseJobProvider,
    FAILURE_BLOCKED,
    FAILURE_INVALID_RESPONSE,
    FAILURE_UNAVAILABLE,
    ProviderBlockedError,
    ProviderInvalidResponseError,
    ProviderUnavailableError,
)
from hunter.scrape_summary import build_scrape_summary
from hunter.services.job_aggregation_service import JobAggregationService
from hunter.services.job_deduplication_service import JobDeduplicationService
from hunter.services.job_persistence_service import JobPersistenceService, PersistenceResult


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


class InvalidResponseProvider(BaseJobProvider):
    name = "invalid"

    def fetch_jobs(self, *, query: str, location: str = "", max_pages: int = 1):
        raise ProviderInvalidResponseError("bad payload")


class UnavailableProvider(BaseJobProvider):
    name = "unavailable"

    def fetch_jobs(self, *, query: str, location: str = "", max_pages: int = 1):
        raise ProviderUnavailableError("network timeout")


class DeduplicationServiceTests(SimpleTestCase):
    def test_deduplicates_by_url_then_fallback_key(self) -> None:
        jobs = [
            JobResult.create(
                title="Data Scientist",
                company="Acme",
                location="Remote",
                link="https://www.example.com/jobs/1?b=2&a=1&utm_source=newsletter",
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
                location="Worldwide",
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
        self.assertEqual(result.providers_blocked, ["failing"])
        self.assertEqual(result.providers_invalid_response, [])
        self.assertEqual(result.provider_job_counts, {"static": 1, "failing": 0})
        self.assertEqual(result.raw_scraped, 1)
        self.assertEqual(result.scraped, 1)

    def test_tracks_invalid_response_summary_separately(self) -> None:
        providers = [
            StaticProvider(
                [
                    JobResult.create(
                        title="Data Scientist",
                        company="Acme",
                        location="Remote",
                        link="https://example.com/jobs/1",
                        source="remotive",
                    )
                ]
            ),
            InvalidResponseProvider(),
        ]

        result = JobAggregationService(providers=providers).aggregate(
            query="data scientist",
            location="remote",
        )

        self.assertEqual(result.providers_failed, ["invalid"])
        self.assertEqual(result.providers_blocked, [])
        self.assertEqual(result.providers_invalid_response, ["invalid"])
        self.assertEqual(result.provider_job_counts, {"static": 1, "invalid": 0})
        self.assertEqual(result.raw_scraped, 1)

    def test_tracks_unavailable_provider_separately(self) -> None:
        result = JobAggregationService(providers=[UnavailableProvider()]).aggregate(
            query="data scientist",
            location="remote",
        )

        self.assertEqual(result.status, "total_failure")
        self.assertEqual(result.providers_unavailable, ["unavailable"])
        self.assertEqual(result.provider_failure_counts, {FAILURE_UNAVAILABLE: 1})

    def test_filters_weak_provider_payloads_before_visible_results(self) -> None:
        result = JobAggregationService(
            providers=[
                StaticProvider(
                    [
                        JobResult.create(
                            title="Backend Engineer",
                            company="Acme",
                            location="Remote",
                            link="https://example.com/jobs/1",
                            source="remotive",
                        ),
                        JobResult.create(
                            title="Untitled",
                            company="",
                            location="",
                            link="",
                            source="remotive",
                        ),
                    ]
                )
            ]
        ).aggregate(query="backend engineer", location="remote")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.raw_scraped, 2)
        self.assertEqual(result.scraped, 1)
        self.assertEqual(result.quality_filtered, 1)
        self.assertEqual(result.quality_issue_counts["missing_company"], 1)
        self.assertEqual(result.quality_issue_counts["missing_actionable_link"], 1)

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

    def test_scrape_summary_includes_provider_counts_and_raw_scraped(self) -> None:
        aggregation = JobAggregationService(
            providers=[
                StaticProvider(
                    [
                        JobResult.create(
                            title="Backend Engineer",
                            company="Canonical",
                            location="Remote",
                            link="https://example.com/jobs/1",
                            source="greenhouse",
                        ),
                        JobResult.create(
                            title="Backend Engineer",
                            company="Canonical",
                            location="Remote",
                            link="https://example.com/jobs/1",
                            source="greenhouse",
                        ),
                    ]
                ),
                InvalidResponseProvider(),
            ]
        ).aggregate(query="backend engineer", location="remote")

        summary = build_scrape_summary(
            aggregation=aggregation,
            persistence=PersistenceResult(created=1),
        )

        self.assertEqual(summary["provider_job_counts"], {"static": 2, "invalid": 0})
        self.assertEqual(summary["raw_scraped"], 2)
        self.assertEqual(summary["scraped"], 1)
        self.assertEqual(summary["saved"], 1)
        self.assertEqual(summary["status"], "partial_success")
        self.assertEqual(summary["status_label"], "Coleta parcial")


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

    def test_skips_bad_rows_without_losing_good_rows(self) -> None:
        result = JobPersistenceService().save_jobs(
            owner=self.user,
            jobs=[
                JobResult.create(
                    title="Backend Engineer",
                    company="Acme",
                    location="Remote",
                    description="Good row",
                    link="https://example.com/jobs/good",
                    source="remotive",
                ),
                JobResult.create(
                    title="",
                    company="",
                    location="Remote",
                    description="Bad row",
                    link="",
                    source="remotive",
                ),
                object(),
            ],
        )

        self.assertEqual(result.created, 1)
        self.assertEqual(result.skipped, 2)
        self.assertEqual(result.saved, 1)
        self.assertEqual(self.user.jobs.count(), 1)
