from __future__ import annotations

from django.conf import settings

from .adzuna import AdzunaProvider
from .ashby import AshbyProvider
from .base import BaseJobProvider, ProviderConfig
from .greenhouse import GreenhouseProvider
from .indeed import IndeedProvider
from .lever import LeverProvider
from .remotive import RemotiveProvider
from .remoteok import RemoteOKProvider
from .weworkremotely import WeWorkRemotelyProvider


PROVIDER_CLASSES: dict[str, type[BaseJobProvider]] = {
    "remotive": RemotiveProvider,
    "greenhouse": GreenhouseProvider,
    "lever": LeverProvider,
    "ashby": AshbyProvider,
    "adzuna": AdzunaProvider,
    "remoteok": RemoteOKProvider,
    "weworkremotely": WeWorkRemotelyProvider,
    "indeed": IndeedProvider,
}


def get_job_aggregation_settings() -> dict:
    return getattr(settings, "JOB_AGGREGATION", {})


def build_provider_config(provider_name: str) -> ProviderConfig:
    config = get_job_aggregation_settings()
    provider_settings = config.get("PROVIDERS", {}).get(provider_name, {})
    defaults = config.get("DEFAULTS", {})
    common_keys = {
        "TIMEOUT",
        "MAX_PAGES",
        "MIN_DELAY",
        "MAX_DELAY",
        "MAX_RETRIES",
        "ENABLED",
        "TRUST_ENV",
    }

    return ProviderConfig(
        timeout=min(int(provider_settings.get("TIMEOUT", defaults.get("TIMEOUT", 10))), 10),
        max_pages=max(1, int(provider_settings.get("MAX_PAGES", defaults.get("MAX_PAGES", 1)))),
        min_delay=float(provider_settings.get("MIN_DELAY", defaults.get("MIN_DELAY", 0.0))),
        max_delay=float(provider_settings.get("MAX_DELAY", defaults.get("MAX_DELAY", 0.0))),
        max_retries=max(1, int(provider_settings.get("MAX_RETRIES", defaults.get("MAX_RETRIES", 2)))),
        enabled=bool(provider_settings.get("ENABLED", True)),
        trust_env=bool(provider_settings.get("TRUST_ENV", defaults.get("TRUST_ENV", False))),
        options={
            key.lower(): value
            for key, value in provider_settings.items()
            if key not in common_keys
        },
    )


def get_configured_provider_names() -> list[str]:
    config = get_job_aggregation_settings()
    provider_names = config.get(
        "PROVIDER_ORDER",
        config.get(
            "ENABLED_PROVIDERS",
            ["remotive", "greenhouse", "lever", "ashby", "remoteok", "weworkremotely", "indeed"],
        ),
    )
    return [name for name in provider_names if name in PROVIDER_CLASSES]


def get_unknown_provider_names(provider_names: list[str]) -> list[str]:
    return [name for name in provider_names if name not in PROVIDER_CLASSES]


def build_enabled_providers(
    provider_names: list[str] | None = None,
) -> list[BaseJobProvider]:
    providers: list[BaseJobProvider] = []
    selected_provider_names = provider_names or get_configured_provider_names()
    for name in selected_provider_names:
        if name not in PROVIDER_CLASSES:
            continue
        provider_class = PROVIDER_CLASSES[name]
        provider_config = build_provider_config(name)
        if not provider_config.enabled:
            continue
        providers.append(provider_class(config=provider_config))
    return providers
