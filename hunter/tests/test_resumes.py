import os
import shutil
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hunter.choices import ResumeParseStatus
from hunter.models.models import Job, JobMatch, Resume
from hunter.services.resume_ingestion_service import ResumeIngestionService
from hunter.services.resume_text_extraction_service import (
    ResumeTextExtractionError,
    ResumeExtractionResult,
    ResumeTextExtractionService,
)


def build_docx_bytes(*paragraphs: str) -> bytes:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body}</w:body>
</w:document>""".format(
        body="".join(
            f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
            for paragraph in paragraphs
        )
    )

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def build_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    payload = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
72 100 Td
({escaped}) Tj
ET
endstream
endobj
trailer
<< /Root 1 0 R >>
%%EOF
"""
    return payload.encode("latin-1")


TEMP_MEDIA_ROOT = os.path.join(os.getcwd(), "test_media")


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ResumeApiTests(TestCase):
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
            username="resume-user",
            password="secret",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-user",
            password="secret",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_authenticated_user_can_upload_resume(self) -> None:
        upload = SimpleUploadedFile(
            "resume.docx",
            build_docx_bytes("Jane Doe", "Senior Data Analyst"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.post(
            "/hunter/api/resumes/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["original_filename"], "resume.docx")
        self.assertEqual(response.data["label"], "resume")
        self.assertEqual(response.data["target_role"], "")
        self.assertTrue(response.data["is_active"])
        self.assertEqual(response.data["parse_status"], ResumeParseStatus.COMPLETED)
        self.assertIn("Jane Doe", response.data["extracted_text"])

    def test_upload_accepts_resume_label_and_target_role(self) -> None:
        upload = SimpleUploadedFile(
            "backend.docx",
            build_docx_bytes("Jane Doe", "Backend Engineer"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.post(
            "/hunter/api/resumes/",
            {
                "file": upload,
                "label": "Backend v2",
                "target_role": "Backend Engineer",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["label"], "Backend v2")
        self.assertEqual(response.data["target_role"], "Backend Engineer")

    def test_list_returns_only_current_users_resumes(self) -> None:
        Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/first.docx",
            original_filename="first.docx",
            extracted_text="mine",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/other.docx",
            original_filename="other.docx",
            extracted_text="other",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.get("/hunter/api/resumes/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["original_filename"], "first.docx")

    def test_user_can_retrieve_own_resume(self) -> None:
        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/me.docx",
            original_filename="me.docx",
            extracted_text="owned",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.get(f"/hunter/api/resumes/{resume.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], resume.id)
        self.assertEqual(response.data["original_filename"], "me.docx")

    def test_user_cannot_access_another_users_resume(self) -> None:
        resume = Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/private.docx",
            original_filename="private.docx",
            extracted_text="private",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.get(f"/hunter/api/resumes/{resume.id}/")

        self.assertEqual(response.status_code, 404)

    def test_delete_removes_own_resume(self) -> None:
        upload = SimpleUploadedFile(
            "delete.docx",
            build_docx_bytes("Delete Me"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        resume = Resume.objects.create(
            owner=self.user,
            file=upload,
            original_filename="delete.docx",
            extracted_text="cleanup",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = self.client.delete(f"/hunter/api/resumes/{resume.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Resume.objects.filter(id=resume.id).exists())

    def test_activate_marks_only_selected_resume_as_active(self) -> None:
        first_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/first.docx",
            label="First",
            target_role="Data Analyst",
            original_filename="first.docx",
            extracted_text="first",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        second_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/second.docx",
            label="Second",
            target_role="Backend Engineer",
            original_filename="second.docx",
            extracted_text="second",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=False,
        )

        response = self.client.post(f"/hunter/api/resumes/{second_resume.id}/activate/")

        first_resume.refresh_from_db()
        second_resume.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(first_resume.is_active)
        self.assertTrue(second_resume.is_active)
        self.assertEqual(response.data["id"], second_resume.id)

    def test_activation_isolated_to_owned_resume(self) -> None:
        private_resume = Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/private.docx",
            label="Private",
            target_role="Private Role",
            original_filename="private.docx",
            extracted_text="private",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )

        response = self.client.post(f"/hunter/api/resumes/{private_resume.id}/activate/")

        self.assertEqual(response.status_code, 404)

    def test_compare_returns_useful_resume_summary(self) -> None:
        first_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/first.docx",
            label="Backend v1",
            target_role="Backend Engineer",
            original_filename="first.docx",
            extracted_text="first",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=False,
        )
        second_resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/second.docx",
            label="Backend v2",
            target_role="Backend Engineer",
            original_filename="second.docx",
            extracted_text="second",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        other_resume = Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/other.docx",
            label="Other",
            target_role="Data Engineer",
            original_filename="other.docx",
            extracted_text="other",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )

        from hunter.models.models import ResumeAnalysis, SeniorityAssessment

        ResumeAnalysis.objects.create(
            resume=first_resume,
            overall_score=68,
            structure_score=65,
            clarity_score=70,
            market_fit_score=66,
            project_score=60,
            strengths=[],
            weaknesses=[],
            recommendations=[],
            raw_summary={},
        )
        ResumeAnalysis.objects.create(
            resume=second_resume,
            overall_score=84,
            structure_score=82,
            clarity_score=85,
            market_fit_score=83,
            project_score=78,
            strengths=[],
            weaknesses=[],
            recommendations=[],
            raw_summary={},
        )
        SeniorityAssessment.objects.create(
            resume=first_resume,
            internship_score=20,
            junior_score=70,
            mid_score=60,
            senior_score=30,
            freelance_score=40,
            recommended_track="junior",
            reasoning={},
        )
        SeniorityAssessment.objects.create(
            resume=second_resume,
            internship_score=10,
            junior_score=65,
            mid_score=78,
            senior_score=40,
            freelance_score=35,
            recommended_track="mid",
            reasoning={},
        )
        ResumeAnalysis.objects.create(
            resume=other_resume,
            overall_score=99,
            structure_score=99,
            clarity_score=99,
            market_fit_score=99,
            project_score=99,
            strengths=[],
            weaknesses=[],
            recommendations=[],
            raw_summary={},
        )

        response = self.client.get(
            f"/hunter/api/resumes/compare/?ids={first_resume.id},{second_resume.id},{other_resume.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["compared_resumes"]), 2)
        self.assertEqual(response.data["best_resume_by_score"]["id"], second_resume.id)
        self.assertEqual(
            response.data["best_resume_for_likely_target"]["id"],
            second_resume.id,
        )
        self.assertEqual(response.data["likely_target_role"], "Backend Engineer")
        self.assertIn("comparison_summary", response.data)
        self.assertTrue(response.data["main_differences"])
        self.assertEqual(response.data["stronger_areas"]["structure"]["id"], second_resume.id)
        self.assertEqual(response.data["compared_resumes"][0]["clarity_score"], 85)
        self.assertEqual(response.data["compared_resumes"][0]["market_fit_score"], 83)
        self.assertEqual(response.data["compared_resumes"][0]["id"], second_resume.id)

    def test_resume_report_returns_rich_deterministic_fields(self) -> None:
        from hunter.models.models import ResumeAnalysis, SeniorityAssessment

        resume = Resume.objects.create(
            owner=self.user,
            file="resumes/user_1/report.docx",
            label="Backend Premium",
            target_role="Backend Engineer",
            original_filename="report.docx",
            extracted_text="Python Django SQL APIs Docker projects and metrics",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )
        ResumeAnalysis.objects.create(
            resume=resume,
            overall_score=81,
            structure_score=78,
            clarity_score=74,
            market_fit_score=80,
            project_score=62,
            strengths=["Clear technical stack."],
            weaknesses=["Projects need more measurable outcomes."],
            recommendations=["Add quantified impact to projects."],
            raw_summary={},
        )
        SeniorityAssessment.objects.create(
            resume=resume,
            internship_score=20,
            junior_score=75,
            mid_score=79,
            senior_score=38,
            freelance_score=44,
            recommended_track="mid",
            reasoning={"explanation": "Mid roles are the best fit."},
        )
        top_job = Job.objects.create(
            owner=self.user,
            title="Backend Engineer",
            company_name="Acme",
            location="Remote",
            description="Python Django APIs Docker SQL",
            url="https://example.com/jobs/report",
        )
        JobMatch.objects.create(
            owner=self.user,
            resume=resume,
            job=top_job,
            match_score=88,
            strengths=["Python overlap."],
            gaps=["Need stronger cloud examples."],
            recommendation="Strong match. Prioritize this application.",
            reasoning={},
        )

        response = self.client.get(f"/hunter/api/resumes/{resume.id}/report/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["resume_id"], resume.id)
        self.assertEqual(response.data["label"], "Backend Premium")
        self.assertEqual(response.data["target_role"], "Backend Engineer")
        self.assertEqual(response.data["category_scores"]["overall"], 81)
        self.assertEqual(response.data["category_scores"]["market_fit"], 80)
        self.assertEqual(response.data["recommended_track"], "mid")
        self.assertTrue(response.data["strengths"])
        self.assertTrue(response.data["top_gaps"])
        self.assertTrue(response.data["priority_actions"])
        self.assertEqual(response.data["recent_match_summary"]["average_match_score"], 88.0)
        self.assertEqual(response.data["recent_match_summary"]["best_match_score"], 88)
        self.assertIn("Backend Premium", response.data["executive_summary"])
        self.assertIn("recommended track is mid", response.data["profile_summary"].lower())

    def test_resume_report_is_scoped_to_owner(self) -> None:
        private_resume = Resume.objects.create(
            owner=self.other_user,
            file="resumes/user_2/private-report.docx",
            label="Private Report",
            target_role="Data Engineer",
            original_filename="private-report.docx",
            extracted_text="private",
            parse_status=ResumeParseStatus.COMPLETED,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            is_active=True,
        )

        response = self.client.get(f"/hunter/api/resumes/{private_resume.id}/report/")

        self.assertEqual(response.status_code, 404)

    def test_invalid_file_type_is_rejected(self) -> None:
        upload = SimpleUploadedFile(
            "resume.txt",
            b"plain text resume",
            content_type="text/plain",
        )

        response = self.client.post(
            "/hunter/api/resumes/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)

    def test_failed_extraction_marks_resume_as_failed(self) -> None:
        upload = SimpleUploadedFile(
            "broken.pdf",
            b"not-a-real-pdf",
            content_type="application/pdf",
        )

        response = self.client.post(
            "/hunter/api/resumes/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["parse_status"], ResumeParseStatus.UNSUPPORTED_STRUCTURE)
        self.assertEqual(response.data["extracted_text"], "")


class ResumeTextExtractionServiceTests(TestCase):
    def test_extracts_text_from_docx(self) -> None:
        text = ResumeTextExtractionService().extract_text(
            file_bytes=build_docx_bytes("Jane Doe", "Python Engineer"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="resume.docx",
        )

        self.assertEqual(text, "Jane Doe\nPython Engineer")

    def test_extracts_text_from_pdf(self) -> None:
        text = ResumeTextExtractionService().extract_text(
            file_bytes=build_pdf_bytes("Jane Doe Resume"),
            content_type="application/pdf",
            filename="resume.pdf",
        )

        self.assertIn("Jane Doe Resume", text)

    def test_extract_result_marks_completed_for_valid_pdf(self) -> None:
        result = ResumeTextExtractionService().extract(
            file_bytes=build_pdf_bytes("Jane Doe Resume"),
            content_type="application/pdf",
            filename="resume.pdf",
        )

        self.assertEqual(result, ResumeExtractionResult(text="Jane Doe Resume", status="completed"))

    def test_unsupported_format_raises_error(self) -> None:
        with self.assertRaises(ResumeTextExtractionError):
            ResumeTextExtractionService().extract_text(
                file_bytes=b"content",
                content_type="text/plain",
                filename="resume.txt",
            )

    def test_pdf_with_no_extractable_text_raises_empty_text_reason(self) -> None:
        with self.assertRaises(ResumeTextExtractionError) as exc_info:
            ResumeTextExtractionService().extract_text(
                file_bytes=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
                content_type="application/pdf",
                filename="empty.pdf",
            )

        self.assertEqual(exc_info.exception.reason, "empty_text")


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ResumeIngestionServiceTests(TestCase):
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
            username="ingestion-user",
            password="secret",
        )

    def test_ingestion_marks_completed_for_extractable_docx(self) -> None:
        resume = ResumeIngestionService().ingest(
            owner=self.user,
            uploaded_file=SimpleUploadedFile(
                "resume.docx",
                build_docx_bytes("Jane Doe", "Python Engineer"),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )

        self.assertEqual(resume.parse_status, ResumeParseStatus.COMPLETED)
        self.assertIn("Jane Doe", resume.extracted_text)

    def test_ingestion_marks_empty_text_for_valid_but_blank_pdf(self) -> None:
        resume = ResumeIngestionService().ingest(
            owner=self.user,
            uploaded_file=SimpleUploadedFile(
                "empty.pdf",
                b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
                content_type="application/pdf",
            ),
        )

        self.assertEqual(resume.parse_status, ResumeParseStatus.EMPTY_TEXT)
        self.assertEqual(resume.extracted_text, "")
