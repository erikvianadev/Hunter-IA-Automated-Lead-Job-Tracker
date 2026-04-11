from __future__ import annotations

import logging

from hunter.models.dto import JobResult

from .base import BaseJobProvider, ProviderBlockedError, ProviderInvalidResponseError

logger = logging.getLogger(__name__)


class RemotiveProvider(BaseJobProvider):
    name = "remotive"
    base_url = "https://remotive.com"
    api_url = "https://remotive.com/api/remote-jobs"

    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        response = self._request(
            self.api_url,
            params={
                "search": query.strip(),
                "limit": 50,
            },
            headers={
                "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
                "Referer": f"{self.base_url}/jobs",
            },
        )
        payload = self._parse_payload(response)
        jobs_payload = self._normalize_jobs_payload(payload, keys=("jobs",))

        query_tokens = self._tokens(query)
        location_tokens = self._tokens(location)
        results: list[JobResult] = []
        for item in jobs_payload:
            if not isinstance(item, dict):
                continue

            searchable = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("company_name") or ""),
                    str(item.get("category") or ""),
                    str(item.get("candidate_required_location") or ""),
                    str(item.get("description") or ""),
                ]
            ).lower()
            candidate_location = str(
                item.get("candidate_required_location")
                or item.get("location")
                or "Remote"
            ).strip()
            if query_tokens and not all(token in searchable for token in query_tokens):
                continue
            if location_tokens and not all(
                token in candidate_location.lower() for token in location_tokens
            ):
                continue

            results.append(
                JobResult.create(
                    title=str(item.get("title") or ""),
                    company=str(item.get("company_name") or ""),
                    location=candidate_location or "Remote",
                    description=str(item.get("description") or ""),
                    link=str(item.get("url") or ""),
                    source=self.name,
                )
            )
        return [job for job in results if job.is_valid()]

    def _tokens(self, value: str) -> list[str]:
        return [token for token in value.lower().split() if token]

    def _parse_payload(self, response) -> object:
        content_type = self._get_content_type(response)
        body = (response.text or "").strip()

        if not body:
            raise ProviderInvalidResponseError(f"{self.name} returned an empty body")
        if self._looks_blocked(body):
            raise ProviderBlockedError(f"{self.name} returned a blocked page")

        if "json" in content_type:
            payload = self._try_parse_json(body)
            if payload is not None:
                return payload
            raise ProviderInvalidResponseError(f"{self.name} returned invalid JSON")

        if body.startswith("<"):
            raise ProviderInvalidResponseError(
                f"{self.name} returned HTML instead of JSON"
            )

        payload = self._try_parse_json(body)
        if payload is not None:
            return payload

        logger.warning(
            "provider_json_decode_failed provider=%s content_type=%s body_preview=%r",
            self.name,
            content_type or "unknown",
            body[:120],
        )
        raise ProviderInvalidResponseError(
            f"{self.name} returned non-JSON content that could not be parsed"
        )

    def _try_parse_json(self, body: str) -> object | None:
        try:
            return self._decode_json_text(body)
        except ProviderBlockedError:
            raise
        except ProviderInvalidResponseError:
            return None
