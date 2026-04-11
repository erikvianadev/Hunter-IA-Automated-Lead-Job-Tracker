import logging
from collections.abc import Mapping

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hunter.serializers import ScrapeJobsRequestSerializer
from hunter.services.job_aggregation_service import JobAggregationService
from hunter.services.job_persistence_service import JobPersistenceService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ScrapeJobsView(APIView):
    """
    POST /hunter/api/scrape/

    Triggers job scraping and persists results to the database.
    Accepts optional query params:
        - query    (default: "Data Scientist")
        - location (default: "Remote")

    Returns:
        {
            "status": "success",
            "scraped": <int>,
            "saved": <int>
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = {key: value for key, value in request.query_params.items()}
        if isinstance(request.data, Mapping):
            payload.update(dict(request.data))
        serializer = ScrapeJobsRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        location = serializer.validated_data["location"]

        logger.info(
            "Scrape triggered by user=%s query=%r location=%r",
            request.user.username,
            query,
            location,
        )

        try:
            aggregation = JobAggregationService().aggregate(query=query, location=location)
            persistence = JobPersistenceService().save_jobs(
                owner=request.user,
                jobs=aggregation.jobs,
            )

            logger.info(
                "scrape_request_completed user=%s status=%s scraped=%d saved=%d providers_failed=%d duplicates_removed=%d",
                request.user.username,
                aggregation.status,
                aggregation.scraped,
                persistence.saved,
                len(aggregation.providers_failed),
                aggregation.duplicates_removed,
            )

            return Response(
                {
                    "status": aggregation.status,
                    "providers_run": aggregation.providers_run,
                    "providers_succeeded": aggregation.providers_succeeded,
                    "providers_failed": aggregation.providers_failed,
                    "scraped": aggregation.scraped,
                    "saved": persistence.saved,
                    "duplicates_removed": aggregation.duplicates_removed,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            logger.exception(
                "Scrape failed for user=%s query=%r location=%r: %s",
                request.user.username,
                query,
                location,
                exc,
            )
            return Response(
                {
                    "status": "error",
                    "detail": "An error occurred while scraping jobs. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
