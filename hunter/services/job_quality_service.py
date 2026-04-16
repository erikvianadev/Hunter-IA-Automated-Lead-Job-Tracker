from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from hunter.models.dto import JobResult

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")
_WEAK_VALUES = {
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "untitled",
    "sem empresa",
    "empresa nao informada",
    "local nao informado",
}


@dataclass(slots=True)
class JobQualityResult:
    jobs: list[JobResult] = field(default_factory=list)
    rejected: int = 0
    issue_counts: dict[str, int] = field(default_factory=dict)


class JobQualityService:
    """
    Keeps obviously weak external payloads out of the visible product surface.
    """

    def prepare(self, jobs: list[JobResult]) -> JobQualityResult:
        accepted: list[JobResult] = []
        issue_counts: dict[str, int] = {}

        for job in jobs:
            normalized, issues = self._normalize_job(job)
            if issues:
                for issue in issues:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1
                continue
            accepted.append(normalized)

        rejected = len(jobs) - len(accepted)
        logger.info(
            "job_quality_completed input_jobs=%d accepted_jobs=%d rejected_jobs=%d issue_counts=%s",
            len(jobs),
            len(accepted),
            rejected,
            issue_counts,
        )
        return JobQualityResult(jobs=accepted, rejected=rejected, issue_counts=issue_counts)

    def _normalize_job(self, job: JobResult) -> tuple[JobResult, list[str]]:
        issues: list[str] = []
        if not isinstance(job, JobResult):
            return JobResult.create(), ["invalid_payload"]

        normalized = JobResult.create(
            title=self._clean_text(job.title),
            company=self._clean_text(job.company),
            location=self._clean_text(job.location) or "Remote",
            description=self._clean_description(job.description),
            link=job.canonical_url(),
            source=self._clean_source(job.source),
        )

        if self._is_weak_text(normalized.title, min_length=3):
            issues.append("missing_title")
        if self._is_weak_text(normalized.company, min_length=2):
            issues.append("missing_company")
        if self._is_weak_text(normalized.location, min_length=2):
            issues.append("missing_location")
        if self._is_weak_text(normalized.source, min_length=2):
            issues.append("missing_source")
        if not self._is_actionable_url(normalized.link):
            issues.append("missing_actionable_link")

        return normalized, issues

    def _clean_text(self, value: object) -> str:
        text = "" if value is None else str(value)
        if "<" in text and ">" in text:
            text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        return _WHITESPACE_RE.sub(" ", unescape(text)).strip()

    def _clean_description(self, value: object) -> str:
        description = self._clean_text(value)
        return description[:5000].rstrip()

    def _clean_source(self, value: object) -> str:
        return self._clean_text(value).lower()

    def _is_weak_text(self, value: str, *, min_length: int) -> bool:
        normalized = value.strip().lower()
        return len(normalized) < min_length or normalized in _WEAK_VALUES

    def _is_actionable_url(self, value: str) -> bool:
        parts = urlsplit(value or "")
        return parts.scheme in {"http", "https"} and bool(parts.netloc)
