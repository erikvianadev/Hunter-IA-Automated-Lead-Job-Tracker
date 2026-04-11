from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO
from xml.etree import ElementTree


logger = logging.getLogger(__name__)


class ResumeTextExtractionError(Exception):
    pass


class ResumeTextExtractionService:
    supported_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    supported_extensions = {".pdf", ".docx"}

    def extract_text(self, *, file_bytes: bytes, content_type: str, filename: str) -> str:
        normalized_name = filename.lower()
        if content_type == "application/pdf" or normalized_name.endswith(".pdf"):
            return self._extract_pdf_text(file_bytes)
        if (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or normalized_name.endswith(".docx")
        ):
            return self._extract_docx_text(file_bytes)
        raise ResumeTextExtractionError("Unsupported resume format.")

    def _extract_docx_text(self, file_bytes: bytes) -> str:
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
            raise ResumeTextExtractionError("Unable to parse DOCX content.") from exc

        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            line = "".join(texts).strip()
            if line:
                paragraphs.append(line)
        text = "\n".join(paragraphs).strip()
        if not text:
            logger.warning("resume_docx_empty_text")
            raise ResumeTextExtractionError("DOCX file did not contain readable text.")
        return text

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
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
        cleaned = [self._decode_pdf_literal_text(segment) for segment in text_segments]
        text = "\n".join(segment for segment in cleaned if segment).strip()
        if not text:
            logger.warning("resume_pdf_empty_text stream_count=%d", len(streams))
            raise ResumeTextExtractionError("Unable to extract text from PDF file.")
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
