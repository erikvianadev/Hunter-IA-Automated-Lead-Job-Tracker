from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hunter.choices import ResumeParseStatus
from hunter.models.models import Job, JobMatch, Resume, SeniorityAssessment


class SeniorityAndMatchingApiTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="sprint4-user",
            password="secret",
        )
        self.other_user = get_user_model().objects.create_user(
            username="sprint4-other",
            password="secret",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.resume = Resume.objects.create(
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
        self.job = Job.objects.create(
            owner=self.user,
            title="Junior Python Developer",
            company_name="Acme",
            location="Remote",
            description="Looking for Python, Django, SQL, Docker and API experience.",
            url="https://example.com/jobs/1",
        )
        self.other_resume = Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/private.docx",
            original_filename="private.docx",
            extracted_text=(
                "Private User\nSummary\nStrong engineer.\nExperience\nSeveral systems.\nSkills\nPython, SQL\n"
            ),
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        self.other_job = Job.objects.create(
            owner=self.other_user,
            title="Senior Data Engineer",
            company_name="OtherCo",
            location="Remote",
            description="Python, Spark, AWS, ETL, leadership.",
            url="https://example.com/jobs/2",
        )

    def test_valid_seniority_assessment(self) -> None:
        response = self.client.post(f"/hunter/api/resumes/{self.resume.id}/assess-seniority/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("internship_score", response.data)
        self.assertIn("junior_score", response.data)
        self.assertIn("mid_score", response.data)
        self.assertIn("senior_score", response.data)
        self.assertIn("freelance_score", response.data)
        self.assertIn("recommended_track", response.data)
        self.assertIn("reasoning", response.data)
        self.assertTrue(SeniorityAssessment.objects.filter(resume=self.resume).exists())

    def test_retrieving_stored_seniority_assessment(self) -> None:
        assessment = SeniorityAssessment.objects.create(
            resume=self.resume,
            internship_score=40,
            junior_score=75,
            mid_score=65,
            senior_score=35,
            freelance_score=60,
            recommended_track="junior",
            reasoning={"explanation": "Junior track fits best."},
        )

        response = self.client.get(f"/hunter/api/resumes/{self.resume.id}/seniority/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], assessment.id)
        self.assertEqual(response.data["recommended_track"], "junior")

    def test_denying_access_to_another_users_resume_seniority(self) -> None:
        SeniorityAssessment.objects.create(
            resume=self.other_resume,
            internship_score=20,
            junior_score=30,
            mid_score=40,
            senior_score=80,
            freelance_score=50,
            recommended_track="senior",
            reasoning={"explanation": "Private assessment."},
        )

        response = self.client.get(f"/hunter/api/resumes/{self.other_resume.id}/seniority/")

        self.assertEqual(response.status_code, 404)

    def test_valid_job_match_creation(self) -> None:
        response = self.client.post(
            f"/hunter/api/jobs/{self.job.id}/match/",
            {"resume_id": self.resume.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("match_score", response.data)
        self.assertIn("strengths", response.data)
        self.assertIn("gaps", response.data)
        self.assertIn("recommendation", response.data)
        self.assertIn("reasoning", response.data)
        self.assertTrue(JobMatch.objects.filter(owner=self.user, resume=self.resume, job=self.job).exists())

    def test_listing_matches_returns_only_owned_matches(self) -> None:
        JobMatch.objects.create(
            owner=self.user,
            resume=self.resume,
            job=self.job,
            match_score=82,
            strengths=["Python and Django overlap."],
            gaps=["Needs more cloud depth."],
            recommendation="Strong match. Prioritize this application.",
            reasoning={"overlapping_skills": ["python", "django"]},
        )
        JobMatch.objects.create(
            owner=self.other_user,
            resume=self.other_resume,
            job=self.other_job,
            match_score=55,
            strengths=["Spark experience."],
            gaps=["Missing leadership signals."],
            recommendation="Moderate match.",
            reasoning={"overlapping_skills": ["python"]},
        )

        response = self.client.get("/hunter/api/matches/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["owner"], self.user.id)

    def test_denying_access_to_another_users_matches(self) -> None:
        other_match = JobMatch.objects.create(
            owner=self.other_user,
            resume=self.other_resume,
            job=self.other_job,
            match_score=55,
            strengths=["Spark experience."],
            gaps=["Missing leadership signals."],
            recommendation="Moderate match.",
            reasoning={"overlapping_skills": ["python"]},
        )

        response = self.client.get(f"/hunter/api/matches/{other_match.id}/")

        self.assertEqual(response.status_code, 404)
