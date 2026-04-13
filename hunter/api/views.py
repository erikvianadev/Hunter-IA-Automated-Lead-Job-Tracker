import logging
from collections.abc import Mapping

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hunter.scrape_summary import build_scrape_summary
from hunter.serializers import ScrapeJobsRequestSerializer
from hunter.services.job_aggregation_service import JobAggregationService
from hunter.services.job_persistence_service import JobPersistenceService

logger = logging.getLogger(__name__)

SCRAPE_FAILURE_CODE = "job_search_failed"
SCRAPE_FAILURE_DETAIL = (
    "Nao foi possivel atualizar a busca de vagas agora. Tente novamente em instantes."
)


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
                "scrape_request_completed user=%s status=%s raw_scraped=%d scraped=%d saved=%d providers_failed=%d providers_blocked=%d providers_invalid_response=%d duplicates_removed=%d provider_job_counts=%s",
                request.user.username,
                aggregation.status,
                aggregation.raw_scraped,
                aggregation.scraped,
                persistence.saved,
                len(aggregation.providers_failed),
                len(aggregation.providers_blocked),
                len(aggregation.providers_invalid_response),
                aggregation.duplicates_removed,
                aggregation.provider_job_counts,
            )

            payload = build_scrape_summary(
                aggregation=aggregation,
                saved=persistence.saved,
            )
            if aggregation.status == "error":
                return Response(
                    {
                        **payload,
                        "code": SCRAPE_FAILURE_CODE,
                        "detail": SCRAPE_FAILURE_DETAIL,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            return Response(payload, status=status.HTTP_200_OK)

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
                    "code": SCRAPE_FAILURE_CODE,
                    "detail": SCRAPE_FAILURE_DETAIL,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
