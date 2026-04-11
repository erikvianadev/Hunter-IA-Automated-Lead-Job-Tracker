from __future__ import annotations

import logging
import re
import zipfile
from dataclasses import dataclass
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
EXTRACTION_REASON_UNSUPPORTED_STRUCTURE = "unsupported_structure"


@dataclass(slots=True)
class ResumeExtractionResult:
    text: str
    status: str


class ResumeTextExtractionError(Exception):
    def __init__(self, message: str, *, reason: str = EXTRACTION_REASON_FAILED) -> None:
        super().__init__(message)
        self.reason = reason


class ResumeTextExtractionService:
    supported_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    supported_extensions = {".pdf", ".docx"}

    def extract(self, *, file_bytes: bytes, content_type: str, filename: str) -> ResumeExtractionResult:
        normalized_name = filename.lower()
        if content_type == "application/pdf" or normalized_name.endswith(".pdf"):
            return ResumeExtractionResult(
                text=self._extract_pdf_text(file_bytes),
                status="completed",
            )
        if (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or normalized_name.endswith(".docx")
        ):
            return ResumeExtractionResult(
                text=self._extract_docx_text(file_bytes),
                status="completed",
            )
        raise ResumeTextExtractionError("Unsupported resume format.")

    def extract_text(self, *, file_bytes: bytes, content_type: str, filename: str) -> str:
        return self.extract(
            file_bytes=file_bytes,
            content_type=content_type,
            filename=filename,
        ).text

    def _extract_docx_text(self, file_bytes: bytes) -> str:
        if Document is not None:
            try:
                document = Document(BytesIO(file_bytes))
                paragraphs = [
                    self._normalize_whitespace(paragraph.text)
                    for paragraph in document.paragraphs
                    if self._normalize_whitespace(paragraph.text)
                ]
                text = "\n".join(paragraphs).strip()
                if text:
                    return text
                logger.warning("resume_docx_empty_text parser=python_docx")
                raise ResumeTextExtractionError(
                    "DOCX file did not contain readable text.",
                    reason=EXTRACTION_REASON_EMPTY_TEXT,
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
            raise ResumeTextExtractionError("Unable to read DOCX file.") from exc

        try:
            root = ElementTree.fromstring(document_xml)
        except ElementTree.ParseError as exc:
            logger.warning("resume_docx_parse_failed error=%s", exc)
            raise ResumeTextExtractionError(
                "Unable to parse DOCX content.",
                reason=EXTRACTION_REASON_UNSUPPORTED_STRUCTURE,
            ) from exc

        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            line = self._normalize_whitespace("".join(texts))
            if line:
                paragraphs.append(line)
        text = "\n".join(paragraphs).strip()
        if not text:
            logger.warning("resume_docx_empty_text parser=xml_fallback")
            raise ResumeTextExtractionError(
                "DOCX file did not contain readable text.",
                reason=EXTRACTION_REASON_EMPTY_TEXT,
            )
        return text

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        is_pdf_signature = file_bytes.lstrip().startswith(b"%PDF")
        if PdfReader is not None:
            try:
                reader = PdfReader(BytesIO(file_bytes))
                pages: list[str] = []
                for index, page in enumerate(reader.pages):
                    extracted = page.extract_text() or ""
                    normalized = self._normalize_whitespace(extracted)
                    if normalized:
                        pages.append(normalized)
                    else:
                        logger.info("resume_pdf_empty_page page=%d", index)
                text = "\n".join(pages).strip()
                if text:
                    return text
                logger.warning(
                    "resume_pdf_empty_text parser=pypdf page_count=%d",
                    len(reader.pages),
                )
                raise ResumeTextExtractionError(
                    "PDF file did not contain extractable text.",
                    reason=EXTRACTION_REASON_EMPTY_TEXT,
                )
            except ResumeTextExtractionError:
                raise
            except Exception as exc:
                logger.warning("resume_pdf_pypdf_failed error=%s", exc)

        decoded = file_bytes.decode("latin-1", errors="ignore")
        streams = re.findall(r"stream(.*?)endstream", decoded, flags=re.DOTALL)
        text_segments = re.findall(r"\((.*?)(?<!\\)\)\s*Tj", decoded, flags=re.DOTALL)
        text_segments.extend(
            fragment
            for block in re.findall(r"\[(.*?)\]\s*TJ", decoded, flags=re.DOTALL)
            for fragment in re.findall(r"\((.*?)(?<!\\)\)", block, flags=re.DOTALL)
        )
        text_segments.extend(
            self._decode_pdf_hex_text(fragment)
            for stream in streams
            for fragment in re.findall(r"<([0-9A-Fa-f]+)>\s*Tj", stream)
        )
        cleaned = [
            self._normalize_whitespace(self._decode_pdf_literal_text(segment))
            for segment in text_segments
        ]
        text = "\n".join(segment for segment in cleaned if segment).strip()
        if not text:
            reason = (
                EXTRACTION_REASON_EMPTY_TEXT
                if is_pdf_signature
                else EXTRACTION_REASON_UNSUPPORTED_STRUCTURE
            )
            logger.warning("resume_pdf_empty_text parser=fallback stream_count=%d", len(streams))
            raise ResumeTextExtractionError(
                "PDF file did not contain extractable text.",
                reason=reason,
            )
        return text

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
            return bytes.fromhex(value).decode("latin-1", errors="ignore").strip()
        except ValueError:
            return ""

    def _normalize_whitespace(self, value: str) -> str:
        value = value.replace("\x00", " ")
        value = re.sub(r"[ \t\f\v]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()
