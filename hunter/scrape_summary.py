from __future__ import annotations

from hunter.services.job_aggregation_service import AggregationResult


def build_scrape_summary(*, aggregation: AggregationResult, saved: int) -> dict[str, object]:
    return {
        "status": aggregation.status,
        "providers_run": aggregation.providers_run,
        "providers_succeeded": aggregation.providers_succeeded,
        "providers_failed": aggregation.providers_failed,
        "providers_blocked": aggregation.providers_blocked,
        "providers_invalid_response": aggregation.providers_invalid_response,
        "provider_job_counts": aggregation.provider_job_counts,
        "raw_scraped": aggregation.raw_scraped,
        "scraped": aggregation.scraped,
        "saved": saved,
        "duplicates_removed": aggregation.duplicates_removed,
    }
