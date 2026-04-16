from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hunter.choices import JobApplicationStatus
from hunter.models.models import Job, JobApplication, JobMatch, Resume, SavedJob


class JobWorkflowApiTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="workflow-user",
            password="secret",
        )
        self.other_user = get_user_model().objects.create_user(
            username="workflow-other",
            password="secret",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.job = Job.objects.create(
            owner=self.user,
            title="Backend Engineer",
            company_name="Acme",
            location="Remote",
            description="Python Django APIs",
            url="https://example.com/jobs/1",
        )
        self.other_job = Job.objects.create(
            owner=self.other_user,
            title="Private Role",
            company_name="OtherCo",
            location="Remote",
            description="Private",
            url="https://example.com/jobs/2",
        )

    def test_saving_a_job_creates_saved_job(self) -> None:
        response = self.client.post(f"/hunter/api/jobs/{self.job.id}/save/")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(SavedJob.objects.filter(owner=self.user, job=self.job).exists())
        self.assertEqual(response.data["job"]["id"], self.job.id)

    def test_preventing_duplicate_saved_jobs(self) -> None:
        SavedJob.objects.create(owner=self.user, job=self.job)

        response = self.client.post(f"/hunter/api/jobs/{self.job.id}/save/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SavedJob.objects.filter(owner=self.user, job=self.job).count(), 1)

    def test_unsaving_a_job_removes_saved_job(self) -> None:
        SavedJob.objects.create(owner=self.user, job=self.job)

        response = self.client.delete(f"/hunter/api/jobs/{self.job.id}/save/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(SavedJob.objects.filter(owner=self.user, job=self.job).exists())

    def test_listing_saved_jobs_returns_only_owned_rows(self) -> None:
        SavedJob.objects.create(owner=self.user, job=self.job)
        SavedJob.objects.create(owner=self.other_user, job=self.other_job)

        response = self.client.get("/hunter/api/saved-jobs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["job"]["id"], self.job.id)

    def test_listing_saved_jobs_hides_rows_linked_to_another_users_job(self) -> None:
        SavedJob.objects.create(owner=self.user, job=self.other_job)

        response = self.client.get("/hunter/api/saved-jobs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_creating_application_from_job(self) -> None:
        response = self.client.post(
            f"/hunter/api/jobs/{self.job.id}/apply/",
            {"notes": "Strong fit for my backend profile."},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], JobApplicationStatus.APPLIED)
        self.assertEqual(response.data["notes"], "Strong fit for my backend profile.")
        self.assertTrue(JobApplication.objects.filter(owner=self.user, job=self.job).exists())
        self.assertIsNotNone(response.data["applied_at"])

    def test_updating_application_status(self) -> None:
        application = JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.SAVED,
            notes="Initial note",
        )

        response = self.client.patch(
            f"/hunter/api/applications/{application.id}/",
            {"status": JobApplicationStatus.INTERVIEW},
            format="json",
        )

        application.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(application.status, JobApplicationStatus.INTERVIEW)
        self.assertIsNotNone(application.applied_at)

    def test_storing_notes_on_application_update(self) -> None:
        application = JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.APPLIED,
            notes="Old note",
        )

        response = self.client.patch(
            f"/hunter/api/applications/{application.id}/",
            {"notes": "Updated note after recruiter reply."},
            format="json",
        )

        application.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(application.notes, "Updated note after recruiter reply.")

    def test_listing_applications_returns_only_owned_rows(self) -> None:
        JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.APPLIED,
            notes="Mine",
        )
        JobApplication.objects.create(
            owner=self.other_user,
            job=self.other_job,
            status=JobApplicationStatus.OFFER,
            notes="Other",
        )

        response = self.client.get("/hunter/api/applications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["job"], self.job.id)

    def test_retrieving_one_application_returns_owned_row(self) -> None:
        application = JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.APPLIED,
            notes="Track this",
        )

        response = self.client.get(f"/hunter/api/applications/{application.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], application.id)
        self.assertEqual(response.data["job_title"], self.job.title)
        self.assertEqual(response.data["job_source"], "example.com")

    def test_application_endpoints_hide_rows_linked_to_another_users_job(self) -> None:
        application = JobApplication.objects.create(
            owner=self.user,
            job=self.other_job,
            status=JobApplicationStatus.APPLIED,
            notes="Should stay hidden",
        )

        list_response = self.client.get("/hunter/api/applications/")
        retrieve_response = self.client.get(f"/hunter/api/applications/{application.id}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 0)
        self.assertEqual(retrieve_response.status_code, 404)

    def test_applications_listing_supports_filtering_by_status_and_job(self) -> None:
        second_job = Job.objects.create(
            owner=self.user,
            title="Data Analyst",
            company_name="Beta",
            location="Remote",
            description="SQL dashboards",
            url="https://example.com/jobs/3",
        )
        JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.APPLIED,
            notes="Primary",
        )
        JobApplication.objects.create(
            owner=self.user,
            job=second_job,
            status=JobApplicationStatus.INTERVIEW,
            notes="Interview loop",
        )

        response = self.client.get(
            f"/hunter/api/applications/?status={JobApplicationStatus.INTERVIEW}&job={second_job.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["job"], second_job.id)
        self.assertEqual(response.data["results"][0]["status"], JobApplicationStatus.INTERVIEW)

    def test_applications_listing_supports_company_filter_and_search(self) -> None:
        first_application = JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.APPLIED,
            notes="Backend platform role",
        )
        second_job = Job.objects.create(
            owner=self.user,
            title="Data Analyst",
            company_name="Beta Labs",
            location="Remote",
            description="SQL dashboards",
            url="https://jobs.lever.co/beta/2",
        )
        JobApplication.objects.create(
            owner=self.user,
            job=second_job,
            status=JobApplicationStatus.SAVED,
            notes="Analytics track",
        )

        company_response = self.client.get("/hunter/api/applications/?company_name=Acme")
        search_response = self.client.get("/hunter/api/applications/?search=platform")

        self.assertEqual(company_response.status_code, 200)
        self.assertEqual(company_response.data["count"], 1)
        self.assertEqual(company_response.data["results"][0]["id"], first_application.id)

        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.data["count"], 1)
        self.assertEqual(search_response.data["results"][0]["id"], first_application.id)

    def test_applications_listing_supports_ordering_by_updated_at(self) -> None:
        older = JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.APPLIED,
            notes="Older",
        )
        second_job = Job.objects.create(
            owner=self.user,
            title="Platform Engineer",
            company_name="Gamma",
            location="Remote",
            description="Python APIs",
            url="https://example.com/jobs/4",
        )
        newer = JobApplication.objects.create(
            owner=self.user,
            job=second_job,
            status=JobApplicationStatus.INTERVIEW,
            notes="Newer",
        )
        JobApplication.objects.filter(id=older.id).update(updated_at=timezone.now() - timedelta(days=2))
        JobApplication.objects.filter(id=newer.id).update(updated_at=timezone.now())

        response = self.client.get("/hunter/api/applications/?ordering=-updated_at")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["id"], newer.id)
        self.assertEqual(response.data["results"][1]["id"], older.id)

    def test_ownership_isolation_for_saved_jobs_and_applications(self) -> None:
        other_saved_job = SavedJob.objects.create(owner=self.other_user, job=self.other_job)
        other_application = JobApplication.objects.create(
            owner=self.other_user,
            job=self.other_job,
            status=JobApplicationStatus.APPLIED,
            notes="Private",
        )

        save_response = self.client.post(f"/hunter/api/jobs/{self.other_job.id}/save/")
        apply_response = self.client.post(f"/hunter/api/jobs/{self.other_job.id}/apply/")
        retrieve_response = self.client.get(f"/hunter/api/applications/{other_application.id}/")

        self.assertEqual(save_response.status_code, 404)
        self.assertEqual(apply_response.status_code, 404)
        self.assertEqual(retrieve_response.status_code, 404)
        self.assertTrue(SavedJob.objects.filter(id=other_saved_job.id).exists())

    def test_jobs_listing_supports_location_and_status_filters(self) -> None:
        saved_job = Job.objects.create(
            owner=self.user,
            title="Platform Engineer",
            company_name="Gamma",
            location="Sao Paulo",
            description="Platform and cloud",
            url="https://jobs.lever.co/gamma/123",
        )
        applied_job = Job.objects.create(
            owner=self.user,
            title="Data Engineer",
            company_name="Delta",
            location="Remote Brazil",
            description="Pipelines and SQL",
            url="https://boards.greenhouse.io/delta/jobs/1",
        )
        SavedJob.objects.create(owner=self.user, job=saved_job)
        JobApplication.objects.create(
            owner=self.user,
            job=applied_job,
            status=JobApplicationStatus.APPLIED,
            notes="Tracked",
        )

        location_response = self.client.get("/hunter/api/jobs/?location=Brazil")
        saved_response = self.client.get("/hunter/api/jobs/?status=saved")
        applied_response = self.client.get("/hunter/api/jobs/?status=applied")

        self.assertEqual(location_response.status_code, 200)
        self.assertEqual(location_response.data["count"], 1)
        self.assertEqual(location_response.data["results"][0]["id"], applied_job.id)

        self.assertEqual(saved_response.status_code, 200)
        self.assertEqual(saved_response.data["count"], 1)
        self.assertEqual(saved_response.data["results"][0]["id"], saved_job.id)

        self.assertEqual(applied_response.status_code, 200)
        self.assertEqual(applied_response.data["count"], 1)
        self.assertEqual(applied_response.data["results"][0]["id"], applied_job.id)

    def test_jobs_listing_exposes_source_status_and_current_match(self) -> None:
        SavedJob.objects.create(owner=self.user, job=self.job)
        application = JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.INTERVIEW,
            notes="Recruiter screen booked",
        )
        active_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/backend.pdf",
            label="Backend Resume",
            target_role="Backend Engineer",
            original_filename="backend.pdf",
            extracted_text="Python Django APIs microservices cloud delivery",
            content_type="application/pdf",
            parse_status="completed",
            is_active=True,
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=self.job,
            match_score=82,
            strengths=["Python overlap"],
            gaps=["Add stronger AWS signal"],
            recommendation="Strong match. Prioritize this application.",
            reasoning={
                "source": "test",
                "decision_class": "aplicar_agora",
                "decision_label": "Aplicar agora",
                "evidence_signals": ["Ha aderencia em Python e Django."],
            },
        )

        response = self.client.get("/hunter/api/jobs/")

        self.assertEqual(response.status_code, 200)
        payload = next(item for item in response.data["results"] if item["id"] == self.job.id)
        self.assertEqual(payload["source"], "example.com")
        self.assertTrue(payload["is_saved"])
        self.assertEqual(payload["application_status"], application.status)
        self.assertEqual(payload["application_id"], application.id)
        self.assertEqual(payload["current_match"]["match_score"], 82)
        self.assertEqual(payload["current_match"]["resume_label"], "Backend Resume")
        self.assertEqual(payload["current_match"]["decision_class"], "aplicar_agora")
        self.assertTrue(payload["current_match"]["evidence_signals"])

    def test_applications_listing_exposes_job_context_and_current_match(self) -> None:
        SavedJob.objects.create(owner=self.user, job=self.job)
        application = JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.INTERVIEW,
            notes="Hiring manager chat booked",
        )
        active_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/backend-2.pdf",
            label="Primary Backend Resume",
            target_role="Backend Engineer",
            original_filename="backend-2.pdf",
            extracted_text="Python Django APIs microservices cloud delivery",
            content_type="application/pdf",
            parse_status="completed",
            is_active=True,
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=self.job,
            match_score=88,
            strengths=["Distributed systems overlap"],
            gaps=["Highlight leadership scope"],
            recommendation="Strong fit with a compelling backend profile.",
            reasoning={
                "source": "test",
                "decision_class": "aplicar_agora",
                "decision_label": "Aplicar agora",
                "evidence_signals": ["Ha aderencia em sistemas distribuidos."],
            },
        )

        response = self.client.get("/hunter/api/applications/")

        self.assertEqual(response.status_code, 200)
        payload = next(item for item in response.data["results"] if item["id"] == application.id)
        self.assertEqual(payload["job_source"], "example.com")
        self.assertTrue(payload["job_is_saved"])
        self.assertEqual(payload["job_url"], self.job.url)
        self.assertEqual(payload["job_location"], self.job.location)
        self.assertEqual(payload["current_match"]["match_score"], 88)
        self.assertEqual(payload["current_match"]["resume_label"], "Primary Backend Resume")
        self.assertEqual(payload["current_match"]["decision_label"], "Aplicar agora")
        self.assertEqual(payload["stage_presentation"]["label"], "Entrevista")
        self.assertEqual(payload["next_action"]["title"], "Preparar a proxima conversa")
        self.assertIn("Notas de acompanhamento registradas", payload["recorded_context"])
        self.assertIn("Hiring manager chat booked", payload["notes_highlights"])
        self.assertNotIn("Notas de acompanhamento", payload["missing_context"])

    def test_application_payload_surfaces_missing_operational_context(self) -> None:
        application = JobApplication.objects.create(
            owner=self.user,
            job=self.job,
            status=JobApplicationStatus.APPLIED,
            notes="",
        )

        response = self.client.get(f"/hunter/api/applications/{application.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["next_action"]["title"], "Registrar contexto do envio")
        self.assertIn("Notas de acompanhamento", response.data["missing_context"])
        self.assertIn("Match com curriculo", response.data["missing_context"])
        self.assertEqual(response.data["notes_highlights"], [])
