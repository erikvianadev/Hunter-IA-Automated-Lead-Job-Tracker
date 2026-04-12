from __future__ import annotations

import logging
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from hunter.models.dto import JobResult

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
        "Gecko/20100101 Firefox/125.0"
    ),
]
_WHITESPACE_RE = re.compile(r"\s+")
_JSON_PREFIX_RE = re.compile(r"^[^{\[]*?(?=[{\[])", re.DOTALL)
_BLOCKED_BODY_MARKERS = (
    "access denied",
    "captcha",
    "cloudflare",
    "forbidden",
    "security check",
    "verify you are a human",
    "just a moment",
)

FAILURE_BLOCKED = "blocked"
FAILURE_INVALID_RESPONSE = "invalid_response"
FAILURE_UNAVAILABLE = "unavailable"
FAILURE_PARSE_ERROR = "parse_error"


def build_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra:
        headers.update(extra)
    return headers


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def sanitize_text(value: str | None) -> str:
    if not value:
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def extract_text(tag: object, default: str = "") -> str:
    if tag is None:
        return default
    text: str = getattr(tag, "get_text", lambda **_: str(tag))(separator=" ")
    return sanitize_text(text)


def absolute_url(base: str, path: str) -> str:
    raw_path = (path or "").strip()
    if not raw_path:
        return ""
    if raw_path.startswith("http"):
        return raw_path
    return urljoin(base, raw_path)


@dataclass(slots=True)
class ProviderConfig:
    timeout: int = 10
    max_pages: int = 1
    min_delay: float = 0.0
    max_delay: float = 0.0
    max_retries: int = 2
    enabled: bool = True
    trust_env: bool = False
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderRunResult:
    provider: str
    jobs: list[JobResult] = field(default_factory=list)
    success: bool = True
    blocked: bool = False
    failure_type: str = ""
    error_message: str = ""
    duration_seconds: float = 0.0

    @property
    def count(self) -> int:
        return len(self.jobs)


class ProviderError(Exception):
    """Base provider exception."""


class ProviderBlockedError(ProviderError):
    """Raised when a provider is blocked or unavailable."""


class ProviderInvalidResponseError(ProviderError):
    """Raised when a provider returns an unexpected payload."""


class ProviderUnavailableError(ProviderError):
    """Raised when a provider cannot be reached reliably."""


class ProviderParseError(ProviderError):
    """Raised when a provider response cannot be parsed safely."""


