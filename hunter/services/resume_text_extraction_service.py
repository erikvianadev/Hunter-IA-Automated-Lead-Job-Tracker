from __future__ import annotations

import logging
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from xml.etree import ElementTree

try:
    from docx import Document
except ImportError:  # pragma: no cover - optional dependency
    Document = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency
    PdfReader = None


logger = logging.getLogger(__name__)

EXTRACTION_REASON_FAILED = "failed"
EXTRACTION_REASON_EMPTY_TEXT = "empty_text"
EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF = "scanned_or_image_pdf"
EXTRACTION_REASON_UNSUPPORTED_STRUCTURE = "unsupported_structure"


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
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.diagnostics = diagnostics or {}


class ResumeTextExtractionService:
    supported_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    supported_extensions = {".pdf", ".docx"}

    def extract(self, *, file_bytes: bytes, content_type: str, filename: str) -> ResumeExtractionResult:
        normalized_name = filename.lower()
        if content_type == "application/pdf" or normalized_name.endswith(".pdf"):
            return self._extract_pdf(file_bytes)
        if (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or normalized_name.endswith(".docx")
        ):
            return self._extract_docx(file_bytes)
        raise ResumeTextExtractionError("Unsupported resume format.")

    def extract_text(self, *, file_bytes: bytes, content_type: str, filename: str) -> str:
        return self.extract(
            file_bytes=file_bytes,
            content_type=content_type,
            filename=filename,
        ).text

    def _extract_docx(self, file_bytes: bytes) -> ResumeExtractionResult:
        diagnostics: dict[str, object] = {
            "content_kind": "docx",
            "parser_used": None,
            "suggestion": None,
        }
        if Document is not None:
            try:
                document = Document(BytesIO(file_bytes))
                paragraphs = [
                    normalized
                    for paragraph in document.paragraphs
                    if (normalized := self._normalize_extracted_text(paragraph.text))
                ]
                text = "\n".join(paragraphs).strip()
                if text:
                    diagnostics.update(
                        {
                            "parser_used": "python_docx",
                            "paragraph_count": len(paragraphs),
                            "normalized_character_count": len(text),
                        }
                    )
                    return ResumeExtractionResult(text=text, status="completed", diagnostics=diagnostics)
                logger.warning("resume_docx_empty_text parser=python_docx")
                raise ResumeTextExtractionError(
                    "DOCX file did not contain readable text.",
                    reason=EXTRACTION_REASON_EMPTY_TEXT,
                    diagnostics={
                        **diagnostics,
                        "parser_used": "python_docx",
                        "paragraph_count": len(document.paragraphs),
                        "suggestion": "Re-export the resume as a DOCX with selectable text.",
                    },
                )
            except ResumeTextExtractionError:
                raise
            except Exception as exc:
                logger.warning("resume_docx_python_docx_failed error=%s", exc)

        try:
            with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
                document_xml = archive.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile) as exc:
            logger.warning("resume_docx_read_failed error=%s", exc)
            raise ResumeTextExtractionError(
                "Unable to read DOCX file.",
                diagnostics={
                    **diagnostics,
                    "parser_used": "zip_fallback",
                    "suggestion": "Re-save the document as a standard DOCX and upload it again.",
                },
            ) from exc

        try:
            root = ElementTree.fromstring(document_xml)
        except ElementTree.ParseError as exc:
            logger.warning("resume_docx_parse_failed error=%s", exc)
            raise ResumeTextExtractionError(
                "Unable to parse DOCX content.",
                reason=EXTRACTION_REASON_UNSUPPORTED_STRUCTURE,
                diagnostics={
                    **diagnostics,
                    "parser_used": "xml_fallback",
                    "suggestion": "Re-export the document as a standard DOCX or PDF with selectable text.",
                },
            ) from exc

        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            line = self._normalize_extracted_text("".join(texts))
            if line:
                paragraphs.append(line)
        text = "\n".join(paragraphs).strip()
        if not text:
            logger.warning("resume_docx_empty_text parser=xml_fallback")
            raise ResumeTextExtractionError(
                "DOCX file did not contain readable text.",
                reason=EXTRACTION_REASON_EMPTY_TEXT,
                diagnostics={
                    **diagnostics,
                    "parser_used": "xml_fallback",
                    "paragraph_count": len(paragraphs),
                    "suggestion": "Open the file, confirm the text is selectable, then export a fresh DOCX or PDF.",
                },
            )
        diagnostics.update(
            {
                "parser_used": "xml_fallback",
                "paragraph_count": len(paragraphs),
                "normalized_character_count": len(text),
            }
        )
        return ResumeExtractionResult(text=text, status="completed", diagnostics=diagnostics)

    def _extract_pdf(self, file_bytes: bytes) -> ResumeExtractionResult:
        is_pdf_signature = file_bytes.lstrip().startswith(b"%PDF")
        decoded = file_bytes.decode("latin-1", errors="ignore")
        fallback_page_count = max(len(re.findall(r"/Type\s*/Page\b", decoded)), 1) if is_pdf_signature else 0
        base_diagnostics: dict[str, object] = {
            "content_kind": "pdf",
            "parser_used": None,
            "page_count": 0,
            "pages_with_text": 0,
            "image_object_count": decoded.count("/Subtype /Image"),
            "has_text_operators": bool(re.search(r"\b(Tj|TJ|BT|ET)\b", decoded)),
            "suggestion": None,
        }

        if PdfReader is not None:
            try:
                reader = PdfReader(BytesIO(file_bytes))
                pages: list[str] = []
                page_count = len(reader.pages)
                for index, page in enumerate(reader.pages):
                    extracted = page.extract_text() or ""
                    normalized = self._normalize_extracted_text(extracted)
                    if normalized:
                        pages.append(normalized)
                    else:
                        logger.info("resume_pdf_empty_page page=%d", index)
                text = "\n\n".join(pages).strip()
                if text:
                    base_diagnostics.update(
                        {
                            "parser_used": "pypdf",
                            "page_count": page_count,
                            "pages_with_text": len(pages),
                            "normalized_character_count": len(text),
                        }
                    )
                    return ResumeExtractionResult(text=text, status="completed", diagnostics=base_diagnostics)
                logger.warning(
                    "resume_pdf_empty_text parser=pypdf page_count=%d",
                    page_count,
                )
            except Exception as exc:
                logger.warning("resume_pdf_pypdf_failed error=%s", exc)

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
        if text:
            base_diagnostics.update(
                {
                    "parser_used": "regex_fallback",
                    "page_count": fallback_page_count,
                    "pages_with_text": 1,
                    "normalized_character_count": len(text),
                }
            )
            return ResumeExtractionResult(text=text, status="completed", diagnostics=base_diagnostics)

        reason = self._classify_pdf_failure(
            is_pdf_signature=is_pdf_signature,
            diagnostics=base_diagnostics,
        )
        logger.warning(
            "resume_pdf_empty_text parser=fallback image_object_count=%d has_text_operators=%s",
            base_diagnostics["image_object_count"],
            base_diagnostics["has_text_operators"],
        )
        raise ResumeTextExtractionError(
            self._build_pdf_failure_message(reason),
            reason=reason,
            diagnostics={
                **base_diagnostics,
                "parser_used": base_diagnostics["parser_used"] or "regex_fallback",
                "page_count": fallback_page_count,
                "pages_with_text": 0,
                "likely_scanned_pdf": reason == EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF,
                "suggestion": self._build_pdf_suggestion(reason),
            },
        )

    def _classify_pdf_failure(self, *, is_pdf_signature: bool, diagnostics: dict[str, object]) -> str:
        if not is_pdf_signature:
            return EXTRACTION_REASON_UNSUPPORTED_STRUCTURE
        image_objects = int(diagnostics.get("image_object_count", 0) or 0)
        has_text_operators = bool(diagnostics.get("has_text_operators"))
        if image_objects > 0 and not has_text_operators:
            return EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF
        if image_objects > 0:
            return EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF
        return EXTRACTION_REASON_EMPTY_TEXT

    def _build_pdf_failure_message(self, reason: str) -> str:
        if reason == EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF:
            return "PDF appears to be scanned or image-based and does not contain selectable text."
        if reason == EXTRACTION_REASON_UNSUPPORTED_STRUCTURE:
            return "PDF structure could not be parsed."
        return "PDF file did not contain extractable text."

    def _build_pdf_suggestion(self, reason: str) -> str:
        if reason == EXTRACTION_REASON_SCANNED_OR_IMAGE_PDF:
            return "Export the resume as a text PDF or upload a DOCX version with selectable text."
        if reason == EXTRACTION_REASON_UNSUPPORTED_STRUCTURE:
            return "Re-export the file as a standard PDF or DOCX and try again."
        return "Confirm the PDF contains selectable text, then re-export it as a text PDF or DOCX."

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
