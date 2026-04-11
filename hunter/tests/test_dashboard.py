from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hunter.choices import JobApplicationStatus, ResumeParseStatus
from hunter.models.models import (
    Job,
    JobApplication,
    JobMatch,
    Resume,
    ResumeAnalysis,
    SavedJob,
    SeniorityAssessment,
)


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
            label="Backend v2",
            target_role="Backend Engineer",
            original_filename="active.docx",
            extracted_text="Python Django SQL Docker APIs",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/old.docx",
            label="Old Version",
            target_role="Data Analyst",
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
        SavedJob.objects.create(owner=self.user, job=top_job)
        JobApplication.objects.create(
            owner=self.user,
            job=top_job,
            status=JobApplicationStatus.APPLIED,
            notes="Applied yesterday.",
        )

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total_resumes"], 2)
        self.assertEqual(response.data["summary"]["total_saved_jobs"], 1)
        self.assertEqual(response.data["summary"]["total_applications"], 1)
        self.assertEqual(response.data["summary"]["total_matches"], 2)
        self.assertEqual(response.data["summary"]["active_resume_label"], "Backend v2")
        self.assertEqual(response.data["summary"]["active_resume_target_role"], "Backend Engineer")
        self.assertEqual(response.data["summary"]["active_resume_status"], "ready")
        self.assertEqual(response.data["summary"]["top_match_score"], 91)
        self.assertEqual(response.data["summary"]["average_match_score"], 82.5)
        self.assertTrue(response.data["summary"]["analysis_ready"])
        self.assertTrue(response.data["summary"]["seniority_ready"])
        self.assertEqual(response.data["active_resume"]["id"], active_resume.id)
        self.assertEqual(response.data["active_resume"]["label"], "Backend v2")
        self.assertEqual(response.data["active_resume"]["target_role"], "Backend Engineer")
        self.assertEqual(response.data["analysis"]["id"], analysis.id)
        self.assertEqual(
            response.data["seniority_assessment"]["id"],
            assessment.id,
        )
        self.assertEqual(response.data["top_matches"][0]["id"], best_match.id)
        self.assertEqual(response.data["top_matches"][0]["job_title"], top_job.title)
        self.assertEqual(len(response.data["recommended_jobs"]), 1)
        self.assertEqual(response.data["recommended_jobs"][0]["job_id"], second_job.id)
        self.assertEqual(response.data["recommended_jobs"][0]["match_score"], 74)
        self.assertEqual(response.data["profile_insights"]["recommended_track"], "junior")
        self.assertEqual(response.data["profile_insights"]["competitiveness_level"], "high")
        self.assertEqual(response.data["profile_insights"]["top_gap_area"], "projects")
        self.assertTrue(response.data["priority_actions"])
        self.assertEqual(response.data["priority_actions"][0]["action_type"], "project_signal")

    def test_dashboard_handles_user_without_active_resume(self) -> None:
        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "summary": {
                    "total_resumes": 0,
                    "total_saved_jobs": 0,
                    "total_applications": 0,
                    "total_matches": 0,
                    "active_resume_label": None,
                    "active_resume_target_role": None,
                    "active_resume_status": "not_set",
                    "average_match_score": None,
                    "top_match_score": None,
                    "analysis_ready": False,
                    "seniority_ready": False,
                },
                "active_resume": None,
                "analysis": None,
                "seniority_assessment": None,
                "top_matches": [],
                "recommended_jobs": [],
                "priority_actions": [
                    {
                        "action_type": "resume_upload",
                        "title": "Upload your active resume",
                        "detail": "A current resume unlocks analysis, matching, and dashboard guidance.",
                        "priority": 1,
                    }
                ],
                "profile_insights": {
                    "recommended_track": None,
                    "competitiveness_level": None,
                    "top_gap_area": None,
                },
            },
        )

    def test_dashboard_is_scoped_to_authenticated_user(self) -> None:
        other_resume = Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/private.docx",
            label="Private Version",
            target_role="Senior Data Engineer",
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
        SavedJob.objects.create(owner=self.other_user, job=other_job)
        JobApplication.objects.create(
            owner=self.other_user,
            job=other_job,
            status=JobApplicationStatus.OFFER,
            notes="Private application.",
        )

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total_resumes"], 0)
        self.assertEqual(response.data["summary"]["total_saved_jobs"], 0)
        self.assertEqual(response.data["summary"]["total_applications"], 0)
        self.assertEqual(response.data["summary"]["total_matches"], 0)
        self.assertEqual(response.data["summary"]["active_resume_status"], "not_set")
        self.assertIsNone(response.data["active_resume"])
        self.assertEqual(response.data["top_matches"], [])
        self.assertEqual(response.data["recommended_jobs"], [])

    def test_dashboard_priority_actions_reflect_missing_analysis_and_seniority(self) -> None:
        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/basic.docx",
            label="Basic",
            target_role="Analyst",
            original_filename="basic.docx",
            extracted_text="Basic resume text",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        self.assertIsNotNone(resume)

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["active_resume_label"], "Basic")
        self.assertEqual(response.data["summary"]["active_resume_target_role"], "Analyst")
        self.assertEqual(response.data["summary"]["active_resume_status"], "uploaded")
        action_types = [item["action_type"] for item in response.data["priority_actions"]]
        self.assertIn("resume_analysis", action_types)
        self.assertIn("seniority_assessment", action_types)

    def test_dashboard_recommended_jobs_skip_low_matches_and_applied_roles(self) -> None:
        active_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/active.docx",
            label="Current",
            target_role="Backend Engineer",
            original_filename="active.docx",
            extracted_text="Python Django SQL",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        good_job = Job.objects.create(
            owner=self.user,
            title="Python Engineer",
            company_name="Acme",
            location="Remote",
            description="Python Django SQL",
            url="https://example.com/jobs/good",
        )
        low_job = Job.objects.create(
            owner=self.user,
            title="Support Analyst",
            company_name="Beta",
            location="Remote",
            description="Customer support",
            url="https://example.com/jobs/low",
        )
        applied_job = Job.objects.create(
            owner=self.user,
            title="Backend Developer",
            company_name="Gamma",
            location="Remote",
            description="Python APIs",
            url="https://example.com/jobs/applied",
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=applied_job,
            match_score=90,
            strengths=["High overlap"],
            gaps=[],
            recommendation="Strong match.",
            reasoning={},
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=good_job,
            match_score=81,
            strengths=["Strong fit"],
            gaps=[],
            recommendation="Strong match.",
            reasoning={},
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=low_job,
            match_score=32,
            strengths=[],
            gaps=["Low overlap"],
            recommendation="Low match.",
            reasoning={},
        )
        JobApplication.objects.create(
            owner=self.user,
            job=applied_job,
            status=JobApplicationStatus.APPLIED,
            notes="Already applied",
        )

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["recommended_jobs"]), 1)
        self.assertEqual(response.data["recommended_jobs"][0]["job_id"], good_job.id)
