from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.contrib.auth.models import AnonymousUser

from hunter.choices import ProductEventCategory
from hunter.models.models import ProductEvent


logger = logging.getLogger("hunter.product_events")


class ProductEventName:
    ACCOUNT_CREATED = "account_created"
    FIRST_LOGIN = "first_login"
    RESUME_UPLOADED = "resume_uploaded"
    RESUME_READY = "resume_ready"
    ANALYSIS_GENERATED = "analysis_generated"
    SENIORITY_GENERATED = "seniority_generated"
    FIRST_JOB_SEARCH = "first_job_search"
    FIRST_SAVED_JOB = "first_saved_job"
    FIRST_APPLICATION = "first_application"

    ACCOUNT_CREATION_FAILED = "account_creation_failed"
    LOGIN_FAILED = "login_failed"
    RESUME_UPLOAD_FAILED = "resume_upload_failed"
    RESUME_NOT_READY = "resume_not_ready"
    ANALYSIS_GENERATION_BLOCKED = "analysis_generation_blocked"
    SENIORITY_GENERATION_BLOCKED = "seniority_generation_blocked"

    JOB_SEARCH_FAILED = "job_search_failed"
    JOB_SEARCH_DEGRADED = "job_search_degraded"
    RESUME_UPLOAD_ERROR = "resume_upload_error"
    ANALYSIS_GENERATION_ERROR = "analysis_generation_error"
    SENIORITY_GENERATION_ERROR = "seniority_generation_error"


FUNNEL_MILESTONE_ORDER = [
    ProductEventName.ACCOUNT_CREATED,
    ProductEventName.FIRST_LOGIN,
    ProductEventName.RESUME_UPLOADED,
    ProductEventName.RESUME_READY,
    ProductEventName.ANALYSIS_GENERATED,
    ProductEventName.SENIORITY_GENERATED,
    ProductEventName.FIRST_JOB_SEARCH,
    ProductEventName.FIRST_SAVED_JOB,
    ProductEventName.FIRST_APPLICATION,
]


class ProductObservabilityService:
    MAX_METADATA_STRING_LENGTH = 200
    SENSITIVE_KEY_PARTS = {"password", "token", "secret", "authorization", "access", "refresh"}

    def record_milestone(
        self,
        *,
        owner,
        event_name: str,
        source: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[ProductEvent | None, bool]:
        if not self._is_authenticated_owner(owner):
            return None, False
        return self._record(
            owner=owner,
            event_name=event_name,
            category=ProductEventCategory.JOURNEY_MILESTONE,
            source=source,
            metadata=metadata,
            once_per_owner=True,
        )

    def record_journey_failure(
        self,
        *,
        event_name: str,
        source: str,
        owner=None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[ProductEvent | None, bool]:
        return self._record(
            owner=owner if self._is_authenticated_owner(owner) else None,
            event_name=event_name,
            category=ProductEventCategory.JOURNEY_FAILURE,
            source=source,
            metadata=metadata,
            once_per_owner=False,
        )

    def record_technical_failure(
        self,
        *,
        event_name: str,
        source: str,
        owner=None,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[ProductEvent | None, bool]:
        return self._record(
            owner=owner if self._is_authenticated_owner(owner) else None,
            event_name=event_name,
            category=ProductEventCategory.TECHNICAL_FAILURE,
            source=source,
            metadata=metadata,
            once_per_owner=False,
        )

    def _record(
        self,
        *,
        owner,
        event_name: str,
        category: ProductEventCategory,
        source: str,
        metadata: Mapping[str, Any] | None,
        once_per_owner: bool,
    ) -> tuple[ProductEvent | None, bool]:
        safe_metadata = self._clean_metadata(metadata or {})
        safe_source = (source or "")[:64]
        try:
            if once_per_owner and owner is not None:
                event, created = ProductEvent.objects.get_or_create(
                    owner=owner,
                    event_name=event_name,
                    category=category,
                    defaults={
                        "source": safe_source,
                        "metadata": safe_metadata,
                    },
                )
            else:
                event = ProductEvent.objects.create(
                    owner=owner,
                    event_name=event_name,
                    category=category,
                    source=safe_source,
                    metadata=safe_metadata,
                )
                created = True

            if created:
                logger.info(
                    "product_event category=%s event=%s user_id=%s source=%s metadata=%s",
                    category,
                    event_name,
                    getattr(owner, "id", None),
                    safe_source,
                    safe_metadata,
                )
            return event, created
        except Exception:  # noqa: BLE001
            logger.exception(
                "product_event_record_failed category=%s event=%s user_id=%s source=%s",
                category,
                event_name,
                getattr(owner, "id", None),
                safe_source,
            )
            return None, False

    def _is_authenticated_owner(self, owner) -> bool:
        if owner is None or isinstance(owner, AnonymousUser):
            return False
        return bool(getattr(owner, "is_authenticated", False))

    def _clean_metadata(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            cleaned = {}
            for key, item in value.items():
                safe_key = str(key)[:64]
                if any(part in safe_key.lower() for part in self.SENSITIVE_KEY_PARTS):
                    cleaned[safe_key] = "<redacted>"
                else:
                    cleaned[safe_key] = self._clean_metadata(item)
            return cleaned
        if isinstance(value, (list, tuple, set)):
            return [self._clean_metadata(item) for item in list(value)[:20]]
        if isinstance(value, str):
            if len(value) > self.MAX_METADATA_STRING_LENGTH:
                return f"{value[: self.MAX_METADATA_STRING_LENGTH].rstrip()}..."
            return str(value)
        if isinstance(value, (bool, int, float)) or value is None:
            return value
        return str(value)[: self.MAX_METADATA_STRING_LENGTH]
