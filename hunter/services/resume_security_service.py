from __future__ import annotations

import re
from dataclasses import dataclass

from django.conf import settings

from hunter.choices import ResumeParseStatus
from hunter.models.models import Resume


LEGACY_STATUS_ALIASES = {
    ResumeParseStatus.FAILED: ResumeParseStatus.PARSING_FAILED,
}

STATUS_MESSAGES = {
    ResumeParseStatus.PENDING: (
        "Resume ingestion has not started yet. Upload the file again if this state does not change."
    ),
    ResumeParseStatus.PROCESSING: (
        "Resume ingestion is still processing. Wait for parsing to finish before using this resume."
    ),
    ResumeParseStatus.UPLOAD_TOO_LARGE: (
        "The uploaded resume exceeded the configured file size limit."
    ),
    ResumeParseStatus.INVALID_FILE: (
        "The uploaded file does not look like a valid PDF or DOCX resume."
    ),
    ResumeParseStatus.UNSUPPORTED_FILE_TYPE: (
        "Only supported PDF or DOCX resumes can be processed."
    ),
    ResumeParseStatus.PARSING_FAILED: (
        "The resume could not be parsed safely. Upload a cleaner export and try again."
    ),
    ResumeParseStatus.PARSING_TIMEOUT_OR_BUDGET_EXCEEDED: (
        "The resume exceeded safe parsing limits and was blocked."
    ),
    ResumeParseStatus.EMPTY_TEXT: (
        "The uploaded file did not contain readable text."
    ),
    ResumeParseStatus.INSUFFICIENT_TEXT: (
        "The uploaded file produced too little reliable text for downstream analysis."
    ),
    ResumeParseStatus.DOCUMENT_NOT_RESUME_LIKE: (
        "Recebemos o arquivo, mas ele nao parece um curriculo utilizavel. Envie um CV real em PDF ou DOCX com conteudo profissional claro."
    ),
    ResumeParseStatus.INSUFFICIENT_RESUME_SIGNALS: (
        "Recebemos o arquivo, mas faltam sinais suficientes de curriculo para liberar analise, senioridade ou match."
    ),
    ResumeParseStatus.BLOCKED_FOR_LOW_RESUME_CONFIDENCE: (
        "Recebemos o arquivo, mas a confianca de que ele e um curriculo utilizavel ficou baixa demais para seguir."
    ),
    ResumeParseStatus.SCANNED_OR_IMAGE_PDF: (
        "The uploaded PDF appears to be scanned or image-based and cannot be analyzed safely."
    ),
    ResumeParseStatus.UNSUPPORTED_STRUCTURE: (
        "The uploaded file could not be parsed as a supported resume structure."
    ),
    ResumeParseStatus.UNSUPPORTED_OR_UNSAFE_STRUCTURE: (
        "The uploaded file contains an unsupported or unsafe structure."
    ),
    ResumeParseStatus.QUARANTINED_OR_BLOCKED_BY_POLICY: (
        "Resume processing for this file or format is currently blocked by policy."
    ),
}


@dataclass(slots=True)
class ResumeTrustDecision:
    trusted: bool
    normalized_status: str
    message: str
    diagnostics: dict[str, object]


class ResumeTrustError(Exception):
    def __init__(self, *, action: str, decision: ResumeTrustDecision) -> None:
        self.action = action
        self.decision = decision
        super().__init__(f"{action}: {decision.message}")


