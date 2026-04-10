from typing import List

from hunter.models.dto import JobResult
from hunter.scrapers.indeed import IndeedScraper


class JobAggregator:
    """
    Central job aggregation engine
    """

    def __init__(self):
        self.scrapers = [
            IndeedScraper(headless=True),
        ]

    def search(self, query: str, location: str = "") -> List[JobResult]:
        results: List[JobResult] = []

        for scraper in self.scrapers:
            try:
                print("Running scraper:", scraper.__class__.__name__)

                jobs = scraper.scrape(query, location)

                print("Found jobs:", len(jobs))

                results.extend(jobs)

            except Exception as e:
                print(f"Scraper error: {scraper.__class__.__name__}: {e}")

        return self._deduplicate(results)

    def _deduplicate(self, jobs: List[JobResult]) -> List[JobResult]:
        seen = set()
        unique = []

        for job in jobs:
            key = job.link

            if key not in seen:
                seen.add(key)
                unique.append(job)

        return unique