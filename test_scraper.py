from hunter.scrapers.indeed import IndeedScraper

with IndeedScraper(headless=True) as scraper:
    jobs = scraper.scrape("Data Scientist", "Remote")
    for job in jobs:
        print(job["title"], job["company"])

    print(f"\nTotal jobs: {len(jobs)}")