class ResumeSecurityService:
    def __init__(self) -> None:
        config = getattr(settings, "RESUME_INGESTION", {})
        self.min_text_characters = int(config.get("MIN_TRUSTED_TEXT_CHARACTERS", 80))
        self.min_word_count = int(config.get("MIN_TRUSTED_WORDS", 12))

    def evaluate(self, *, resume: Resume) -> ResumeTrustDecision:
        diagnostics = dict(resume.extraction_diagnostics or {})
        original_diagnostics = dict(diagnostics)
        normalized_status = self.normalize_status(resume.parse_status)
        text = (resume.extracted_text or "").strip()
        character_count = int(
            diagnostics.get("normalized_character_count")
            or diagnostics.get("character_count")
            or len(text)
        )
        word_count = int(
            diagnostics.get("word_count")
            or len(re.findall(r"\b\w+\b", text))
        )

        diagnostics.setdefault("normalized_character_count", character_count)
        diagnostics.setdefault("word_count", word_count)
        diagnostics.setdefault("normalized_parse_status", normalized_status)
        diagnostics.setdefault("is_trusted_ingestion", False)

        # Estados que consideramos legítimos o suficiente para processamento (Trusted)
        # 1. COMPLETED: Fluxo normal
        # 2. INSUFFICIENT_RESUME_SIGNALS: Currículo legítimo mas fraco/curto
        # 3. BLOCKED_FOR_LOW_RESUME_CONFIDENCE: Baixa confiança, mas não bloqueio duro
        # 4. INSUFFICIENT_TEXT: Permitimos passar se tiver o mínimo de sinais de currículo (opcional, mas vamos manter o foco nos 3 acima)
        trusted_statuses = {
            ResumeParseStatus.COMPLETED,
            ResumeParseStatus.INSUFFICIENT_RESUME_SIGNALS,
            ResumeParseStatus.BLOCKED_FOR_LOW_RESUME_CONFIDENCE,
        }

        if normalized_status in trusted_statuses:
            # Se for COMPLETED, ainda validamos o mínimo de texto para evitar lixo
            if normalized_status == ResumeParseStatus.COMPLETED:
                if (
                    self._has_quality_diagnostics(original_diagnostics)
                    and (
                        character_count < self.min_text_characters
                        or word_count < self.min_word_count
                    )
                ):
                    diagnostics.update(
                        {
                            "normalized_parse_status": ResumeParseStatus.INSUFFICIENT_TEXT,
                            "is_trusted_ingestion": False,
                            "minimum_trusted_characters": self.min_text_characters,
                            "minimum_trusted_words": self.min_word_count,
                        }
                    )
                    return ResumeTrustDecision(
                        trusted=False,
                        normalized_status=ResumeParseStatus.INSUFFICIENT_TEXT,
                        message=STATUS_MESSAGES[ResumeParseStatus.INSUFFICIENT_TEXT],
                        diagnostics=diagnostics,
                    )

            # Para INSUFFICIENT_RESUME_SIGNALS e BLOCKED_FOR_LOW_RESUME_CONFIDENCE, 
            # permitimos passar como trusted para degradar graciosamente em vez de bloquear.
            diagnostics["is_trusted_ingestion"] = True
            return ResumeTrustDecision(
                trusted=True,
                normalized_status=normalized_status,
                message=STATUS_MESSAGES.get(normalized_status, "Resume ingestion completed."),
                diagnostics=diagnostics,
            )

        message = str(
            diagnostics.get("user_message")
            or diagnostics.get("suggestion")
            or STATUS_MESSAGES.get(normalized_status)
            or "Resume ingestion is not in a trusted state."
        )
        return ResumeTrustDecision(
            trusted=False,
            normalized_status=normalized_status,
            message=message,
            diagnostics=diagnostics,
        )

    def assert_trusted(self, *, resume: Resume, action: str) -> ResumeTrustDecision:
        decision = self.evaluate(resume=resume)
        if not decision.trusted:
            raise ResumeTrustError(action=action, decision=decision)
        return decision

    def normalize_status(self, status_value: str | None) -> str:
        if not status_value:
            return ResumeParseStatus.PENDING
        return LEGACY_STATUS_ALIASES.get(status_value, status_value)

    def _has_quality_diagnostics(self, diagnostics: dict[str, object]) -> bool:
        quality_keys = {
            "normalized_character_count",
            "character_count",
            "word_count",
            "minimum_trusted_characters",
            "minimum_trusted_words",
            "parser_used",
            "content_kind",
        }
        return any(key in diagnostics for key in quality_keys)
