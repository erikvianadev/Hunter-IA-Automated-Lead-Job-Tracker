from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from hunter.choices import ResumeParseStatus
from hunter.models.models import Resume

from .resume_security_service import ResumeSecurityService
from .resume_text_extraction_service import ResumeTextExtractionError, ResumeTextExtractionService


class ResumeValidationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = ResumeParseStatus.INVALID_FILE,
        diagnostics: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or {}


class ResumeIngestionService:
    def __init__(
        self,
        *,
        extraction_service: ResumeTextExtractionService | None = None,
        security_service: ResumeSecurityService | None = None,
    ) -> None:
        self.extraction_service = extraction_service or ResumeTextExtractionService()
        self.security_service = security_service or ResumeSecurityService()
        config = getattr(settings, "RESUME_INGESTION", {})
        self.max_upload_size_bytes = int(config.get("MAX_UPLOAD_SIZE_BYTES", 5 * 1024 * 1024))
        self.allowed_extensions = {
            extension.lower()
            for extension in config.get("ALLOWED_EXTENSIONS", [".pdf", ".docx"])
        }
        self.allowed_content_types = {
            extension.lower(): {value.lower() for value in values}
            for extension, values in config.get("ALLOWED_CONTENT_TYPES", {}).items()
        }
        self.enable_content_type_validation = bool(
            config.get("ENABLE_CONTENT_TYPE_VALIDATION", True)
        )

    @transaction.atomic
    def ingest(self, *, owner, uploaded_file: UploadedFile) -> Resume:
        return self.ingest_with_profile(
            owner=owner,
            uploaded_file=uploaded_file,
            label=None,
            target_role="",
        )

    @transaction.atomic
    def ingest_with_profile(
        self,
        *,
        owner,
        uploaded_file: UploadedFile,
        label: str | None = None,
        target_role: str = "",
    ) -> Resume:
        content_type = self._detect_content_type(uploaded_file)
        admission_diagnostics = self._validate_file(
            uploaded_file=uploaded_file,
            content_type=content_type,
        )

        resume = Resume.objects.create(
            owner=owner,
            file=uploaded_file,
            label=(label or Path(uploaded_file.name).stem).strip(),
            target_role=target_role.strip(),
            original_filename=uploaded_file.name,
            content_type=content_type,
            extraction_diagnostics=admission_diagnostics,
            parse_status=ResumeParseStatus.PENDING,
            is_active=False,
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
            diagnostics = {
                **admission_diagnostics,
                **(getattr(exc, "diagnostics", {}) or {}),
            }
            diagnostics["normalized_parse_status"] = self.security_service.normalize_status(
                getattr(exc, "reason", None)
            )
            resume.parse_status = diagnostics["normalized_parse_status"]
            resume.extracted_text = getattr(exc, "extracted_text", "") or ""
            resume.extraction_diagnostics = diagnostics
            resume.is_active = False
            resume.save(
                update_fields=[
                    "parse_status",
                    "extracted_text",
                    "extraction_diagnostics",
                    "is_active",
                    "updated_at",
                ]
            )
            return resume

        parse_status = self.security_service.normalize_status(extraction.status)
        diagnostics = {
            **admission_diagnostics,
            **extraction.diagnostics,
            "normalized_parse_status": parse_status,
        }
        resume.parse_status = parse_status
        resume.extracted_text = extraction.text
        resume.extraction_diagnostics = diagnostics
        resume.is_active = parse_status == ResumeParseStatus.COMPLETED
        resume.save(
            update_fields=[
                "parse_status",
                "extracted_text",
                "extraction_diagnostics",
                "is_active",
                "updated_at",
            ]
        )
        if resume.is_active:
            Resume.objects.filter(owner=owner, is_active=True).exclude(id=resume.id).update(is_active=False)
        return resume

    def _validate_file(self, *, uploaded_file: UploadedFile, content_type: str) -> dict[str, object]:
        if not uploaded_file or not uploaded_file.name:
            raise ResumeValidationError("Resume file is required.")

        extension = Path(uploaded_file.name).suffix.lower()
        file_size = int(getattr(uploaded_file, "size", 0) or 0)
        diagnostics = {
            "file_name": uploaded_file.name,
            "file_size_bytes": file_size,
            "file_extension": extension,
            "detected_content_type": content_type,
            "admission_validated": True,
            "blocked_by_policy": False,
        }

        if extension not in self.allowed_extensions:
            raise ResumeValidationError(
                "Only PDF and DOCX resume files are supported.",
                code=ResumeParseStatus.UNSUPPORTED_FILE_TYPE,
                diagnostics={
                    **diagnostics,
                    "allowed_extensions": sorted(self.allowed_extensions),
                },
            )

        if file_size <= 0:
            raise ResumeValidationError(
                "Uploaded resume file is empty.",
                code=ResumeParseStatus.INVALID_FILE,
                diagnostics=diagnostics,
            )

        if file_size > self.max_upload_size_bytes:
            raise ResumeValidationError(
                "Uploaded resume exceeds the configured size limit.",
                code=ResumeParseStatus.UPLOAD_TOO_LARGE,
                diagnostics={
                    **diagnostics,
                    "max_upload_size_bytes": self.max_upload_size_bytes,
                },
            )

        if self.enable_content_type_validation:
            allowed_content_types = self.allowed_content_types.get(extension, set())
            if content_type not in allowed_content_types:
                raise ResumeValidationError(
                    "Unsupported resume content type.",
                    code=ResumeParseStatus.UNSUPPORTED_FILE_TYPE,
                    diagnostics={
                        **diagnostics,
                        "allowed_content_types": sorted(allowed_content_types),
                    },
                )

        signature = self._peek_bytes(uploaded_file, length=8)
        if extension == ".pdf" and not signature.lstrip().startswith(b"%PDF"):
            raise ResumeValidationError(
                "Uploaded file does not look like a valid PDF.",
                code=ResumeParseStatus.INVALID_FILE,
                diagnostics=diagnostics,
            )
        if extension == ".docx" and not signature.startswith(b"PK"):
            raise ResumeValidationError(
                "Uploaded file does not look like a valid DOCX archive.",
                code=ResumeParseStatus.INVALID_FILE,
                diagnostics=diagnostics,
            )
        return diagnostics

    def _detect_content_type(self, uploaded_file: UploadedFile) -> str:
        content_type = (uploaded_file.content_type or "").strip().lower()
        if content_type:
            return content_type
        guessed_content_type, _ = mimetypes.guess_type(uploaded_file.name)
        return (guessed_content_type or "").lower()

    def _peek_bytes(self, uploaded_file: UploadedFile, *, length: int) -> bytes:
        position = None
        try:
            position = uploaded_file.tell()
        except (AttributeError, OSError):
            position = None
        try:
            uploaded_file.seek(0)
            return uploaded_file.read(length)
        finally:
            if position is not None:
                uploaded_file.seek(position)
