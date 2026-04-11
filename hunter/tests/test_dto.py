from django.test import SimpleTestCase

from hunter.models.dto import JobResult


class JobResultTests(SimpleTestCase):
    def test_is_valid_allows_blank_optional_fields(self) -> None:
        job = JobResult.create(
            title="Data Engineer",
            company="Acme",
            location="",
            description="",
            link="https://example.com/job",
            source="remoteok",
        )

        self.assertTrue(job.is_valid())

    def test_canonicalizes_link_and_builds_fallback_key(self) -> None:
        job = JobResult.create(
            title=" Data Engineer ",
            company=" Acme ",
            location=" Remote ",
            link="HTTPS://Example.com/jobs/123/?b=2&a=1",
        )

        self.assertEqual(job.link, "https://example.com/jobs/123?a=1&b=2")
        self.assertEqual(
            job.deduplication_key(),
            "https://example.com/jobs/123?a=1&b=2",
        )

    def test_merge_prefers_richer_duplicate_data(self) -> None:
        original = JobResult.create(
            title="Data Engineer",
            company="Acme",
            location="Remote",
            description="Short text",
            link="https://example.com/job/1",
            source="remoteok",
        )
        duplicate = JobResult.create(
            title="Senior Data Engineer",
            company="Acme Inc",
            location="Remote - Brazil",
            description="Longer, richer description for the same role.",
            link="https://example.com/job/1",
            source="indeed",
        )

        original.merge(duplicate)

        self.assertEqual(original.title, "Senior Data Engineer")
        self.assertEqual(original.company, "Acme Inc")
        self.assertEqual(original.location, "Remote - Brazil")
        self.assertEqual(
            original.description,
            "Longer, richer description for the same role.",
        )
