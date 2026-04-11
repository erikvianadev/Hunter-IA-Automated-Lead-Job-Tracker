from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from hunter.choices import JobApplicationStatus
from hunter.models.models import Job, JobApplication, SavedJob


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