class BaseJobProvider(ABC):
    name = "base"
    base_url = ""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config or ProviderConfig()
        self.session = session or requests.Session()
        self.session.trust_env = self.config.trust_env
        self.session.headers.update(build_headers())

    def run(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int | None = None,
    ) -> ProviderRunResult:
        started = time.perf_counter()
        logger.info(
            "provider_started provider=%s query=%r location=%r",
            self.name,
            query,
            location,
        )

        try:
            jobs = self.fetch_jobs(
                query=query,
                location=location,
                max_pages=max_pages or self.config.max_pages,
            )
            duration = time.perf_counter() - started
            logger.info(
                "provider_finished provider=%s jobs=%d duration_seconds=%.3f",
                self.name,
                len(jobs),
                duration,
            )
            return ProviderRunResult(
                provider=self.name,
                jobs=jobs,
                success=True,
                duration_seconds=duration,
            )
        except ProviderBlockedError as exc:
            duration = time.perf_counter() - started
            logger.warning(
                "provider_blocked provider=%s duration_seconds=%.3f error=%s",
                self.name,
                duration,
                exc,
            )
            return ProviderRunResult(
                provider=self.name,
                success=False,
                blocked=True,
                failure_type=FAILURE_BLOCKED,
                error_message=str(exc),
                duration_seconds=duration,
            )
        except ProviderInvalidResponseError as exc:
            duration = time.perf_counter() - started
            logger.warning(
                "provider_invalid_response provider=%s duration_seconds=%.3f error=%s",
                self.name,
                duration,
                exc,
            )
            return ProviderRunResult(
                provider=self.name,
                success=False,
                failure_type=FAILURE_INVALID_RESPONSE,
                error_message=str(exc),
                duration_seconds=duration,
            )
        except ProviderUnavailableError as exc:
            duration = time.perf_counter() - started
            logger.warning(
                "provider_unavailable provider=%s duration_seconds=%.3f error=%s",
                self.name,
                duration,
                exc,
            )
            return ProviderRunResult(
                provider=self.name,
                success=False,
                failure_type=FAILURE_UNAVAILABLE,
                error_message=str(exc),
                duration_seconds=duration,
            )
        except ProviderParseError as exc:
            duration = time.perf_counter() - started
            logger.warning(
                "provider_parse_error provider=%s duration_seconds=%.3f error=%s",
                self.name,
                duration,
                exc,
            )
            return ProviderRunResult(
                provider=self.name,
                success=False,
                failure_type=FAILURE_PARSE_ERROR,
                error_message=str(exc),
                duration_seconds=duration,
            )
        except Exception as exc:  # noqa: BLE001
            duration = time.perf_counter() - started
            logger.exception(
                "provider_failed provider=%s duration_seconds=%.3f error=%s",
                self.name,
                duration,
                exc,
            )
            return ProviderRunResult(
                provider=self.name,
                success=False,
                failure_type=FAILURE_PARSE_ERROR,
                error_message=f"unexpected provider error: {exc}",
                duration_seconds=duration,
            )

    @abstractmethod
    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        """Fetch and normalize jobs from a provider."""

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "BaseJobProvider":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _cap_pages(self, requested_pages: int) -> int:
        return max(1, min(requested_pages, self.config.max_pages))

    def _get_option(self, key: str, default: Any = None) -> Any:
        return self.config.options.get(key.lower(), default)

    def _pause(self) -> None:
        if self.config.max_delay > 0:
            random_delay(self.config.min_delay, self.config.max_delay)

    def _log_response_metadata(self, response: requests.Response) -> None:
        raw_body = response.text
        body = raw_body if isinstance(raw_body, str) else str(raw_body or "")
        stripped = body.lstrip()
        body_kind = "empty"
        if stripped.startswith("<"):
            body_kind = "html"
        elif stripped.startswith("{") or stripped.startswith("["):
            body_kind = "json_like"
        elif stripped:
            body_kind = "text"
        logger.info(
            "provider_response provider=%s status=%s content_type=%s body_kind=%s body_preview=%r",
            self.name,
            response.status_code,
            response.headers.get("Content-Type", ""),
            body_kind,
            stripped[:120],
        )

    def _get_content_type(self, response: requests.Response) -> str:
        return response.headers.get("Content-Type", "").split(";")[0].strip().lower()

    def _ensure_html_response(self, response: requests.Response) -> str:
        content_type = self._get_content_type(response)
        if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
            raise ProviderInvalidResponseError(
                f"{self.name} returned non-HTML content type '{content_type}'"
            )
        body = response.text.strip()
        if not body:
            raise ProviderInvalidResponseError(f"{self.name} returned an empty HTML body")
        return body

    def _ensure_json_response(self, response: requests.Response) -> Any:
        content_type = self._get_content_type(response)
        if "json" not in content_type:
            raise ProviderInvalidResponseError(
                f"{self.name} returned non-JSON content type '{content_type or 'unknown'}'"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderInvalidResponseError(
                f"{self.name} returned invalid JSON"
            ) from exc

    def _looks_blocked(self, body: str) -> bool:
        lowered = (body or "").lower()
        return any(marker in lowered for marker in _BLOCKED_BODY_MARKERS)

    def _decode_json_text(
        self,
        body: str,
        *,
        allow_wrapped: bool = True,
    ) -> Any:
        raw_body = (body or "").strip()
        if not raw_body:
            raise ProviderInvalidResponseError(f"{self.name} returned an empty body")
        if self._looks_blocked(raw_body):
            raise ProviderBlockedError(f"{self.name} returned a blocked page")

        candidates = [raw_body]
        if allow_wrapped:
            candidates.extend(self._json_candidates(raw_body))

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except ValueError:
                continue

        raise ProviderInvalidResponseError(f"{self.name} returned invalid JSON")

    def _json_candidates(self, body: str) -> list[str]:
        candidates: list[str] = []
        stripped = body.strip()
        prefix_trimmed = _JSON_PREFIX_RE.sub("", stripped, count=1).strip()
        if prefix_trimmed and prefix_trimmed != stripped:
            candidates.append(prefix_trimmed)

        decoder = json.JSONDecoder()
        for start_char in ("{", "["):
            index = stripped.find(start_char)
            if index < 0:
                continue
            fragment = stripped[index:]
            try:
                _, end = decoder.raw_decode(fragment)
            except ValueError:
                continue
            candidates.append(fragment[:end])

        seen: set[str] = set()
        unique_candidates: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                unique_candidates.append(candidate)
        return unique_candidates

    def _request(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        blocked_statuses: tuple[int, ...] = (),
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=build_headers(headers),
                    timeout=min(self.config.timeout, 10),
                )
                self._log_response_metadata(response)
                if response.status_code in blocked_statuses:
                    raise ProviderBlockedError(
                        f"{self.name} returned HTTP {response.status_code}"
                    )
                if response.status_code in {401, 429}:
                    raise ProviderUnavailableError(
                        f"{self.name} returned HTTP {response.status_code}"
                    )
                response.raise_for_status()
                if not response.encoding:
                    response.encoding = response.apparent_encoding or "utf-8"
                return response
            except ProviderBlockedError:
                raise
            except ProviderInvalidResponseError:
                raise
            except ProviderParseError:
                raise
            except ProviderUnavailableError as exc:
                last_error = exc
                logger.warning(
                    "provider_request_unavailable provider=%s attempt=%d/%d url=%s error=%s",
                    self.name,
                    attempt,
                    self.config.max_retries,
                    url,
                    exc,
                )
                if attempt < self.config.max_retries:
                    self._pause()
            except requests.RequestException as exc:
                last_error = exc
                logger.warning(
                    "provider_request_retry provider=%s attempt=%d/%d url=%s error=%s",
                    self.name,
                    attempt,
                    self.config.max_retries,
                    url,
                    exc,
                )
                if attempt < self.config.max_retries:
                    self._pause()

        raise ProviderUnavailableError(f"{self.name} request failed: {last_error}")

    def _get_soup(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        blocked_statuses: tuple[int, ...] = (),
    ) -> BeautifulSoup:
        response = self._request(
            url,
            params=params,
            headers=headers,
            blocked_statuses=blocked_statuses,
        )
        body = self._ensure_html_response(response)
        return BeautifulSoup(body, "html.parser")

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        blocked_statuses: tuple[int, ...] = (),
    ) -> Any:
        response = self._request(
            url,
            params=params,
            headers=headers,
            blocked_statuses=blocked_statuses,
        )
        return self._ensure_json_response(response)

    def _normalize_jobs_payload(
        self,
        payload: object,
        *,
        keys: tuple[str, ...] = ("jobs", "data", "results"),
    ) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            raise ProviderInvalidResponseError(
                f"{self.name} JSON payload does not contain a jobs list"
            )
        raise ProviderInvalidResponseError(
            f"{self.name} returned an unsupported JSON payload"
        )
