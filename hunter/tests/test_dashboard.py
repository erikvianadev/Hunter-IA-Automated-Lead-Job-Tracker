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
        self.assertEqual(response.data["activation"]["completed_steps"], 6)
        self.assertEqual(response.data["activation"]["progress_percent"], 100)
        self.assertTrue(response.data["activation"]["is_complete"])
        self.assertEqual(
            response.data["activation"]["next_best_action"]["action_type"],
            "activation_complete",
        )
        self.assertEqual(response.data["best_resume_summary"]["id"], active_resume.id)
        self.assertEqual(response.data["resume_report_preview"]["resume_id"], active_resume.id)
        self.assertEqual(response.data["resume_report_preview"]["average_match_score"], 82.5)
        self.assertTrue(response.data["comparison_available"])
        self.assertTrue(response.data["priority_actions"])
        self.assertEqual(response.data["priority_actions"][0]["action_type"], "project_signal")

    def test_dashboard_handles_user_without_active_resume(self) -> None:
        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["summary"],
            {
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
        )
        self.assertIsNone(response.data["active_resume"])
        self.assertIsNone(response.data["analysis"])
        self.assertIsNone(response.data["seniority_assessment"])
        self.assertEqual(response.data["top_matches"], [])
        self.assertEqual(response.data["recommended_jobs"], [])
        self.assertIsNone(response.data["best_resume_summary"])
        self.assertIsNone(response.data["resume_report_preview"])
        self.assertFalse(response.data["comparison_available"])

        self.assertEqual(response.data["activation"]["completed_steps"], 1)
        self.assertEqual(response.data["activation"]["progress_percent"], 17)
        self.assertEqual(
            response.data["activation"]["next_best_action"]["action_type"],
            "resume_upload",
        )
        self.assertTrue(response.data["priority_actions"])
        self.assertEqual(response.data["priority_actions"][0]["action_type"], "resume_upload")

        weekly_control = response.data["weekly_control"]
        self.assertEqual(weekly_control["headline"], "Mission Control semanal")
        self.assertEqual(weekly_control["applications_needing_attention"], [])
        self.assertEqual(weekly_control["jobs_to_act_now"], [])
        self.assertEqual(weekly_control["resume_gaps"], [])

        main_priority = weekly_control["main_priority"]
        self.assertEqual(main_priority["rank"], 1)
        self.assertEqual(main_priority["source"], "setup")
        self.assertEqual(main_priority["title"], "Criar a base da busca semanal")
        self.assertEqual(main_priority["cta_href"], "/resumes")
        self.assertIn("curriculo ativo", main_priority["reason"])
        self.assertGreater(main_priority["score"], weekly_control["secondary_priorities"][0]["score"])

        secondary_titles = [item["title"] for item in weekly_control["secondary_priorities"]]
        self.assertEqual(
            secondary_titles,
            [
                "Depois, liberar diagnostico do curriculo",
                "Montar a primeira shortlist",
            ],
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
        self.assertIsNone(response.data["best_resume_summary"])
        self.assertIsNone(response.data["resume_report_preview"])
        self.assertFalse(response.data["comparison_available"])
        self.assertEqual(response.data["activation"]["completed_steps"], 1)
        self.assertEqual(
            response.data["activation"]["next_best_action"]["action_type"],
            "resume_upload",
        )

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
        self.assertEqual(response.data["resume_report_preview"]["resume_id"], resume.id)
        self.assertEqual(response.data["activation"]["completed_steps"], 2)
        self.assertEqual(
            response.data["activation"]["next_best_action"]["action_type"],
            "resume_analysis",
        )
        action_types = [item["action_type"] for item in response.data["priority_actions"]]
        self.assertIn("resume_analysis", action_types)
        self.assertIn("seniority_assessment", action_types)

    def test_dashboard_flags_comparison_available_when_user_has_multiple_resumes(self) -> None:
        Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/one.docx",
            label="One",
            target_role="Backend Engineer",
            original_filename="one.docx",
            extracted_text="one",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/two.docx",
            label="Two",
            target_role="Backend Engineer",
            original_filename="two.docx",
            extracted_text="two",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=False,
        )

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["comparison_available"])

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
        self.assertEqual(
            response.data["activation"]["next_best_action"]["action_type"],
            "resume_analysis",
        )

    def test_dashboard_next_best_action_highlights_first_job_action_after_search(self) -> None:
        active_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/active-ready.docx",
            label="Current",
            target_role="Backend Engineer",
            original_filename="active-ready.docx",
            extracted_text="Python Django SQL APIs",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        ResumeAnalysis.objects.create(
            resume=active_resume,
            overall_score=79,
            structure_score=80,
            clarity_score=78,
            market_fit_score=77,
            project_score=76,
            strengths=["Boa clareza"],
            weaknesses=["Poucas metricas"],
            recommendations=["Adicione impacto numerico."],
            raw_summary={"parsed_resume": {"projects": ["API interna"], "links": ["linkedin"]}},
        )
        SeniorityAssessment.objects.create(
            resume=active_resume,
            internship_score=20,
            junior_score=70,
            mid_score=76,
            senior_score=48,
            freelance_score=52,
            recommended_track="mid",
            reasoning={"explanation": "Pleno parece o nivel mais aderente."},
        )
        target_job = Job.objects.create(
            owner=self.user,
            title="Backend Engineer",
            company_name="Acme",
            location="Remote",
            description="Python Django APIs",
            url="https://example.com/jobs/ready",
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=target_job,
            match_score=84,
            strengths=["Boa aderencia tecnica"],
            gaps=["Precisa reforcar cloud"],
            recommendation="Vale priorizar essa vaga.",
            reasoning={},
        )

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["activation"]["next_best_action"]["action_type"],
            "job_first_action",
        )

    def test_dashboard_weekly_control_ranks_hot_application_before_strong_job(self) -> None:
        active_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/mission-control.docx",
            label="Mission Control",
            target_role="Backend Engineer",
            original_filename="mission-control.docx",
            extracted_text="Python Django SQL APIs observability delivery",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        ResumeAnalysis.objects.create(
            resume=active_resume,
            overall_score=84,
            structure_score=82,
            clarity_score=83,
            market_fit_score=84,
            project_score=81,
            strengths=["Boa aderencia tecnica"],
            weaknesses=[],
            recommendations=[],
            raw_summary={
                "parsed_resume": {
                    "projects": ["API de pagamentos"],
                    "links": ["https://github.com/example"],
                }
            },
        )
        SeniorityAssessment.objects.create(
            resume=active_resume,
            internship_score=10,
            junior_score=40,
            mid_score=82,
            senior_score=68,
            freelance_score=50,
            recommended_track="mid",
            reasoning={"explanation": "Pleno e o nivel mais aderente."},
        )
        offer_job = Job.objects.create(
            owner=self.user,
            title="Backend Engineer",
            company_name="OfferCo",
            location="Remote",
            description="Python Django APIs",
            url="https://example.com/jobs/offer",
        )
        strong_job = Job.objects.create(
            owner=self.user,
            title="Platform Engineer",
            company_name="StrongCo",
            location="Remote",
            description="Python APIs observability",
            url="https://example.com/jobs/strong",
        )
        offer_application = JobApplication.objects.create(
            owner=self.user,
            job=offer_job,
            status=JobApplicationStatus.OFFER,
            notes="",
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=active_resume,
            job=strong_job,
            match_score=92,
            strengths=["Python and APIs overlap."],
            gaps=[],
            recommendation="Strong match.",
            reasoning={},
        )

        response = self.client.get("/hunter/api/resumes/dashboard/")

        self.assertEqual(response.status_code, 200)
        weekly_control = response.data["weekly_control"]
        self.assertEqual(weekly_control["main_priority"]["source"], "application")
        self.assertEqual(weekly_control["main_priority"]["source_id"], offer_application.id)
        self.assertEqual(weekly_control["main_priority"]["rank"], 1)
        self.assertIn("oferta", weekly_control["main_priority"]["reason"])

        self.assertEqual(
            weekly_control["applications_needing_attention"][0]["application_id"],
            offer_application.id,
        )
        self.assertEqual(
            weekly_control["applications_needing_attention"][0]["objective_criteria"][0],
            "oferta em aberto",
        )
        self.assertEqual(weekly_control["jobs_to_act_now"][0]["job_id"], strong_job.id)
        self.assertEqual(weekly_control["jobs_to_act_now"][0]["match_score"], 92)
        self.assertIn(
            "job",
            [priority["source"] for priority in weekly_control["secondary_priorities"]],
        )
