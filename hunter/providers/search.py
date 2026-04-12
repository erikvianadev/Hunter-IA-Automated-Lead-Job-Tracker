from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[+#]+)?")
_WHITESPACE_RE = re.compile(r"\s+")
_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "for",
    "in",
    "na",
    "no",
    "of",
    "or",
    "para",
    "the",
    "to",
    "with",
}
_REMOTE_MARKERS = {
    "anywhere",
    "distributed",
    "global",
    "home based",
    "remote",
    "remote-first",
    "remote first",
    "remota",
    "remoto",
    "work from home",
    "worldwide",
}


def normalize_text(value: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip().lower())


def tokenize(value: str | None, *, drop_stopwords: bool = False) -> list[str]:
    tokens = _TOKEN_RE.findall(normalize_text(value))
    if not drop_stopwords:
        return tokens
    return [token for token in tokens if token not in _QUERY_STOPWORDS]


def is_remote_value(value: str | None) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    return any(marker in normalized for marker in _REMOTE_MARKERS)


@dataclass(slots=True)
class SearchCriteria:
    query: str = ""
    location: str = ""
    query_tokens: list[str] = field(init=False, default_factory=list)
    location_tokens: list[str] = field(init=False, default_factory=list)
    remote_location: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self.query = normalize_text(self.query)
        self.location = normalize_text(self.location)
        self.query_tokens = tokenize(self.query, drop_stopwords=True)
        self.location_tokens = tokenize(self.location)
        self.remote_location = is_remote_value(self.location)

    def matches_query(self, searchable: str | None) -> bool:
        if not self.query_tokens:
            return True

        normalized = normalize_text(searchable)
        if not normalized:
            return False
        if self.query and self.query in normalized:
            return True

        searchable_tokens = set(tokenize(normalized, drop_stopwords=True))
        if not searchable_tokens:
            return False

        overlap = sum(1 for token in self.query_tokens if token in searchable_tokens)
        return overlap >= self._required_query_matches()

    def matches_location(
        self,
        candidate_location: str | None,
        *,
        is_remote: bool = False,
        extra_locations: list[str] | None = None,
    ) -> bool:
        if not self.location_tokens:
            return True

        searchable_chunks = [candidate_location or ""]
        if extra_locations:
            searchable_chunks.extend(extra_locations)
        searchable = normalize_text(" ".join(chunk for chunk in searchable_chunks if chunk))

        if self.remote_location:
            return is_remote or is_remote_value(searchable)

        if not searchable:
            return False
        if self.location and self.location in searchable:
            return True

        searchable_tokens = set(tokenize(searchable))
        overlap = sum(1 for token in self.location_tokens if token in searchable_tokens)
        return overlap >= self._required_location_matches()

    def _required_query_matches(self) -> int:
        token_count = len(self.query_tokens)
        if token_count <= 2:
            return token_count
        if token_count == 3:
            return 2
        return min(token_count, max(2, math.ceil(token_count * 0.6)))

    def _required_location_matches(self) -> int:
        token_count = len(self.location_tokens)
        if token_count <= 2:
            return 1
        return min(token_count, 2)
