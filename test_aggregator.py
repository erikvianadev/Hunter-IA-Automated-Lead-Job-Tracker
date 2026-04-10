from hunter.core.aggregator import JobAggregator

agg = JobAggregator()

jobs = agg.search("Data Scientist", "Remote")

for job in jobs:
    print(job.title, job.company)

print(f"\nTotal jobs: {len(jobs)}")