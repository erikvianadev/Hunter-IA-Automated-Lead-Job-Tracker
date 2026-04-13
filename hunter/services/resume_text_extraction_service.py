from __future__ import annotations

import logging
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from xml.etree import ElementTree

from django.conf import settings

try:
    from docx import Document
except ImportError:  # pragma: no cover - optional dependency
    Document = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency
    PdfReader = None

from hunter.choices import ResumeParseStatus


logger = logging.getLogger(__name__)

EXTRACTION_REASON_FAILED = ResumeParseStatus.PARSING_FAILED
EXTRACTION_REASON_EMPTY_TEXT = ResumeParseStatus.EMPTY_TEXT
EXTRACTION_REASON_INSUFFICIENT_TEXT = ResumeParseStatus.INSUFFICIENT_TEXT
EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF = ResumeParseStatus.SCANNED_OR_IMAGE_PDF
EXTRACTION_REASON_UNSUPPORTED_STRUCTURE = ResumeParseStatus.UNSUPPORTED_OR_UNSAFE_STRUCTURE
EXTRACTION_REASON_BUDGET_EXCEEDED = ResumeParseStatus.PARSING_TIMEOUT_OR_BUDGET_EXCEEDED
EXTRACTION_REASON_BLOCKED_BY_POLICY = ResumeParseStatus.QUARANTINED_OR_BLOCKED_BY_POLICY


@dataclass(slots=True)
class ResumeExtractionResult:
    text: str
    status: str
    diagnostics: dict[str, object] = field(default_factory=dict)


class ResumeTextExtractionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        reason: str = EXTRACTION_REASON_FAILED,
        diagnostics: dict[str, object] | None = None,
        extracted_text: str = "",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.diagnostics = diagnostics or {}
        self.extracted_text = extracted_text


