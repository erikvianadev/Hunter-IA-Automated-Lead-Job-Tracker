import logging

from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hunter.core.aggregator import JobAggregator
from hunter.core.persistence import JobPersistence

logger = logging.getLogger(__name__)

User = get_user_model()


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
        query = request.query_params.get("query", "Data Scientist")
        location = request.query_params.get("location", "Remote")

        logger.info(
            "Scrape triggered by user=%s query=%r location=%r",
            request.user.username,
            query,
            location,
        )

        try:
            aggregator = JobAggregator()
            jobs = aggregator.search(query=query, location=location)
            scraped_count = len(jobs)

            logger.info("Scraped %d jobs (query=%r, location=%r)", scraped_count, query, location)

            persistence = JobPersistence()
            saved_objects = persistence.save_jobs(owner=request.user, jobs=jobs)
            saved_count = len(saved_objects)

            logger.info(
                "Persisted %d new jobs for user=%s",
                saved_count,
                request.user.username,
            )

            return Response(
                {
                    "status": "success",
                    "scraped": scraped_count,
                    "saved": saved_count,
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
