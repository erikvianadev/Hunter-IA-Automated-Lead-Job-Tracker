from pathlib import Path

from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from hunter.scrapers.base import JobResult
from hunter.scrapers.indeed import IndeedScraper


class JobResultTests(SimpleTestCase):
    def test_is_valid_allows_blank_optional_fields(self) -> None:
        job = JobResult.create(
            title="Data Engineer",
            company="Acme",
            location="",
            description="",
            link="https://example.com/job",
        )

        self.assertTrue(job.is_valid())


class IndeedScraperExtractionTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.fixture_path = Path(__file__).resolve().parent.parent / "debug_indeed.html"
        cls.page_source = cls.fixture_path.read_text(encoding="utf-8", errors="ignore")
        cls.soup = BeautifulSoup(cls.page_source, "html.parser")

    def setUp(self) -> None:
        self.scraper = IndeedScraper(headless=True, fetch_descriptions=False)
        self.addCleanup(self.scraper.close)

    def test_parse_current_indeed_cards(self) -> None:
        raw_cards = self.scraper._parse_jobs(self.soup)

        self.assertGreater(len(raw_cards), 0)

        first_job = self.scraper._normalize(raw_cards[0])
        self.assertEqual(first_job["title"], "Research Scientist")
        self.assertEqual(first_job["company"], "Humana")
        self.assertEqual(first_job["location"], "Remote")
        self.assertIn("viewjob?jk=", first_job["link"])

    def test_extract_jobs_from_bootstrap_payload(self) -> None:
        jobs = self.scraper._extract_jobs_from_bootstrap_data(self.page_source)

        self.assertGreater(len(jobs), 0)
        self.assertTrue(all(job.is_valid() for job in jobs))
        self.assertTrue(any(job["title"] == "Research Scientist" for job in jobs))
