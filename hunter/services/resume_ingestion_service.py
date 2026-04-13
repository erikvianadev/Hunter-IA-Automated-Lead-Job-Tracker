from __future__ import annotations

import mimetypes
import zipfile
from io import BytesIO
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
    CONTENT_TYPE_ALIASES = {
        "application/x-pdf": "application/pdf",
        "application/x-zip-compressed": "application/zip",
    }

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

    def _make_json_safe(self, value):
        if isinstance(value, bytes):
            return f"<bytes:{len(value)}>"
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): self._make_json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._make_json_safe(item) for item in value]
        return value

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
        file_bytes = self._read_file_bytes(uploaded_file)
        admission_diagnostics = self._make_json_safe(self._validate_file(
            uploaded_file=uploaded_file,
            content_type=content_type,
            file_bytes=file_bytes,
        ))
        uploaded_file.seek(0)

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
            extraction = self.extraction_service.extract(
                file_bytes=file_bytes,
                content_type=content_type,
                filename=uploaded_file.name,
            )
        except (ResumeTextExtractionError, OSError, ValueError) as exc:
            diagnostics = self._make_json_safe({
                **admission_diagnostics,
                **(getattr(exc, "diagnostics", {}) or {}),
            })
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
        diagnostics = self._make_json_safe({
            **admission_diagnostics,
            **extraction.diagnostics,
            "normalized_parse_status": parse_status,
        })
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

    def _validate_file(
        self,
        *,
        uploaded_file: UploadedFile,
        content_type: str,
        file_bytes: bytes,
    ) -> dict[str, object]:
        if not uploaded_file or not uploaded_file.name:
            raise ResumeValidationError("Resume file is required.")

        extension = Path(uploaded_file.name).suffix.lower()
        file_size = int(getattr(uploaded_file, "size", 0) or 0)
        reported_content_type = self._normalize_content_type(
            (getattr(uploaded_file, "content_type", "") or "").strip().lower()
        )
        detected_signature = self._detect_file_signature(file_bytes)
        diagnostics = {
            "file_name": uploaded_file.name,
            "file_size_bytes": file_size,
            "file_extension": extension,
            "reported_content_type": reported_content_type,
            "detected_content_type": content_type,
            "detected_file_signature": detected_signature,
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
            should_validate_reported_type = reported_content_type not in {
                "",
                "application/octet-stream",
                "binary/octet-stream",
            }
            if should_validate_reported_type and reported_content_type not in allowed_content_types:
                raise ResumeValidationError(
                    "Unsupported resume content type.",
                    code=ResumeParseStatus.UNSUPPORTED_FILE_TYPE,
                    diagnostics={
                        **diagnostics,
                        "allowed_content_types": sorted(allowed_content_types),
                    },
                )

        self._validate_file_signature(
            extension=extension,
            file_bytes=file_bytes,
            diagnostics=diagnostics,
        )

        return diagnostics

    def _detect_content_type(self, uploaded_file: UploadedFile) -> str:
        content_type = (uploaded_file.content_type or "").strip().lower()
        if content_type:
            return self._normalize_content_type(content_type)
        guessed_content_type, _ = mimetypes.guess_type(uploaded_file.name)
        return self._normalize_content_type((guessed_content_type or "").lower())

    def _read_file_bytes(self, uploaded_file: UploadedFile) -> bytes:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        return file_bytes

    def _normalize_content_type(self, content_type: str) -> str:
        normalized = (content_type or "").strip().lower()
        return self.CONTENT_TYPE_ALIASES.get(normalized, normalized)

    def _detect_file_signature(self, file_bytes: bytes) -> str:
        stripped = file_bytes.lstrip()
        if stripped.startswith(b"%PDF"):
            return "pdf"
        if file_bytes.startswith(b"PK"):
            return "zip"
        return "unknown"

    def _validate_file_signature(
        self,
        *,
        extension: str,
        file_bytes: bytes,
        diagnostics: dict[str, object],
    ) -> None:
        if extension == ".pdf":
            if not file_bytes.lstrip().startswith(b"%PDF"):
                raise ResumeValidationError(
                    "The uploaded file does not contain a valid PDF signature.",
                    code=ResumeParseStatus.INVALID_FILE,
                    diagnostics=diagnostics,
                )
            diagnostics["signature_matches_extension"] = True
            return

        if extension == ".docx":
            if not file_bytes.startswith(b"PK"):
                raise ResumeValidationError(
                    "The uploaded file does not contain a valid DOCX archive signature.",
                    code=ResumeParseStatus.INVALID_FILE,
                    diagnostics=diagnostics,
                )
            try:
                with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
                    members = set(archive.namelist())
            except zipfile.BadZipFile as exc:
                raise ResumeValidationError(
                    "The uploaded file is not a readable DOCX archive.",
                    code=ResumeParseStatus.INVALID_FILE,
                    diagnostics=diagnostics,
                ) from exc

            required_members = {"[Content_Types].xml", "word/document.xml"}
            missing_members = sorted(required_members - members)
            if missing_members:
                raise ResumeValidationError(
                    "The uploaded file is not a supported DOCX document.",
                    code=ResumeParseStatus.INVALID_FILE,
                    diagnostics={
                        **diagnostics,
                        "missing_docx_members": missing_members,
                    },
                )
            diagnostics["signature_matches_extension"] = True
