from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hunter.choices import ResumeParseStatus
from hunter.models.models import Job, JobMatch, Resume, ResumeAnalysis, SeniorityAssessment


def throttle_settings(**rates):
    framework_settings = dict(settings.REST_FRAMEWORK)
    framework_settings["DEFAULT_THROTTLE_RATES"] = {
        **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        **rates,
    }
    return framework_settings


class SeniorityAndMatchingApiTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
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
        ResumeAnalysis.objects.create(
            resume=self.resume,
            overall_score=90,
            structure_score=88,
            clarity_score=86,
            market_fit_score=91,
            project_score=84,
            strengths=["Strong Python and Django background."],
            weaknesses=[],
            recommendations=[],
            raw_summary={"projects": ["Job aggregation platform"]},
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
        self.assertIn("decision_class", response.data)
        self.assertIn("decision_label", response.data)
        self.assertIn("evidence_signals", response.data)
        self.assertEqual(response.data["decision_class"], "strong")
        self.assertTrue(response.data["evidence_signals"])
        self.assertTrue(JobMatch.objects.filter(owner=self.user, resume=self.resume, job=self.job).exists())

    def test_match_without_resume_analysis_returns_product_message(self) -> None:
        resume_without_analysis = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/no-analysis.docx",
            original_filename="no-analysis.docx",
            extracted_text="Backend Engineer with Python Django SQL APIs and production systems.",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=False,
        )

        response = self.client.post(
            f"/hunter/api/jobs/{self.job.id}/match/",
            {"resume_id": resume_without_analysis.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Gere a analise do curriculo", response.data["detail"])
        self.assertNotIn("Resume analysis", response.data["detail"])

    @override_settings(REST_FRAMEWORK=throttle_settings(job_match="1/min"))
    def test_job_match_action_is_rate_limited(self) -> None:
        payload = {"resume_id": 999999}

        first_response = self.client.post(
            f"/hunter/api/jobs/{self.job.id}/match/",
            payload,
            format="json",
        )
        second_response = self.client.post(
            f"/hunter/api/jobs/{self.job.id}/match/",
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, 400)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.data["code"], "rate_limited")

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

    def test_match_endpoints_hide_rows_with_cross_owned_links(self) -> None:
        foreign_job_match = JobMatch.objects.create(
            owner=self.user,
            resume=self.resume,
            job=self.other_job,
            match_score=91,
            strengths=["Should stay hidden."],
            gaps=["Foreign job linkage."],
            recommendation="Hidden malformed match.",
            reasoning={"source": "test"},
        )
        foreign_resume_match = JobMatch.objects.create(
            owner=self.user,
            resume=self.other_resume,
            job=self.job,
            match_score=73,
            strengths=["Should also stay hidden."],
            gaps=["Foreign resume linkage."],
            recommendation="Hidden malformed match.",
            reasoning={"source": "test"},
        )

        list_response = self.client.get("/hunter/api/matches/")
        retrieve_job_response = self.client.get(f"/hunter/api/matches/{foreign_job_match.id}/")
        retrieve_resume_response = self.client.get(f"/hunter/api/matches/{foreign_resume_match.id}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 0)
        self.assertEqual(retrieve_job_response.status_code, 404)
        self.assertEqual(retrieve_resume_response.status_code, 404)
