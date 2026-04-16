import os
import shutil
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hunter.choices import ProductEventCategory, ResumeParseStatus
from hunter.models.dto import JobResult
from hunter.models.models import Job, ProductEvent, Resume
from hunter.providers.base import ProviderRunResult
from hunter.services import ProductEventName
from hunter.services.job_aggregation_service import AggregationResult
from hunter.services.job_persistence_service import PersistenceResult
from hunter.tests.test_resumes import TEMP_MEDIA_ROOT, build_docx_bytes


class ProductObservabilityAuthTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_signup_records_account_created_and_first_login_once(self) -> None:
        response = self.client.post(
            "/api/auth/signup/",
            {
                "username": "new-observed-user",
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username="new-observed-user")
        self.assertTrue(
            ProductEvent.objects.filter(
                owner=user,
                category=ProductEventCategory.JOURNEY_MILESTONE,
                event_name=ProductEventName.ACCOUNT_CREATED,
            ).exists()
        )
        self.assertEqual(
            ProductEvent.objects.filter(
                owner=user,
                category=ProductEventCategory.JOURNEY_MILESTONE,
                event_name=ProductEventName.FIRST_LOGIN,
            ).count(),
            1,
        )

        login_response = self.client.post(
            "/api/token/",
            {
                "username": "new-observed-user",
                "password": "SenhaForte123!",
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(
            ProductEvent.objects.filter(
                owner=user,
                category=ProductEventCategory.JOURNEY_MILESTONE,
                event_name=ProductEventName.FIRST_LOGIN,
            ).count(),
            1,
        )

    def test_invalid_login_records_journey_failure(self) -> None:
        get_user_model().objects.create_user(
            username="login-observed-user",
            password="super-secret-123",
        )

        response = self.client.post(
            "/api/token/",
            {
                "username": "login-observed-user",
                "password": "wrong-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        event = ProductEvent.objects.get(event_name=ProductEventName.LOGIN_FAILED)
        self.assertEqual(event.category, ProductEventCategory.JOURNEY_FAILURE)
        self.assertEqual(event.metadata["reason"], "invalid_credentials")


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ProductObservabilityFunnelTests(TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(TEMP_MEDIA_ROOT, exist_ok=True)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="funnel-user",
            password="secret",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_resume_upload_records_uploaded_and_ready_milestones(self) -> None:
        upload = SimpleUploadedFile(
            "resume.docx",
            build_docx_bytes("Jane Doe", "Backend Engineer", "Python Django APIs"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.post(
            "/hunter/api/resumes/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(
                ProductEvent.objects.filter(
                    owner=self.user,
                    category=ProductEventCategory.JOURNEY_MILESTONE,
                ).values_list("event_name", flat=True)
            ),
            {
                ProductEventName.RESUME_UPLOADED,
                ProductEventName.RESUME_READY,
            },
        )

    def test_analysis_and_seniority_record_generation_milestones(self) -> None:
        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/resume.docx",
            original_filename="resume.docx",
            extracted_text=(
                "Jane Doe\n"
                "Backend Engineer\n"
                "Summary\n"
                "Backend engineer with Python, Django, SQL, Docker, and API experience.\n"
                "Experience\n"
                "Built APIs, improved reliability, and worked with production systems.\n"
                "Skills\n"
                "Python, Django, SQL, Docker, APIs, AWS\n"
                "Projects\n"
                "Built a job aggregation platform and analytics dashboard.\n"
                "Links\n"
                "https://github.com/janedoe\n"
            ),
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )

        analysis_response = self.client.post(f"/hunter/api/resumes/{resume.id}/analyze/")
        seniority_response = self.client.post(
            f"/hunter/api/resumes/{resume.id}/assess-seniority/"
        )

        self.assertEqual(analysis_response.status_code, 200)
        self.assertEqual(seniority_response.status_code, 200)
        self.assertTrue(
            ProductEvent.objects.filter(
                owner=self.user,
                event_name=ProductEventName.ANALYSIS_GENERATED,
                category=ProductEventCategory.JOURNEY_MILESTONE,
            ).exists()
        )
        self.assertTrue(
            ProductEvent.objects.filter(
                owner=self.user,
                event_name=ProductEventName.SENIORITY_GENERATED,
                category=ProductEventCategory.JOURNEY_MILESTONE,
            ).exists()
        )

    def test_saving_and_applying_record_first_usage_milestones(self) -> None:
        job = Job.objects.create(
            owner=self.user,
            title="Backend Engineer",
            company_name="Acme",
            location="Remote",
            description="Python Django APIs",
            url="https://example.com/jobs/1",
        )

        save_response = self.client.post(f"/hunter/api/jobs/{job.id}/save/")
        apply_response = self.client.post(f"/hunter/api/jobs/{job.id}/apply/")

        self.assertEqual(save_response.status_code, 201)
        self.assertEqual(apply_response.status_code, 201)
        self.assertTrue(
            ProductEvent.objects.filter(
                owner=self.user,
                event_name=ProductEventName.FIRST_SAVED_JOB,
                category=ProductEventCategory.JOURNEY_MILESTONE,
            ).exists()
        )
        self.assertTrue(
            ProductEvent.objects.filter(
                owner=self.user,
                event_name=ProductEventName.FIRST_APPLICATION,
                category=ProductEventCategory.JOURNEY_MILESTONE,
            ).exists()
        )

    @patch("hunter.api.views.JobPersistenceService.save_jobs")
    @patch("hunter.api.views.JobAggregationService.aggregate")
    def test_job_search_records_milestone_and_degraded_technical_event(
        self,
        aggregate_mock,
        save_jobs_mock,
    ) -> None:
        aggregate_mock.return_value = AggregationResult(
            jobs=[
                JobResult.create(
                    title="Backend Engineer",
                    company="Acme",
                    location="Remote",
                    link="https://example.com/jobs/1",
                    source="remotive",
                )
            ],
            provider_results=[
                ProviderRunResult(
                    provider="remotive",
                    success=True,
                    jobs=[],
                ),
                ProviderRunResult(
                    provider="indeed",
                    success=False,
                    blocked=True,
                    failure_type="blocked",
                ),
            ],
        )
        save_jobs_mock.return_value = PersistenceResult(created=1, updated=0, unchanged=0)

        response = self.client.post(
            "/hunter/api/scrape/?query=Backend+Engineer&location=Remote",
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ProductEvent.objects.filter(
                owner=self.user,
                event_name=ProductEventName.FIRST_JOB_SEARCH,
                category=ProductEventCategory.JOURNEY_MILESTONE,
            ).exists()
        )
        self.assertTrue(
            ProductEvent.objects.filter(
                owner=self.user,
                event_name=ProductEventName.JOB_SEARCH_DEGRADED,
                category=ProductEventCategory.TECHNICAL_FAILURE,
            ).exists()
        )

    @patch("hunter.api.views.JobPersistenceService.save_jobs")
    @patch("hunter.api.views.JobAggregationService.aggregate")
    def test_failed_job_search_records_technical_failure(
        self,
        aggregate_mock,
        save_jobs_mock,
    ) -> None:
        aggregate_mock.return_value = AggregationResult(
            jobs=[],
            provider_results=[
                ProviderRunResult(
                    provider="remotive",
                    success=False,
                    failure_type="invalid_response",
                ),
            ],
        )
        save_jobs_mock.return_value = PersistenceResult(created=0, updated=0, unchanged=0)

        response = self.client.post(
            "/hunter/api/scrape/?query=Backend+Engineer&location=Remote",
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertTrue(
            ProductEvent.objects.filter(
                owner=self.user,
                event_name=ProductEventName.JOB_SEARCH_FAILED,
                category=ProductEventCategory.TECHNICAL_FAILURE,
            ).exists()
        )


class ProductObservabilityEndpointTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="observed-user",
            password="secret",
        )
        self.staff_user = get_user_model().objects.create_user(
            username="staff-user",
            password="secret",
            is_staff=True,
        )

    def test_funnel_summary_is_staff_only_and_groups_events(self) -> None:
        ProductEvent.objects.create(
            owner=self.user,
            event_name=ProductEventName.ACCOUNT_CREATED,
            category=ProductEventCategory.JOURNEY_MILESTONE,
            source="test",
        )
        ProductEvent.objects.create(
            owner=self.user,
            event_name=ProductEventName.RESUME_UPLOAD_FAILED,
            category=ProductEventCategory.JOURNEY_FAILURE,
            source="test",
            metadata={"reason": "invalid_file"},
        )

        regular_client = APIClient()
        regular_client.force_authenticate(user=self.user)
        staff_client = APIClient()
        staff_client.force_authenticate(user=self.staff_user)

        forbidden_response = regular_client.get("/hunter/api/observability/funnel/")
        response = staff_client.get("/hunter/api/observability/funnel/")

        self.assertEqual(forbidden_response.status_code, 403)
        self.assertEqual(response.status_code, 200)
        account_created = next(
            item
            for item in response.data["milestones"]
            if item["event_name"] == ProductEventName.ACCOUNT_CREATED
        )
        self.assertEqual(account_created["users"], 1)
        self.assertEqual(response.data["failures"][0]["category"], ProductEventCategory.JOURNEY_FAILURE)
        self.assertEqual(response.data["failures"][0]["event_name"], ProductEventName.RESUME_UPLOAD_FAILED)
