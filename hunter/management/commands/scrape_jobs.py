from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from hunter.providers.registry import build_enabled_providers, get_unknown_provider_names
from hunter.services.job_aggregation_service import JobAggregationService
from hunter.services.job_persistence_service import JobPersistenceService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scrape jobs from enabled providers and optionally persist them for a user."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--query", default="Data Scientist")
        parser.add_argument("--location", default="Remote")
        parser.add_argument("--username", default=None)
        parser.add_argument(
            "--providers",
            default="",
            help="Comma-separated provider names to run instead of the configured defaults.",
        )

    def handle(self, *args, **options):
        query = options["query"]
        location = options["location"]
        username = options["username"]
        provider_names = [
            name.strip().lower()
            for name in (options.get("providers") or "").split(",")
            if name.strip()
        ]

        unknown_provider_names = get_unknown_provider_names(provider_names)
        if unknown_provider_names:
            raise CommandError(
                "Unknown providers: {providers}".format(
                    providers=", ".join(sorted(unknown_provider_names))
                )
            )

        providers = build_enabled_providers(provider_names or None)
        aggregation = JobAggregationService(providers=providers).aggregate(
            query=query,
            location=location,
        )

        saved = 0
        user_model = get_user_model()
        owner = None
        if username:
            try:
                owner = user_model.objects.get(username=username)
            except user_model.DoesNotExist as exc:
                raise CommandError(f"User '{username}' does not exist.") from exc
        else:
            owner = user_model.objects.order_by("id").first()

        if owner is not None:
            persistence = JobPersistenceService().save_jobs(owner=owner, jobs=aggregation.jobs)
            saved = persistence.saved

        logger.info(
            "scrape_command_completed status=%s providers_run=%s providers_succeeded=%s providers_failed=%s providers_blocked=%s providers_invalid_response=%s scraped=%d saved=%d duplicates_removed=%d",
            aggregation.status,
            aggregation.providers_run,
            aggregation.providers_succeeded,
            aggregation.providers_failed,
            aggregation.providers_blocked,
            aggregation.providers_invalid_response,
            aggregation.scraped,
            saved,
            aggregation.duplicates_removed,
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "status={status} providers_run={providers_run} "
                    "providers_succeeded={providers_succeeded} "
                    "providers_failed={providers_failed} "
                    "providers_blocked={providers_blocked} "
                    "providers_invalid_response={providers_invalid_response} "
                    "scraped={scraped} saved={saved} "
                    "duplicates_removed={duplicates_removed}"
                ).format(
                    status=aggregation.status,
                    providers_run=",".join(aggregation.providers_run),
                    providers_succeeded=",".join(aggregation.providers_succeeded),
                    providers_failed=",".join(aggregation.providers_failed),
                    providers_blocked=",".join(aggregation.providers_blocked),
                    providers_invalid_response=",".join(
                        aggregation.providers_invalid_response
                    ),
                    scraped=aggregation.scraped,
                    saved=saved,
                    duplicates_removed=aggregation.duplicates_removed,
                )
            )
        )
