from typing import List
from django.db import transaction

from hunter.models.dto import JobResult
from hunter.models.models import Job


class JobPersistence:

    @transaction.atomic
    def save_jobs(self, owner, jobs: List[JobResult]):
        created = []

        for job in jobs:
            obj, _ = Job.objects.get_or_create(
                url=job.link,
                defaults={
                    "owner": owner,
                    "title": job.title,
                    "company_name": job.company,
                    "location": job.location,
                    "description": job.description,
                },
            )

            created.append(obj)

        return created