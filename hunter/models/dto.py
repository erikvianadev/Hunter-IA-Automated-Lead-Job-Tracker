from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_QUERY_PREFIXES = ("utm_",)
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
}


def canonicalize_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    parts = urlsplit(raw)
    query_items = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if not _is_tracking_query_key(key)
    )
    normalized_path = parts.path.rstrip("/") or parts.path
    normalized_netloc = parts.netloc.lower()
    if normalized_netloc.startswith("www."):
        normalized_netloc = normalized_netloc[4:]

    return urlunsplit(
        (
            parts.scheme.lower(),
            normalized_netloc,
            normalized_path,
            urlencode(query_items),
            "",
        )
    )


def _is_tracking_query_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in _TRACKING_QUERY_KEYS or normalized.startswith(_TRACKING_QUERY_PREFIXES)


def normalize_key_part(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


@dataclass(slots=True)
class JobResult:
    title: str
    company: str
    location: str
    description: str
    link: str
    source: str = "unknown"

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        self.company = (self.company or "").strip()
        self.location = (self.location or "").strip()
        self.description = (self.description or "").strip()
        self.link = canonicalize_url(self.link)
        self.source = (self.source or "unknown").strip().lower()

    def is_valid(self) -> bool:
        return bool(self.title and (self.link or self.company))

    def canonical_url(self) -> str:
        return canonicalize_url(self.link)

    def deduplication_key(self) -> str:
        if self.canonical_url():
            return self.canonical_url()

        return "|".join(
            [
                normalize_key_part(self.title),
                normalize_key_part(self.company),
                normalize_key_part(self.location),
            ]
        )

    def merge(self, other: "JobResult") -> "JobResult":
        if not isinstance(other, JobResult):
            return self

        self.title = self._prefer_value(self.title, other.title)
        self.company = self._prefer_value(self.company, other.company)
        self.location = self._prefer_value(self.location, other.location)
        self.description = self._prefer_value(self.description, other.description)
        self.link = self._prefer_value(self.link, other.link)
        if self.source == "unknown" and other.source:
            self.source = other.source
        return self

    def _prefer_value(self, current: str, incoming: str) -> str:
        if not current:
            return incoming
        if not incoming:
            return current
        return incoming if len(incoming) > len(current) else current

    def __getitem__(self, key: str) -> str:
        return getattr(self, key)

    @classmethod
    def create(
        cls,
        title: str = "",
        company: str = "",
        location: str = "",
        description: str = "",
        link: str = "",
        source: str = "unknown",
    ) -> "JobResult":
        return cls(
            title=title,
            company=company,
            location=location,
            description=description,
            link=link,
            source=source,
        )
