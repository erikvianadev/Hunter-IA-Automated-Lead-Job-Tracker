import os
import shutil
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hunter.choices import ResumeParseStatus
from hunter.models.models import Resume
from hunter.services.resume_text_extraction_service import (
    ResumeTextExtractionError,
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
        self.assertEqual(response.data["parse_status"], ResumeParseStatus.COMPLETED)
        self.assertIn("Jane Doe", response.data["extracted_text"])

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
        self.assertEqual(response.data["parse_status"], ResumeParseStatus.FAILED)
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

    def test_unsupported_format_raises_error(self) -> None:
        with self.assertRaises(ResumeTextExtractionError):
            ResumeTextExtractionService().extract_text(
                file_bytes=b"content",
                content_type="text/plain",
                filename="resume.txt",
            )
