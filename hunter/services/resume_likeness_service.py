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
        "analista de dados",
        "developer",
        "desenvolvedor",
        "desenvolvedora",
        "engineer",
        "engenheiro",
        "engenheira",
        "engenheiro de dados",
        "manager",
        "gerente",
        "gerente de produto",
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
        "data analyst",
        "data engineer",
        "data scientist",
        "cientista de dados",
        "product",
        "marketing",
        "financeiro",
        "operations analyst",
        "analista de operacoes",
        "analista operacional",
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
        "data analytics",
        "data engineering",
        "data science",
        "analise de dados",
        "engenharia de dados",
        "scrum",
        "agile",
        "kanban",
        "figma",
        "analytics",
        "machine learning",
        "pandas",
        "numpy",
        "estudante",
        "aluno",
        "student",
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
            "programacao para ia",
            "algoritmo",
            "portugol",
            "variaveis",
            "aula",
        ),
        "legal": (
            "lei no",
            "decreto",
            "processo judicial",
            "advogado constituido",
            "testemunhas",
        ),
        "identity_or_declaration": (
            "autodeclaracao",
            "autodeclaracao de raca",
            "cpf",
            "rg",
            "assinatura aprovada",
            "signatario",
            "signatarios",
            "certificado emitente",
            "servico de validacao",
            "validar iti",
            "relatorio de conformidade",
        ),
        "template_placeholder": (
            "really great site",
            "123 anywhere",
            "any city",
            "phone 123 456 7890",
        ),
    }
    CAREER_SECTION_KEYS = {
        "profile",
        "experience",
        "education",
        "skills",
        "projects",
        "certifications",
    }

    def __init__(self) -> None:
        config = getattr(settings, "RESUME_INGESTION", {})
        # Aumentamos o threshold de COMPLETED para 0.45 para separar currículos fracos
        self.min_confidence = float(config.get("MIN_RESUME_LIKENESS_CONFIDENCE", 0.45))

    def evaluate(self, *, text: str) -> ResumeLikenessResult:
        normalized_text = self._normalize(text)
        search_texts = self._build_search_texts(normalized_text)
        words = re.findall(r"\b[\w+#.]+\b", normalized_text)
        meaningful_lines = [
            line.strip()
            for line in normalized_text.splitlines()
            if len(line.strip()) >= 3
        ]
        section_hits = self._collect_section_hits(search_texts)
        role_hits = self._collect_keyword_hits(search_texts, self.ROLE_KEYWORDS)
        skill_hits = self._collect_keyword_hits(search_texts, self.SKILL_KEYWORDS)
        experience_hits = self._collect_keyword_hits(search_texts, self.EXPERIENCE_VERBS)
        unrelated_hits = self._collect_unrelated_hits(search_texts)
        contact_signals = self._detect_contact_signals(search_texts)
        has_name_like_opening = self._has_name_like_opening(text)

        section_count = len(section_hits)
        career_section_hits = section_hits & self.CAREER_SECTION_KEYS
        has_professional_signal = bool(
            career_section_hits
            or role_hits
            or skill_hits
            or experience_hits
        )
        resume_signal_group_count = sum(
            1
            for has_signal in (
                bool(career_section_hits),
                bool(role_hits),
                bool(skill_hits),
                bool(experience_hits),
                "email" in contact_signals,
                has_name_like_opening,
            )
            if has_signal
        )
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
            career_section_count=len(career_section_hits),
            unrelated_hits=unrelated_hits,
            experience_hits=experience_hits,
            role_hits=role_hits,
            skill_hits=skill_hits,
            has_email="email" in contact_signals,
        )
        
        # A propria deteccao de documento alheio ja considera sinais fortes de
        # curriculo, entao nao suavizamos o bloqueio por sinais acidentais.
        blocked_by_unrelated_document = strong_unrelated_document
        
        is_resume_like = (
            confidence >= self.min_confidence
            and has_professional_signal
            and not blocked_by_unrelated_document
        )
        
        # Curriculos fracos precisam ter ao menos um sinal profissional real;
        # nome e quantidade de linhas sozinhos tambem aparecem em documentos arbitrarios.
        is_weak_resume = (
            not is_resume_like
            and confidence >= 0.15
            and has_professional_signal
            and not blocked_by_unrelated_document
        )

        status = self._choose_status(
            is_resume_like=is_resume_like,
            is_weak_resume=is_weak_resume,
            confidence=confidence,
            strong_unrelated_document=blocked_by_unrelated_document,
            has_professional_signal=has_professional_signal,
        )
        
        diagnostics = {
            "resume_likeness_validated": True,
            "resume_likeness_confidence": round(confidence, 3),
            "minimum_resume_likeness_confidence": self.min_confidence,
            "resume_likeness_status": status,
            "resume_likeness_signals": {
                "sections": sorted(section_hits),
                "career_sections": sorted(career_section_hits),
                "roles": role_hits[:8],
                "skills": skill_hits[:12],
                "experience_terms": experience_hits[:8],
                "contact": sorted(contact_signals),
                "name_like_opening": has_name_like_opening,
                "has_professional_signal": has_professional_signal,
                "resume_signal_group_count": resume_signal_group_count,
                "character_spaced_text_detected": len(search_texts) > 1,
                "meaningful_line_count": len(meaningful_lines),
                "word_count": len(words),
                "blocked_by_unrelated_document": blocked_by_unrelated_document,
            },
            "resume_likeness_unrelated_signals": unrelated_hits,
        }
        
        if not (is_resume_like or is_weak_resume):
            diagnostics.update(
                {
                    "failure_reason": status,
                    "blocked_by_resume_likeness_gate": True,
                    "blocked_for_low_resume_confidence": (
                        status == ResumeParseStatus.BLOCKED_FOR_LOW_RESUME_CONFIDENCE
                    ),
                    "user_message": RESUME_LIKENESS_USER_MESSAGE,
                    "suggestion": (
                        "Envie um CV real em PDF ou DOCX, com secoes claras de "
                        "experiencia, formacao, habilidades, projetos ou dados de contato profissional."
                    ),
                }
            )
            
        return ResumeLikenessResult(
            is_resume_like=is_resume_like or is_weak_resume,
            status=status,
            confidence=round(confidence, 3),
            diagnostics=diagnostics,
        )

    def _collect_section_hits(self, search_texts: tuple[str, ...]) -> set[str]:
        hits: set[str] = set()
        for section, keywords in self.SECTION_KEYWORDS.items():
            if any(self._contains_phrase(search_texts, keyword) for keyword in keywords):
                hits.add(section)
        return hits

    def _collect_keyword_hits(self, search_texts: tuple[str, ...], keywords: tuple[str, ...]) -> list[str]:
        return [
            keyword
            for keyword in keywords
            if self._contains_phrase(search_texts, keyword)
        ]

    def _collect_unrelated_hits(self, search_texts: tuple[str, ...]) -> dict[str, list[str]]:
        hits: dict[str, list[str]] = {}
        for category, patterns in self.UNRELATED_PATTERNS.items():
            matches = [
                pattern
                for pattern in patterns
                if self._contains_phrase(search_texts, pattern)
            ]
            if matches:
                hits[category] = matches
        return hits

    def _detect_contact_signals(self, search_texts: tuple[str, ...]) -> set[str]:
        signals: set[str] = set()
        has_email = any(
            re.search(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", text)
            for text in search_texts
        )
        if has_email:
            signals.add("email")
        if self._has_phone_signal(search_texts=search_texts, has_email=has_email):
            signals.add("phone")
        return signals

    def _has_phone_signal(self, *, search_texts: tuple[str, ...], has_email: bool) -> bool:
        text = search_texts[0]
        has_phone_context = bool(
            re.search(r"\b(?:telefone|celular|whatsapp|phone|mobile|contato)\b", text)
        )
        if not (has_phone_context or has_email):
            return False
        phone_pattern = r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?\d{4,5}[\s.-]?\d{4}"
        return any(re.search(phone_pattern, value) for value in search_texts)

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
        career_section_count: int,
        unrelated_hits: dict[str, list[str]],
        experience_hits: list[str],
        role_hits: list[str],
        skill_hits: list[str],
        has_email: bool,
    ) -> bool:
        if "template_placeholder" in unrelated_hits:
            return True
        unrelated_count = sum(len(values) for values in unrelated_hits.values())
        if unrelated_count < 2:
            return False
        resume_core_signal_count = sum(
            1
            for has_signal in (
                career_section_count >= 2,
                bool(role_hits),
                bool(skill_hits),
                bool(experience_hits),
                has_email,
            )
            if has_signal
        )
        if resume_core_signal_count >= 2:
            return False
        return True

    def _choose_status(
        self,
        *,
        is_resume_like: bool,
        is_weak_resume: bool,
        confidence: float,
        strong_unrelated_document: bool,
        has_professional_signal: bool,
    ) -> str:
        if is_resume_like:
            return ResumeParseStatus.COMPLETED
        if is_weak_resume:
            return ResumeParseStatus.INSUFFICIENT_RESUME_SIGNALS
        if strong_unrelated_document:
            return ResumeParseStatus.DOCUMENT_NOT_RESUME_LIKE
        if not has_professional_signal:
            return ResumeParseStatus.DOCUMENT_NOT_RESUME_LIKE
        
        # Se chegou aqui, não é nem resume_like nem weak_resume.
        # Se a confiança for mínima mas não zero, classificamos como bloqueio por baixa confiança.
        if confidence >= 0.05:
            return ResumeParseStatus.BLOCKED_FOR_LOW_RESUME_CONFIDENCE
            
        return ResumeParseStatus.DOCUMENT_NOT_RESUME_LIKE

    def _contains_phrase(self, search_texts: tuple[str, ...], phrase: str) -> bool:
        normalized_phrase = self._normalize(phrase)
        for index, text in enumerate(search_texts):
            if index == 0:
                if " " in normalized_phrase:
                    if normalized_phrase in text:
                        return True
                elif re.search(rf"\b{re.escape(normalized_phrase)}\b", text):
                    return True
                continue

            compacted_phrase = self._compact_for_search(normalized_phrase)
            if len(compacted_phrase) >= 4 and compacted_phrase in text:
                return True
        return False

    def _build_search_texts(self, normalized_text: str) -> tuple[str, ...]:
        compacted = self._compact_character_spaced_lines(normalized_text)
        if compacted == normalized_text:
            return (normalized_text,)
        return (normalized_text, self._compact_for_search(compacted))

    def _compact_character_spaced_lines(self, text: str) -> str:
        lines: list[str] = []
        changed = False
        for line in text.splitlines():
            if self._is_character_spaced_line(line):
                lines.append(re.sub(r"(?<=\S)\s+(?=\S)", "", line))
                changed = True
            else:
                lines.append(line)
        return "\n".join(lines) if changed else text

    def _is_character_spaced_line(self, line: str) -> bool:
        tokens = line.split()
        if len(tokens) < 4:
            return False
        single_character_tokens = sum(1 for token in tokens if len(token) == 1)
        return single_character_tokens / len(tokens) >= 0.65

    def _compact_for_search(self, value: str) -> str:
        return re.sub(r"[^a-z0-9+#@./-]+", "", value)

    def _normalize(self, value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value or "")
        ascii_text = "".join(
            char for char in decomposed if not unicodedata.combining(char)
        )
        ascii_text = ascii_text.lower().replace("\r\n", "\n").replace("\r", "\n")
        ascii_text = re.sub(r"[^\S\n]+", " ", ascii_text)
        return ascii_text.strip()
