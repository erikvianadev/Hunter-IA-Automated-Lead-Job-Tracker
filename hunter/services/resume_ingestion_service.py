from __future__ import annotations

import mimetypes
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from hunter.choices import ResumeParseStatus
from hunter.models.models import Resume

from .resume_text_extraction_service import (
    EXTRACTION_REASON_EMPTY_TEXT,
    EXTRACTION_REASON_UNSUPPORTED_STRUCTURE,
    ResumeTextExtractionError,
    ResumeTextExtractionService,
)


class ResumeValidationError(Exception):
    pass


class ResumeIngestionService:
    def __init__(
        self,
        *,
        extraction_service: ResumeTextExtractionService | None = None,
    ) -> None:
        self.extraction_service = extraction_service or ResumeTextExtractionService()

    @transaction.atomic
    def ingest(self, *, owner, uploaded_file: UploadedFile) -> Resume:
        content_type = self._detect_content_type(uploaded_file)
        self._validate_file(uploaded_file=uploaded_file, content_type=content_type)

        Resume.objects.filter(owner=owner, is_active=True).update(is_active=False)
        resume = Resume.objects.create(
            owner=owner,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            content_type=content_type,
            parse_status=ResumeParseStatus.PENDING,
            is_active=True,
        )
        resume.parse_status = ResumeParseStatus.PROCESSING
        resume.save(update_fields=["parse_status", "updated_at"])

        try:
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            extraction = self.extraction_service.extract(
                file_bytes=file_bytes,
                content_type=content_type,
                filename=uploaded_file.name,
            )
        except (ResumeTextExtractionError, OSError, ValueError) as exc:
            reason = getattr(exc, "reason", None)
            resume.parse_status = self._map_failure_reason_to_status(reason)
            resume.extracted_text = ""
            resume.save(update_fields=["parse_status", "extracted_text", "updated_at"])
            return resume

        resume.parse_status = ResumeParseStatus.COMPLETED
        resume.extracted_text = extraction.text
        resume.save(update_fields=["parse_status", "extracted_text", "updated_at"])
        return resume

    def _validate_file(self, *, uploaded_file: UploadedFile, content_type: str) -> None:
        if not uploaded_file or not uploaded_file.name:
            raise ResumeValidationError("Resume file is required.")
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in self.extraction_service.supported_extensions:
            raise ResumeValidationError("Only PDF and DOCX resume files are supported.")
        if content_type not in self.extraction_service.supported_content_types:
            raise ResumeValidationError("Unsupported resume content type.")

    def _detect_content_type(self, uploaded_file: UploadedFile) -> str:
        content_type = (uploaded_file.content_type or "").strip().lower()
        if content_type:
            return content_type
        guessed_content_type, _ = mimetypes.guess_type(uploaded_file.name)
        return (guessed_content_type or "").lower()

    def _map_failure_reason_to_status(self, reason: str | None) -> str:
        if reason == EXTRACTION_REASON_EMPTY_TEXT:
            return ResumeParseStatus.EMPTY_TEXT
        if reason == EXTRACTION_REASON_UNSUPPORTED_STRUCTURE:
            return ResumeParseStatus.UNSUPPORTED_STRUCTURE
        return ResumeParseStatus.FAILED
