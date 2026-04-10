from hunter.scrapers.indeed import IndeedScraper

scraper = IndeedScraper(
    headless=False,
    fetch_descriptions=False,
    debug=True
)

jobs = scraper.scrape(
    query="Python",
    location="Remote",
    max_pages=3
)

for job in jobs:
    print(job["title"], job["company"])

print(f"\nTotal jobs: {len(jobs)}")