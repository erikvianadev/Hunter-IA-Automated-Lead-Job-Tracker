import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from django.contrib.auth import get_user_model

from hunter.core.aggregator import JobAggregator
from hunter.core.persistence import JobPersistence


User = get_user_model()
user = User.objects.first()

agg = JobAggregator()
jobs = agg.search("Data Scientist", "Remote")

print("Scraped:", len(jobs))

saved = JobPersistence().save_jobs(user, jobs)

print("Saved:", len(saved))