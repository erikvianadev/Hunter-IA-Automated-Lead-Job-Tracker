from __future__ import annotations

from hunter.services.job_aggregation_service import AggregationResult
from hunter.services.job_persistence_service import PersistenceResult


FAILURE_PRESENTATIONS = {
    "blocked": "Fonte temporariamente bloqueada",
    "invalid_response": "Resposta fora do formato esperado",
    "unavailable": "Fonte indisponivel",
    "parse_error": "Resposta instavel",
    "unknown": "Falha temporaria",
}


STATUS_PRESENTATIONS = {
    "success": {
        "label": "Coleta concluida",
        "tone": "good",
    },
    "partial_success": {
        "label": "Coleta parcial",
        "tone": "warning",
    },
    "total_failure": {
        "label": "Coleta indisponivel",
        "tone": "blocked",
    },
}


def _derive_search_state(aggregation: AggregationResult) -> str:
    """Granular search state for frontend traceability beyond the 3-value status."""
    if aggregation.status == "total_failure":
        return "total_failure"
    if aggregation.providers_budget_exhausted and not aggregation.providers_succeeded:
        return "budget_exhausted_all"
    if aggregation.providers_budget_exhausted:
        return "partial_budget_exhausted"
    if aggregation.status == "partial_success":
        return "partial_success"
    if aggregation.scraped == 0 and aggregation.raw_scraped > 0:
        return "quality_filtered_all"
    if aggregation.raw_scraped == 0 and aggregation.status == "success":
        return "no_results"
    return "success"


def build_scrape_summary(
    *,
    aggregation: AggregationResult,
    persistence: PersistenceResult,
) -> dict[str, object]:
    return {
        "status": aggregation.status,
        "search_state": _derive_search_state(aggregation),
        "status_label": STATUS_PRESENTATIONS.get(
            aggregation.status,
            {"label": "Coleta atualizada", "tone": "info"},
        )["label"],
        "status_tone": STATUS_PRESENTATIONS.get(
            aggregation.status,
            {"label": "Coleta atualizada", "tone": "info"},
        )["tone"],
        "message": _build_user_message(aggregation=aggregation, persistence=persistence),
        "providers_run": aggregation.providers_run,
        "providers_succeeded": aggregation.providers_succeeded,
        "providers_failed": aggregation.providers_failed,
        "providers_blocked": aggregation.providers_blocked,
        "providers_invalid_response": aggregation.providers_invalid_response,
        "providers_unavailable": aggregation.providers_unavailable,
        "providers_parse_error": aggregation.providers_parse_error,
        "provider_failure_counts": aggregation.provider_failure_counts,
        "provider_status_summary": {
            "total": len(aggregation.providers_run),
            "succeeded": len(aggregation.providers_succeeded),
            "failed": len(aggregation.providers_failed),
            "blocked": len(aggregation.providers_blocked),
            "invalid_payload": len(aggregation.providers_invalid_response),
            "unavailable": len(aggregation.providers_unavailable),
        },
        "provider_health": _build_provider_health(aggregation),
        "provider_job_counts": aggregation.provider_job_counts,
        "raw_scraped": aggregation.raw_scraped,
        "scraped": aggregation.scraped,
        "saved": persistence.saved,
        "created": persistence.created,
        "updated": persistence.updated,
        "unchanged": persistence.unchanged,
        "persistence_skipped": persistence.skipped,
        "duplicates_removed": aggregation.duplicates_removed,
        "quality_filtered": aggregation.quality_filtered,
        "quality_issue_counts": aggregation.quality_issue_counts,
    }


def _build_provider_health(aggregation: AggregationResult) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for result in aggregation.provider_results:
        failure_type = result.failure_type or ""
        results.append(
            {
                "provider": result.provider,
                "jobs_found": result.count,
                "status": "available" if result.success else failure_type or "unknown",
                "label": "Disponivel" if result.success else FAILURE_PRESENTATIONS.get(failure_type, FAILURE_PRESENTATIONS["unknown"]),
                "tone": "good" if result.success else _failure_tone(failure_type),
            }
        )
    return results


def _failure_tone(failure_type: str) -> str:
    if failure_type == "blocked":
        return "blocked"
    return "warning"


def _build_user_message(
    *,
    aggregation: AggregationResult,
    persistence: PersistenceResult,
) -> str:
    if aggregation.status == "total_failure":
        return (
            "Nao conseguimos consultar as fontes de vagas agora. "
            "Sua lista atual foi preservada; tente novamente em instantes."
        )

    if aggregation.raw_scraped == 0:
        if aggregation.providers_failed and not aggregation.providers_succeeded:
            return (
                "A busca terminou com todas as fontes instaveis desta vez. "
                "Tente novamente em alguns minutos ou use um termo mais amplo, como 'Software Engineer' ou 'Data Analyst'."
            )
        if aggregation.providers_failed:
            return (
                "A busca terminou com algumas fontes instaveis e sem vagas aproveitaveis desta vez. "
                "Sugestoes: tente 'Software Engineer', 'Backend Developer' ou remova a restricao de local."
            )
        return (
            "A busca terminou sem vagas aproveitaveis para este criterio. "
            "Sugestoes: use um cargo mais generico como 'Backend Engineer' ou 'Data Scientist', "
            "ou remova o filtro de local para ampliar a cobertura."
        )

    if aggregation.scraped == 0:
        return (
            "Encontramos vagas nas fontes, mas todas foram filtradas por qualidade insuficiente. "
            "Tente um cargo mais amplo como 'Software Engineer' ou remova restricoes de local."
        )

    saved_phrase = f"{persistence.saved} foram salvas ou atualizadas"
    if persistence.skipped:
        saved_phrase = f"{saved_phrase}; {persistence.skipped} itens inconsistentes foram ignorados"

    if aggregation.status == "partial_success":
        return (
            f"Busca concluida com instabilidade em algumas fontes. "
            f"Mantivemos {aggregation.scraped} vagas aproveitaveis e {saved_phrase}."
        )

    return f"Busca concluida. Mantivemos {aggregation.scraped} vagas aproveitaveis e {saved_phrase}."