class ResumeTextExtractionService:
    supported_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    }
    supported_extensions = {".pdf", ".docx"}

    def __init__(self) -> None:
        config = getattr(settings, "RESUME_INGESTION", {})
        self.enable_pdf_parsing = bool(config.get("ENABLE_PDF_PARSING", True))
        self.enable_docx_parsing = bool(config.get("ENABLE_DOCX_PARSING", True))
        self.enable_pypdf = bool(config.get("ENABLE_PYPDF", True))
        self.enable_pdf_regex_fallback = bool(config.get("ENABLE_PDF_REGEX_FALLBACK", True))
        self.enable_python_docx = bool(config.get("ENABLE_PYTHON_DOCX", False))
        self.pdf_max_pages = int(config.get("PDF_MAX_PAGES", 25))
        self.pdf_max_images = int(config.get("PDF_MAX_IMAGES", 128))
        self.pdf_max_characters = int(config.get("PDF_MAX_CHARACTERS", 120000))
        self.docx_max_archive_files = int(config.get("DOCX_MAX_ARCHIVE_FILES", 200))
        self.docx_max_uncompressed_bytes = int(config.get("DOCX_MAX_UNCOMPRESSED_BYTES", 8 * 1024 * 1024))
        self.docx_max_xml_bytes = int(config.get("DOCX_MAX_XML_BYTES", 4 * 1024 * 1024))
        self.docx_max_compression_ratio = max(
            1,
            int(config.get("DOCX_MAX_COMPRESSION_RATIO", 100)),
        )
        self.min_trusted_text_characters = int(config.get("MIN_TRUSTED_TEXT_CHARACTERS", 80))
        self.min_trusted_words = int(config.get("MIN_TRUSTED_WORDS", 12))

    def extract(self, *, file_bytes: bytes, content_type: str, filename: str) -> ResumeExtractionResult:
        normalized_name = filename.lower()
        if content_type == "application/pdf" or normalized_name.endswith(".pdf"):
            if not self.enable_pdf_parsing:
                raise self._policy_error(
                    content_kind="pdf",
                    suggestion="PDF parsing is disabled by configuration. Upload DOCX or re-enable PDF parsing.",
                )
            return self._extract_pdf(file_bytes)
        if (
            content_type
            in {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/zip",
            }
            or normalized_name.endswith(".docx")
        ):
            if not self.enable_docx_parsing:
                raise self._policy_error(
                    content_kind="docx",
                    suggestion="DOCX parsing is disabled by configuration. Upload PDF or re-enable DOCX parsing.",
                )
            return self._extract_docx(file_bytes)
        raise ResumeTextExtractionError(
            "Unsupported resume format.",
            reason=ResumeParseStatus.UNSUPPORTED_FILE_TYPE,
            diagnostics={
                "content_kind": "unknown",
                "blocked_by_policy": False,
                "suggestion": "Upload a PDF or DOCX resume.",
            },
        )

    def extract_text(self, *, file_bytes: bytes, content_type: str, filename: str) -> str:
        return self.extract(
            file_bytes=file_bytes,
            content_type=content_type,
            filename=filename,
        ).text

    def _extract_docx(self, file_bytes: bytes) -> ResumeExtractionResult:
        diagnostics = {
            "content_kind": "docx",
            "parser_used": None,
            "blocked_by_policy": False,
            "structurally_safe": False,
            "suggestion": None,
        }
        archive_info = self._inspect_docx_archive(file_bytes)
        document_xml = archive_info.pop("document_xml")
        diagnostics.update(archive_info)
        diagnostics["structurally_safe"] = True

        text = self._extract_docx_xml_text(document_xml)
        diagnostics.update(
            {
                "parser_used": "xml_fallback",
                "normalized_character_count": len(text),
                "word_count": self._count_words(text),
                "paragraph_count": text.count("\n") + (1 if text else 0),
            }
        )
        if text:
            return self._finalize_result(text=text, diagnostics=diagnostics)

        if self.enable_python_docx and Document is not None:
            try:
                document = Document(BytesIO(file_bytes))
                paragraphs = [
                    normalized
                    for paragraph in document.paragraphs
                    if (normalized := self._normalize_extracted_text(paragraph.text))
                ]
                text = "\n".join(paragraphs).strip()
                diagnostics.update(
                    {
                        "parser_used": "python_docx",
                        "normalized_character_count": len(text),
                        "word_count": self._count_words(text),
                        "paragraph_count": len(paragraphs),
                    }
                )
                if text:
                    return self._finalize_result(text=text, diagnostics=diagnostics)
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("resume_docx_python_docx_failed error=%s", exc)
                diagnostics["python_docx_error"] = str(exc)

        logger.warning("resume_docx_empty_text parser=%s", diagnostics["parser_used"])
        raise ResumeTextExtractionError(
            "DOCX file did not contain readable text.",
            reason=EXTRACTION_REASON_EMPTY_TEXT,
            diagnostics={
                **diagnostics,
                "suggestion": "Open the file, confirm the text is selectable, then export a fresh DOCX or PDF.",
            },
        )

    def _inspect_docx_archive(self, file_bytes: bytes) -> dict[str, object]:
        if not file_bytes.startswith(b"PK"):
            raise ResumeTextExtractionError(
                "The DOCX file is not a valid OpenXML archive.",
                reason=ResumeParseStatus.INVALID_FILE,
                diagnostics={
                    "content_kind": "docx",
                    "structurally_safe": False,
                    "suggestion": "Upload a standard DOCX file exported from your editor.",
                },
            )

        try:
            with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
                members = archive.infolist()
                if len(members) > self.docx_max_archive_files:
                    raise ResumeTextExtractionError(
                        "DOCX archive contains too many entries.",
                        reason=EXTRACTION_REASON_BUDGET_EXCEEDED,
                        diagnostics={
                            "content_kind": "docx",
                            "archive_member_count": len(members),
                            "max_archive_member_count": self.docx_max_archive_files,
                            "structurally_safe": False,
                            "suggestion": "Re-export the file as a clean DOCX with standard document contents only.",
                        },
                    )

                total_uncompressed = 0
                max_ratio = 0
                for member in members:
                    total_uncompressed += int(member.file_size or 0)
                    compressed_size = int(member.compress_size or 0)
                    if compressed_size > 0:
                        max_ratio = max(max_ratio, round(member.file_size / compressed_size, 2))
                    elif member.file_size:
                        max_ratio = max(max_ratio, float(member.file_size))

                if total_uncompressed > self.docx_max_uncompressed_bytes:
                    raise ResumeTextExtractionError(
                        "DOCX archive expands beyond the safe parsing budget.",
                        reason=EXTRACTION_REASON_BUDGET_EXCEEDED,
                        diagnostics={
                            "content_kind": "docx",
                            "archive_member_count": len(members),
                            "total_uncompressed_bytes": total_uncompressed,
                            "max_uncompressed_bytes": self.docx_max_uncompressed_bytes,
                            "structurally_safe": False,
                            "suggestion": "Re-save the document without embedded assets or template bloat.",
                        },
                    )

                if max_ratio > self.docx_max_compression_ratio:
                    raise ResumeTextExtractionError(
                        "DOCX archive compression ratio looks unsafe.",
                        reason=EXTRACTION_REASON_UNSUPPORTED_STRUCTURE,
                        diagnostics={
                            "content_kind": "docx",
                            "archive_member_count": len(members),
                            "max_compression_ratio": max_ratio,
                            "allowed_compression_ratio": self.docx_max_compression_ratio,
                            "structurally_safe": False,
                            "suggestion": "Re-export the resume as a clean DOCX or PDF before uploading it again.",
                        },
                    )

                try:
                    document_info = archive.getinfo("word/document.xml")
                except KeyError as exc:
                    raise ResumeTextExtractionError(
                        "DOCX file is missing the main document body.",
                        reason=EXTRACTION_REASON_UNSUPPORTED_STRUCTURE,
                        diagnostics={
                            "content_kind": "docx",
                            "archive_member_count": len(members),
                            "structurally_safe": False,
                            "suggestion": "Upload a standard DOCX file with a normal document body.",
                        },
                    ) from exc

                if document_info.file_size > self.docx_max_xml_bytes:
                    raise ResumeTextExtractionError(
                        "DOCX document XML exceeds the safe parsing budget.",
                        reason=EXTRACTION_REASON_BUDGET_EXCEEDED,
                        diagnostics={
                            "content_kind": "docx",
                            "document_xml_bytes": document_info.file_size,
                            "max_document_xml_bytes": self.docx_max_xml_bytes,
                            "structurally_safe": False,
                            "suggestion": "Remove excessive embedded content and re-export the document.",
                        },
                    )

                document_xml = archive.read("word/document.xml")
        except ResumeTextExtractionError:
            raise
        except zipfile.BadZipFile as exc:
            raise ResumeTextExtractionError(
                "Unable to read DOCX archive safely.",
                reason=ResumeParseStatus.INVALID_FILE,
                diagnostics={
                    "content_kind": "docx",
                    "structurally_safe": False,
                    "suggestion": "Upload a valid DOCX file exported from your editor.",
                },
            ) from exc

        return {
            "archive_member_count": len(members),
            "total_uncompressed_bytes": total_uncompressed,
            "max_compression_ratio": max_ratio,
            "document_xml": document_xml,
            "document_xml_bytes": len(document_xml),
        }

    def _extract_docx_xml_text(self, document_xml: bytes) -> str:
        try:
            root = ElementTree.fromstring(document_xml)
        except ElementTree.ParseError as exc:
            raise ResumeTextExtractionError(
                "Unable to parse DOCX content safely.",
                reason=EXTRACTION_REASON_UNSUPPORTED_STRUCTURE,
                diagnostics={
                    "content_kind": "docx",
                    "structurally_safe": False,
                    "suggestion": "Re-export the document as a standard DOCX or PDF.",
                },
            ) from exc

        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            line = self._normalize_extracted_text("".join(texts))
            if line:
                paragraphs.append(line)
        return "\n".join(paragraphs).strip()

    def _extract_pdf(self, file_bytes: bytes) -> ResumeExtractionResult:
        is_pdf_signature = file_bytes.lstrip().startswith(b"%PDF")
        decoded = file_bytes.decode("latin-1", errors="ignore")
        fallback_page_count = len(re.findall(r"/Type\s*/Page\b", decoded)) if is_pdf_signature else 0
        image_object_count = decoded.count("/Subtype /Image")
        diagnostics: dict[str, object] = {
            "content_kind": "pdf",
            "parser_used": None,
            "page_count": fallback_page_count,
            "pages_with_text": 0,
            "image_object_count": image_object_count,
            "has_text_operators": bool(re.search(r"\b(Tj|TJ|BT|ET)\b", decoded)),
            "blocked_by_policy": False,
            "structurally_safe": is_pdf_signature,
            "suggestion": None,
        }

        if not is_pdf_signature:
            raise ResumeTextExtractionError(
                "The uploaded PDF does not have a valid PDF signature.",
                reason=ResumeParseStatus.UNSUPPORTED_STRUCTURE,
                diagnostics={
                    **diagnostics,
                    "structurally_safe": False,
                    "suggestion": "Export the resume again as a standard PDF or upload a DOCX version.",
                },
            )

        if fallback_page_count > self.pdf_max_pages:
            raise ResumeTextExtractionError(
                "PDF exceeds the configured page parsing budget.",
                reason=EXTRACTION_REASON_BUDGET_EXCEEDED,
                diagnostics={
                    **diagnostics,
                    "max_page_count": self.pdf_max_pages,
                    "suggestion": "Upload a shorter PDF or export only the resume pages.",
                },
            )

        if image_object_count > self.pdf_max_images:
            raise ResumeTextExtractionError(
                "PDF contains too many embedded image objects for safe parsing.",
                reason=EXTRACTION_REASON_UNSUPPORTED_STRUCTURE,
                diagnostics={
                    **diagnostics,
                    "max_image_object_count": self.pdf_max_images,
                    "suggestion": "Export the resume as a text PDF or DOCX with fewer embedded assets.",
                },
            )

        if self.enable_pypdf and PdfReader is not None:
            try:
                reader = PdfReader(BytesIO(file_bytes))
                page_count = len(reader.pages)
                if page_count > self.pdf_max_pages:
                    raise ResumeTextExtractionError(
                        "PDF exceeds the configured page parsing budget.",
                        reason=EXTRACTION_REASON_BUDGET_EXCEEDED,
                        diagnostics={
                            **diagnostics,
                            "page_count": page_count,
                            "max_page_count": self.pdf_max_pages,
                            "suggestion": "Upload a shorter PDF or export only the resume pages.",
                        },
                    )

                pages: list[str] = []
                for index, page in enumerate(reader.pages):
                    extracted = page.extract_text() or ""
                    normalized = self._normalize_extracted_text(extracted)
                    if normalized:
                        pages.append(normalized)
                    else:
                        logger.info("resume_pdf_empty_page page=%d", index)
                    combined_length = sum(len(value) for value in pages)
                    if combined_length > self.pdf_max_characters:
                        raise ResumeTextExtractionError(
                            "PDF text extraction exceeded the configured parsing budget.",
                            reason=EXTRACTION_REASON_BUDGET_EXCEEDED,
                            diagnostics={
                                **diagnostics,
                                "page_count": page_count,
                                "normalized_character_count": combined_length,
                                "max_normalized_character_count": self.pdf_max_characters,
                                "suggestion": "Trim the PDF to the resume pages before uploading it again.",
                            },
                        )

                text = "\n\n".join(pages).strip()
                diagnostics.update(
                    {
                        "parser_used": "pypdf",
                        "page_count": page_count,
                        "pages_with_text": len(pages),
                        "normalized_character_count": len(text),
                        "word_count": self._count_words(text),
                    }
                )
                if text:
                    return self._finalize_result(text=text, diagnostics=diagnostics)
                logger.warning("resume_pdf_empty_text parser=pypdf page_count=%d", page_count)
            except ResumeTextExtractionError:
                raise
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("resume_pdf_pypdf_failed error=%s", exc)
                diagnostics["pypdf_error"] = str(exc)

        if not self.enable_pdf_regex_fallback:
            raise self._policy_error(
                content_kind="pdf",
                suggestion="PDF regex fallback parsing is disabled by configuration.",
                diagnostics=diagnostics,
            )

        text_segments = re.findall(r"\((.*?)(?<!\\)\)\s*Tj", decoded, flags=re.DOTALL)
        text_segments.extend(
            fragment
            for block in re.findall(r"\[(.*?)\]\s*TJ", decoded, flags=re.DOTALL)
            for fragment in re.findall(r"\((.*?)(?<!\\)\)", block, flags=re.DOTALL)
        )
        text_segments.extend(re.findall(r"\((.*?)(?<!\\)\)\s*'", decoded, flags=re.DOTALL))
        text_segments.extend(re.findall(r"\((.*?)(?<!\\)\)\s*\"", decoded, flags=re.DOTALL))
        text_segments.extend(
            self._decode_pdf_hex_text(fragment)
            for fragment in re.findall(r"<([0-9A-Fa-f]+)>\s*Tj", decoded)
        )

        cleaned = [
            self._normalize_extracted_text(self._decode_pdf_literal_text(segment))
            for segment in text_segments
        ]
        unique_segments = [segment for segment in cleaned if segment]
        text = "\n".join(unique_segments).strip()
        diagnostics.update(
            {
                "parser_used": "regex_fallback",
                "pages_with_text": 1 if text else 0,
                "normalized_character_count": len(text),
                "word_count": self._count_words(text),
            }
        )
        if text:
            return self._finalize_result(text=text, diagnostics=diagnostics)

        reason = self._classify_pdf_failure(diagnostics=diagnostics)
        logger.warning(
            "resume_pdf_empty_text parser=fallback image_object_count=%d has_text_operators=%s",
            image_object_count,
            diagnostics["has_text_operators"],
        )
        raise ResumeTextExtractionError(
            self._build_pdf_failure_message(reason),
            reason=reason,
            diagnostics={
                **diagnostics,
                "likely_scanned_pdf": reason == EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF,
                "suggestion": self._build_pdf_suggestion(reason),
            },
        )

    def _finalize_result(self, *, text: str, diagnostics: dict[str, object]) -> ResumeExtractionResult:
        normalized_text = text.strip()
        character_count = len(normalized_text)
        word_count = self._count_words(normalized_text)
        diagnostics = {
            **diagnostics,
            "normalized_character_count": character_count,
            "word_count": word_count,
            "minimum_trusted_characters": self.min_trusted_text_characters,
            "minimum_trusted_words": self.min_trusted_words,
        }
        if (
            character_count < self.min_trusted_text_characters
            or word_count < self.min_trusted_words
        ):
            diagnostics["suggestion"] = (
                "Upload a clearer resume export with more selectable text before analysis or matching."
            )
            return ResumeExtractionResult(
                text=normalized_text,
                status=ResumeParseStatus.INSUFFICIENT_TEXT,
                diagnostics=diagnostics,
            )
        return ResumeExtractionResult(
            text=normalized_text,
            status=ResumeParseStatus.COMPLETED,
            diagnostics=diagnostics,
        )

    def _classify_pdf_failure(self, *, diagnostics: dict[str, object]) -> str:
        image_objects = int(diagnostics.get("image_object_count", 0) or 0)
        if image_objects > 0:
            return EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF
        return EXTRACTION_REASON_EMPTY_TEXT

    def _build_pdf_failure_message(self, reason: str) -> str:
        if reason == EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF:
            return "PDF appears to be scanned or image-based and does not contain selectable text."
        if reason == EXTRACTION_REASON_UNSUPPORTED_STRUCTURE:
            return "PDF structure could not be parsed safely."
        return "PDF file did not contain extractable text."

    def _build_pdf_suggestion(self, reason: str) -> str:
        if reason == EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF:
            return "Export the resume as a text PDF or upload a DOCX version with selectable text."
        if reason == EXTRACTION_REASON_UNSUPPORTED_STRUCTURE:
            return "Re-export the file as a standard PDF or DOCX and try again."
        return "Confirm the PDF contains selectable text, then re-export it as a text PDF or DOCX."

    def _policy_error(
        self,
        *,
        content_kind: str,
        suggestion: str,
        diagnostics: dict[str, object] | None = None,
    ) -> ResumeTextExtractionError:
        base = {
            "content_kind": content_kind,
            "blocked_by_policy": True,
            "suggestion": suggestion,
        }
        if diagnostics:
            base.update(diagnostics)
            base["blocked_by_policy"] = True
            base["suggestion"] = suggestion
        return ResumeTextExtractionError(
            "Resume parsing was blocked by policy.",
            reason=EXTRACTION_REASON_BLOCKED_BY_POLICY,
            diagnostics=base,
        )

    def _decode_pdf_literal_text(self, value: str) -> str:
        replacements = {
            r"\(": "(",
            r"\)": ")",
            r"\n": "\n",
            r"\r": "\r",
            r"\t": "\t",
            r"\\": "\\",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
        return value.strip()

    def _decode_pdf_hex_text(self, value: str) -> str:
        try:
            decoded = bytes.fromhex(value).decode("latin-1", errors="ignore")
        except ValueError:
            return ""
        return self._normalize_extracted_text(decoded)

    def _normalize_extracted_text(self, value: str) -> str:
        replacements = {
            "\x00": " ",
            "\u00a0": " ",
            "\u00ad": "",
            "\uf0b7": " ",
            "\uf0a7": " ",
            "\uf0d8": " ",
            "\u2022": "\n",
            "\u200b": " ",
            "\u200c": " ",
            "\u200d": " ",
            "\ufeff": " ",
            "\u2013": "-",
            "\u2014": "-",
            "\u2212": "-",
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
        }
        for source, target in replacements.items():
            value = value.replace(source, target)

        value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
        value = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", value)
        value = re.sub(r"[ \t]*\n[ \t]*", "\n", value)
        value = re.sub(r"[^\S\n]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        value = re.sub(r"[^\S\n]*\|\s*", "\n", value)
        value = "".join(ch for ch in value if ch == "\n" or ch.isprintable())
        value = re.sub(r" ?\n ?", "\n", value)
        return value.strip()

    def _count_words(self, text: str) -> int:
        return len(re.findall(r"\b\w+\b", text))
