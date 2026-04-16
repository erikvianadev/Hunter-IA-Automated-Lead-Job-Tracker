import os
import shutil

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hunter.models.models import Resume, ResumeAnalysis


TEMP_MEDIA_ROOT = os.path.join(os.getcwd(), "test_media_analysis")


def throttle_settings(**rates):
    framework_settings = dict(settings.REST_FRAMEWORK)
    framework_settings["DEFAULT_THROTTLE_RATES"] = {
        **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        **rates,
    }
    return framework_settings


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ResumeAnalysisApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(TEMP_MEDIA_ROOT, exist_ok=True)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="analysis-user",
            password="secret",
        )
        self.other_user = get_user_model().objects.create_user(
            username="analysis-other",
            password="secret",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_analyzing_valid_resume_returns_expected_fields(self) -> None:
        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/resume.docx",
            original_filename="resume.docx",
            extracted_text=(
                "Jane Doe\n"
                "Data Analyst\n"
                "Summary\n"
                "Analytical professional with Python and SQL experience building dashboards.\n"
                "Experience\n"
                "Built reporting pipelines and improved KPI visibility.\n"
                "Skills\n"
                "Python, SQL, Tableau\n"
                "Projects\n"
                "Customer churn dashboard with automated refreshes.\n"
                "Links\n"
                "https://github.com/janedoe\n"
            ),
            parse_status="completed",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.post(f"/hunter/api/resumes/{resume.id}/analyze/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("overall_score", response.data)
        self.assertIn("structure_score", response.data)
        self.assertIn("clarity_score", response.data)
        self.assertIn("market_fit_score", response.data)
        self.assertIn("project_score", response.data)
        self.assertIn("strengths", response.data)
        self.assertIn("weaknesses", response.data)
        self.assertIn("recommendations", response.data)
        self.assertIn("raw_summary", response.data)
        self.assertIn("working_signals", response.data)
        self.assertIn("missing_signals", response.data)
        self.assertIn("priority_actions", response.data)
        self.assertIn("priority_summary", response.data)
        self.assertTrue(response.data["priority_actions"])
        self.assertIn("impact", response.data["priority_actions"][0])
        self.assertTrue(ResumeAnalysis.objects.filter(resume=resume).exists())

    def test_retrieving_existing_analysis_returns_saved_analysis(self) -> None:
        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/resume.docx",
            original_filename="resume.docx",
            extracted_text="Useful resume text for analysis with summary skills experience projects.",
            parse_status="completed",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        analysis = ResumeAnalysis.objects.create(
            resume=resume,
            overall_score=80,
            structure_score=78,
            clarity_score=82,
            market_fit_score=79,
            project_score=81,
            strengths=["Clear skills section"],
            weaknesses=["Needs stronger summary"],
            recommendations=["Add measurable impact"],
            raw_summary={"parsed_resume": {"headline": "Jane Doe"}},
        )

        response = self.client.get(f"/hunter/api/resumes/{resume.id}/analysis/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], analysis.id)
        self.assertEqual(response.data["overall_score"], 80)

    def test_denying_access_to_another_users_analysis(self) -> None:
        resume = Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/private.docx",
            original_filename="private.docx",
            extracted_text="Private resume text with enough content for analysis and parsing.",
            parse_status="completed",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        ResumeAnalysis.objects.create(
            resume=resume,
            overall_score=70,
            structure_score=70,
            clarity_score=70,
            market_fit_score=70,
            project_score=70,
            strengths=[],
            weaknesses=[],
            recommendations=[],
            raw_summary={},
        )

        response = self.client.get(f"/hunter/api/resumes/{resume.id}/analysis/")

        self.assertEqual(response.status_code, 404)

    def test_empty_extracted_text_fails_gracefully(self) -> None:
        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/empty.docx",
            original_filename="empty.docx",
            extracted_text="",
            parse_status="completed",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.post(f"/hunter/api/resumes/{resume.id}/analyze/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    @override_settings(REST_FRAMEWORK=throttle_settings(resume_analysis="1/min"))
    def test_resume_analysis_action_is_rate_limited(self) -> None:
        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/empty.docx",
            original_filename="empty.docx",
            extracted_text="",
            parse_status="completed",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        first_response = self.client.post(f"/hunter/api/resumes/{resume.id}/analyze/")
        second_response = self.client.post(f"/hunter/api/resumes/{resume.id}/analyze/")

        self.assertEqual(first_response.status_code, 400)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.data["code"], "rate_limited")

    def test_missing_analysis_returns_not_found(self) -> None:
        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/no-analysis.docx",
            original_filename="no-analysis.docx",
            extracted_text="This resume has enough text but has not been analyzed yet.",
            parse_status="completed",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.get(f"/hunter/api/resumes/{resume.id}/analysis/")

        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.data)
