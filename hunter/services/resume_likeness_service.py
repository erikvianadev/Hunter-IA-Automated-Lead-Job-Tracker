from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from django.conf import settings

from hunter.choices import ResumeParseStatus


RESUME_LIKENESS_USER_MESSAGE = (
    "Recebemos o arquivo, mas ele nao parece um curriculo utilizavel. "
    "Envie um CV real em PDF ou DOCX, com experiencias, formacao, habilidades "
    "ou projetos profissionais claros."
)


@dataclass(slots=True)
class ResumeLikenessResult:
    is_resume_like: bool
    status: str
    confidence: float
    diagnostics: dict[str, object]


class ResumeLikenessService:
    SECTION_KEYWORDS = {
        "profile": (
            "resumo",
            "perfil",
            "objetivo",
            "sobre mim",
            "summary",
            "profile",
            "objective",
        ),
        "experience": (
            "experiencia",
            "experiencias",
            "experiencia profissional",
            "historico profissional",
            "professional experience",
            "work experience",
            "employment",
            "carreira",
            "atuacao",
        ),
        "education": (
            "formacao",
            "educacao",
            "academico",
            "academic",
            "education",
            "university",
            "universidade",
            "faculdade",
            "degree",
            "bacharel",
            "graduacao",
        ),
        "skills": (
            "habilidades",
            "competencias",
            "skills",
            "tecnologias",
            "ferramentas",
            "stack",
            "technical skills",
        ),
        "projects": (
            "projetos",
            "portfolio",
            "projects",
            "github",
        ),
        "certifications": (
            "certificacoes",
            "certificados",
            "certifications",
            "courses",
            "cursos",
        ),
        "languages": (
            "idiomas",
            "languages",
            "ingles",
            "espanhol",
            "english",
            "spanish",
        ),
        "contact": (
            "contato",
            "email",
            "telefone",
            "linkedin",
            "github",
            "contact",
            "phone",
        ),
    }
    ROLE_KEYWORDS = (
        "analyst",
        "analista",
        "developer",
        "desenvolvedor",
        "desenvolvedora",
        "engineer",
        "engenheiro",
        "engenheira",
        "manager",
        "gerente",
        "coordinator",
        "coordenador",
        "coordenadora",
        "specialist",
        "especialista",
        "designer",
        "consultant",
        "consultor",
        "consultora",
        "assistant",
        "assistente",
        "intern",
        "estagio",
        "estagiario",
        "estagiaria",
        "backend",
        "frontend",
        "fullstack",
        "data",
        "dados",
        "product",
        "produto",
        "marketing",
        "financeiro",
        "operations",
        "operacoes",
    )
    SKILL_KEYWORDS = (
        "python",
        "django",
        "flask",
        "fastapi",
        "sql",
        "excel",
        "tableau",
        "power bi",
        "javascript",
        "typescript",
        "react",
        "node",
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "api",
        "apis",
        "data",
        "dados",
        "scrum",
        "agile",
        "kanban",
        "figma",
        "analytics",
        "machine learning",
    )
    EXPERIENCE_VERBS = (
        "atuei",
        "atual",
        "desenvolvi",
        "desenvolveu",
        "implementei",
        "implementar",
        "liderou",
        "liderei",
        "responsavel",
        "construi",
        "otimizei",
        "melhorei",
        "built",
        "developed",
        "implemented",
        "improved",
        "led",
        "managed",
        "responsible",
        "delivered",
    )
    UNRELATED_PATTERNS = {
        "contract": (
            "contrato",
            "clausula",
            "contratante",
            "contratada",
            "foro",
            "partes acordam",
        ),
        "invoice": (
            "nota fiscal",
            "boleto",
            "fatura",
            "pagamento vencimento",
            "cnpj",
            "inscricao estadual",
        ),
        "policy": (
            "termos de uso",
            "politica de privacidade",
            "politica interna",
            "regulamento",
            "compliance policy",
        ),
        "academic_or_report": (
            "capitulo",
            "artigo",
            "referencias bibliograficas",
            "sumario executivo",
            "ata de reuniao",
            "relatorio financeiro",
            "manual de instrucoes",
            "edital",
        ),
        "legal": (
            "lei no",
            "decreto",
            "processo judicial",
            "advogado constituido",
            "testemunhas",
        ),
    }

    def __init__(self) -> None:
        config = getattr(settings, "RESUME_INGESTION", {})
        self.min_confidence = float(config.get("MIN_RESUME_LIKENESS_CONFIDENCE", 0.35))

    def evaluate(self, *, text: str) -> ResumeLikenessResult:
        normalized_text = self._normalize(text)
        words = re.findall(r"\b[\w+#.]+\b", normalized_text)
        meaningful_lines = [
            line.strip()
            for line in normalized_text.splitlines()
            if len(line.strip()) >= 3
        ]
        section_hits = self._collect_section_hits(normalized_text)
        role_hits = self._collect_keyword_hits(normalized_text, self.ROLE_KEYWORDS)
        skill_hits = self._collect_keyword_hits(normalized_text, self.SKILL_KEYWORDS)
        experience_hits = self._collect_keyword_hits(normalized_text, self.EXPERIENCE_VERBS)
        unrelated_hits = self._collect_unrelated_hits(normalized_text)
        contact_signals = self._detect_contact_signals(normalized_text)
        has_name_like_opening = self._has_name_like_opening(text)

        section_count = len(section_hits)
        confidence = 0.0
        if section_count >= 1:
            confidence += 0.18
        if section_count >= 2:
            confidence += 0.18
        if section_count >= 3:
            confidence += 0.09
        if role_hits:
            confidence += 0.22
        if skill_hits:
            confidence += 0.14
        if experience_hits:
            confidence += 0.12
        if contact_signals:
            confidence += 0.12
        if any(key in section_hits for key in ("education", "certifications", "languages")):
            confidence += 0.08
        if len(meaningful_lines) >= 3:
            confidence += 0.07
        if has_name_like_opening:
            confidence += 0.13

        unrelated_penalty = min(0.35, 0.08 * sum(len(values) for values in unrelated_hits.values()))
        confidence = max(0.0, min(1.0, confidence - unrelated_penalty))
        strong_unrelated_document = self._is_strong_unrelated_document(
            section_count=section_count,
            unrelated_hits=unrelated_hits,
            contact_signals=contact_signals,
            experience_hits=experience_hits,
        )
        is_resume_like = confidence >= self.min_confidence and not strong_unrelated_document
        status = self._choose_status(
            is_resume_like=is_resume_like,
            confidence=confidence,
            strong_unrelated_document=strong_unrelated_document,
        )
        diagnostics = {
            "resume_likeness_validated": True,
            "resume_likeness_confidence": round(confidence, 3),
            "minimum_resume_likeness_confidence": self.min_confidence,
            "resume_likeness_status": status,
            "resume_likeness_signals": {
                "sections": sorted(section_hits),
                "roles": role_hits[:8],
                "skills": skill_hits[:12],
                "experience_terms": experience_hits[:8],
                "contact": sorted(contact_signals),
                "name_like_opening": has_name_like_opening,
                "meaningful_line_count": len(meaningful_lines),
                "word_count": len(words),
            },
            "resume_likeness_unrelated_signals": unrelated_hits,
        }
        if not is_resume_like:
            diagnostics.update(
                {
                    "failure_reason": status,
                    "blocked_for_low_resume_confidence": True,
                    "user_message": RESUME_LIKENESS_USER_MESSAGE,
                    "suggestion": (
                        "Envie um CV real em PDF ou DOCX, com secoes claras de "
                        "experiencia, formacao, habilidades, projetos ou dados de contato profissional."
                    ),
                }
            )
        return ResumeLikenessResult(
            is_resume_like=is_resume_like,
            status=status,
            confidence=round(confidence, 3),
            diagnostics=diagnostics,
        )

    def _collect_section_hits(self, text: str) -> set[str]:
        hits: set[str] = set()
        for section, keywords in self.SECTION_KEYWORDS.items():
            if any(self._contains_phrase(text, keyword) for keyword in keywords):
                hits.add(section)
        return hits

    def _collect_keyword_hits(self, text: str, keywords: tuple[str, ...]) -> list[str]:
        return [
            keyword
            for keyword in keywords
            if self._contains_phrase(text, keyword)
        ]

    def _collect_unrelated_hits(self, text: str) -> dict[str, list[str]]:
        hits: dict[str, list[str]] = {}
        for category, patterns in self.UNRELATED_PATTERNS.items():
            matches = [
                pattern
                for pattern in patterns
                if self._contains_phrase(text, pattern)
            ]
            if matches:
                hits[category] = matches
        return hits

    def _detect_contact_signals(self, text: str) -> set[str]:
        signals: set[str] = set()
        if re.search(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", text):
            signals.add("email")
        if re.search(r"(linkedin\.com|github\.com|portfolio|curriculo lattes)", text):
            signals.add("professional_link")
        if re.search(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?\d{4,5}[\s.-]?\d{4}", text):
            signals.add("phone")
        return signals

    def _has_name_like_opening(self, original_text: str) -> bool:
        lines = [line.strip() for line in original_text.splitlines() if line.strip()]
        if not lines:
            return False
        first_line = lines[0]
        if len(first_line) > 80 or any(char.isdigit() for char in first_line):
            return False
        normalized_first_line = self._normalize(first_line)
        document_title_terms = {
            "ata",
            "boleto",
            "contrato",
            "edital",
            "fatura",
            "manual",
            "politica",
            "plano",
            "proposal",
            "regulamento",
            "relatorio",
            "report",
            "strategy",
        }
        if any(term in normalized_first_line.split() for term in document_title_terms):
            return False
        words = re.findall(r"[A-Za-zÀ-ÿ]+", first_line)
        if not 2 <= len(words) <= 5:
            return False
        return all(word.isupper() or word[:1].isupper() for word in words)

    def _is_strong_unrelated_document(
        self,
        *,
        section_count: int,
        unrelated_hits: dict[str, list[str]],
        contact_signals: set[str],
        experience_hits: list[str],
    ) -> bool:
        unrelated_count = sum(len(values) for values in unrelated_hits.values())
        if unrelated_count < 2:
            return False
        if section_count >= 2 or contact_signals or experience_hits:
            return False
        return True

    def _choose_status(
        self,
        *,
        is_resume_like: bool,
        confidence: float,
        strong_unrelated_document: bool,
    ) -> str:
        if is_resume_like:
            return ResumeParseStatus.COMPLETED
        if strong_unrelated_document:
            return ResumeParseStatus.DOCUMENT_NOT_RESUME_LIKE
        if confidence >= self.min_confidence * 0.6:
            return ResumeParseStatus.BLOCKED_FOR_LOW_RESUME_CONFIDENCE
        return ResumeParseStatus.INSUFFICIENT_RESUME_SIGNALS

    def _contains_phrase(self, text: str, phrase: str) -> bool:
        normalized_phrase = self._normalize(phrase)
        if " " in normalized_phrase:
            return normalized_phrase in text
        return bool(re.search(rf"\b{re.escape(normalized_phrase)}\b", text))

    def _normalize(self, value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value or "")
        ascii_text = "".join(
            char for char in decomposed if not unicodedata.combining(char)
        )
        ascii_text = ascii_text.lower().replace("\r\n", "\n").replace("\r", "\n")
        ascii_text = re.sub(r"[^\S\n]+", " ", ascii_text)
        return ascii_text.strip()
