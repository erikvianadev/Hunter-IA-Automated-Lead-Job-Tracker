from __future__ import annotations

import re
from urllib.parse import urlparse


class ResumeParserService:
    section_aliases = {
        "summary": "summary",
        "profile": "summary",
        "professional summary": "summary",
        "about": "summary",
        "experience": "experience",
        "work experience": "experience",
        "professional experience": "experience",
        "employment": "experience",
        "education": "education",
        "academic background": "education",
        "skills": "skills",
        "technical skills": "skills",
        "core skills": "skills",
        "projects": "projects",
        "personal projects": "projects",
        "portfolio": "projects",
        "links": "links",
        "contact": "links",
        "languages": "languages",
    }

    def parse(self, *, text: str) -> dict[str, object]:
        lines = [self._normalize_line(line) for line in text.splitlines()]
        non_empty_lines = [line for line in lines if line]
        headline = non_empty_lines[0] if non_empty_lines else ""
        sections = self._split_sections(non_empty_lines[1:] if len(non_empty_lines) > 1 else [])
        links = self._extract_links(text, sections.get("links", []))

        summary_lines = sections.get("summary", [])
        skills = self._extract_list_items(sections.get("skills", []))
        languages = self._extract_list_items(sections.get("languages", []))
        projects = sections.get("projects", [])

        return {
            "headline": headline,
            "summary": " ".join(summary_lines).strip(),
            "experience": sections.get("experience", []),
            "education": sections.get("education", []),
            "skills": skills,
            "projects": projects,
            "links": links,
            "languages": languages,
            "section_order": [name for name in sections.keys()],
            "line_count": len(non_empty_lines),
            "word_count": len(re.findall(r"\b\w+\b", text)),
        }

    def _split_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current_section = "summary"
        sections[current_section] = []

        for line in lines:
            normalized = self.section_aliases.get(line.lower().strip(":"))
            if normalized:
                current_section = normalized
                sections.setdefault(current_section, [])
                continue
            sections.setdefault(current_section, []).append(line)
        return {key: value for key, value in sections.items() if value}

    def _extract_list_items(self, lines: list[str]) -> list[str]:
        items: list[str] = []
        for line in lines:
            for part in re.split(r"[|,;/]", line):
                cleaned = part.strip(" -•\t")
                if cleaned:
                    items.append(cleaned)
        seen: list[str] = []
        for item in items:
            if item.lower() not in [existing.lower() for existing in seen]:
                seen.append(item)
        return seen

    def _extract_links(self, text: str, link_lines: list[str]) -> list[str]:
        candidates = re.findall(r"https?://[^\s,]+", text)
        candidates.extend(
            match.group(0)
            for line in link_lines
            for match in re.finditer(r"(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s,]*)?", line)
        )
        normalized: list[str] = []
        for candidate in candidates:
            value = candidate.strip().rstrip(".,)")
            if not value.startswith(("http://", "https://")):
                value = f"https://{value}"
            parsed = urlparse(value)
            if parsed.netloc and value not in normalized:
                normalized.append(value)
        return normalized

    def _normalize_line(self, line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()
