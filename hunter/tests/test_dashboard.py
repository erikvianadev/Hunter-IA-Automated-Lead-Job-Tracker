from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hunter.choices import ResumeParseStatus
from hunter.models.models import Job, JobMatch, Resume, ResumeAnalysis, SeniorityAssessment


class DashboardApiTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="dashboard-user",
            password="secret",
        )
        self.other_user = get_user_model().objects.create_user(
            username="dashboard-other",
            password="secret",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_dashboard_returns_consolidated_active_resume_data(self) -> None:
        active_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/active.docx",
            original_filename="active.docx",
            extracted_text="Python Django SQL Docker APIs",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/old.docx",
            original_filename="old.docx",
            extracted_text="old resume",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=False,
        )
        analysis = ResumeAnalysis.objects.create(
            resume=active_resume,
            overall_score=88,
            structure_score=84,
            clarity_score=86,
            market_fit_score=85,
            project_score=82,
            strengths=["Clear technical stack."],
            weaknesses=["Could quantify outcomes more."],
            recommendations=["Add impact metrics."],
            raw_summary={"parsed_resume": {"skills": ["Python", "Django"]}},
        )
        assessment = SeniorityAssessment.objects.create(
            resume=active_resume,
            internship_score=30,
            junior_score=78,
            mid_score=72,
            senior_score=45,
            freelance_score=60,
            recommended_track="junior",
            reasoning={"explanation": "Junior backend roles are the best fit."},
        )
        top_job = Job.objects.create(
            owner=self.user,
            title="Junior Backend Engineer",
            company_name="Acme",
            location="Remote",
            description="Python Django SQL APIs",
            url="https://example.com/jobs/1",
        )
        second_job = Job.objects.create(
            owner=self.user,
            title="Platform Analyst",
            company_name="Beta",
            location="Remote",
            description="SQL dashboards and APIs",
            url="https://example.com/jobs/2",
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=second_job,
            match_score=74,
            strengths=["Strong SQL overlap."],
            gaps=["Needs more BI tooling."],
            recommendation="Promising match.",
            reasoning={"overlapping_skills": ["sql"]},
        )
        best_match = JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=top_job,
            match_score=91,
            strengths=["Python and Django overlap."],
            gaps=["Small cloud gap."],
            recommendation="Strong match. Prioritize this application.",
            reasoning={"overlapping_skills": ["python", "django"]},
        )

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total_resumes"], 2)
        self.assertEqual(response.data["summary"]["total_matches"], 2)
        self.assertEqual(response.data["summary"]["top_match_score"], 91)
        self.assertEqual(response.data["summary"]["average_match_score"], 82.5)
        self.assertTrue(response.data["summary"]["analysis_ready"])
        self.assertTrue(response.data["summary"]["seniority_ready"])
        self.assertEqual(response.data["active_resume"]["id"], active_resume.id)
        self.assertEqual(response.data["analysis"]["id"], analysis.id)
        self.assertEqual(
            response.data["seniority_assessment"]["id"],
            assessment.id,
        )
        self.assertEqual(response.data["top_matches"][0]["id"], best_match.id)
        self.assertEqual(response.data["top_matches"][0]["job_title"], top_job.title)

    def test_dashboard_handles_user_without_active_resume(self) -> None:
        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "summary": {
                    "total_resumes": 0,
                    "total_matches": 0,
                    "average_match_score": None,
                    "top_match_score": None,
                    "analysis_ready": False,
                    "seniority_ready": False,
                },
                "active_resume": None,
                "analysis": None,
                "seniority_assessment": None,
                "top_matches": [],
            },
        )

    def test_dashboard_is_scoped_to_authenticated_user(self) -> None:
        other_resume = Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/private.docx",
            original_filename="private.docx",
            extracted_text="private",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        other_job = Job.objects.create(
            owner=self.other_user,
            title="Senior Data Engineer",
            company_name="OtherCo",
            location="Remote",
            description="Python Spark AWS",
            url="https://example.com/jobs/3",
        )
        ResumeAnalysis.objects.create(
            resume=other_resume,
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
        SeniorityAssessment.objects.create(
            resume=other_resume,
            internship_score=10,
            junior_score=20,
            mid_score=30,
            senior_score=80,
            freelance_score=50,
            recommended_track="senior",
            reasoning={"explanation": "Private assessment."},
        )
        JobMatch.objects.create(
            owner=self.other_user,
            resume=other_resume,
            job=other_job,
            match_score=95,
            strengths=["Private"],
            gaps=[],
            recommendation="Private",
            reasoning={},
        )

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total_resumes"], 0)
        self.assertEqual(response.data["summary"]["total_matches"], 0)
        self.assertIsNone(response.data["active_resume"])
        self.assertEqual(response.data["top_matches"], [])
