from __future__ import annotations

from bs4 import BeautifulSoup

from hunter.models.dto import JobResult

from .base import (
    BaseJobProvider,
    ProviderBlockedError,
    ProviderInvalidResponseError,
    ProviderParseError,
)


class RemoteOKProvider(BaseJobProvider):
    name = "remoteok"
    base_url = "https://remoteok.com"
    api_url = "https://remoteok.com/api"

    def fetch_jobs(
        self,
        *,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> list[JobResult]:
        response = self._request(
            self.api_url,
            headers={
                "Accept": "application/json,text/plain;q=0.9,text/html;q=0.8,*/*;q=0.7",
                "Referer": self.base_url,
                "Origin": self.base_url,
            },
        )
        payload = self._parse_payload(response)
        query_tokens = self._tokens(query)
        location_tokens = self._tokens(location)

        results: list[JobResult] = []
        for item in payload:
            if not isinstance(item, dict) or "position" not in item:
                continue

            searchable = " ".join(
                [
                    str(item.get("position") or ""),
                    str(item.get("company") or ""),
                    " ".join(item.get("tags") or []),
                    str(item.get("description") or ""),
                ]
            ).lower()
            candidate_location = str(item.get("location") or "Remote")

            if query_tokens and not all(token in searchable for token in query_tokens):
                continue
            if location_tokens and not all(
                token in candidate_location.lower() for token in location_tokens
            ):
                continue

            results.append(
                JobResult.create(
                    title=str(item.get("position") or ""),
                    company=str(item.get("company") or ""),
                    location=candidate_location or "Remote",
                    description=str(item.get("description") or ""),
                    link=str(item.get("url") or ""),
                    source=self.name,
                )
            )
        return results

    def _tokens(self, value: str) -> list[str]:
        return [token for token in value.lower().split() if token]

    def _parse_payload(self, response) -> list[dict]:
        content_type = self._get_content_type(response)
        if "json" in content_type:
            payload = self._ensure_json_response(response)
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                for key in ("jobs", "data", "results"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return value
                raise ProviderInvalidResponseError(
                    f"{self.name} JSON payload does not contain a jobs list"
                )
            raise ProviderInvalidResponseError(
                f"{self.name} returned an unsupported JSON payload"
            )

        body = response.text.strip()
        if not body:
            raise ProviderInvalidResponseError(f"{self.name} returned an empty body")

        if any(marker in body.lower() for marker in ("access denied", "captcha", "cloudflare")):
            raise ProviderBlockedError(f"{self.name} returned a blocked HTML page")

        try:
            return self._parse_html_fallback(body)
        except ProviderParseError as exc:
            raise ProviderInvalidResponseError(
                f"{self.name} returned non-JSON content that did not contain fallback job data"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderInvalidResponseError(
                f"{self.name} returned non-JSON content that could not be parsed"
            ) from exc

    def _parse_html_fallback(self, body: str) -> list[dict]:
        soup = BeautifulSoup(body, "html.parser")
        script = soup.find("script", type="application/ld+json")
        if script is None:
            raise ProviderParseError(f"{self.name} HTML fallback did not contain job data")

        try:
            import json

            payload = json.loads(script.get_text())
        except ValueError as exc:
            raise ProviderParseError(f"{self.name} HTML fallback contained invalid JSON") from exc

        if isinstance(payload, dict):
            items = payload.get("itemListElement", [])
            results: list[dict] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                job = item.get("item") or {}
                if isinstance(job, dict):
                    results.append(
                        {
                            "position": job.get("title") or "",
                            "company": ((job.get("hiringOrganization") or {}).get("name") or ""),
                            "location": (
                                ((job.get("jobLocation") or {}).get("address") or {}).get("addressLocality")
                                or "Remote"
                            ),
                            "description": job.get("description") or "",
                            "url": job.get("url") or "",
                            "tags": [],
                        }
                    )
            if results:
                return results

        raise ProviderParseError(f"{self.name} HTML fallback did not yield job entries")
