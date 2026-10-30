"""Diagnostics download: operational state only.

Values are copied from an allowlist instead of redacting a full dump, so no
service token, installation credential, birth detail or ticket number can reach
the downloaded file.
"""
from __future__ import annotations

from typing import Any

from .const import (
    CONF_AI_AUTO_GENERATE,
    CONF_ALLOW_OFFICIAL_FALLBACK,
    CONF_ENABLE_AI,
    CONF_GAME_COUNTS,
    CONF_PERSONAL_CONSENT,
    CONF_SAJU_BIRTH_DATE,
    CONF_SELECTED_METHODS,
    CONF_USE_SERVICE,
    DEFAULT_AI_AUTO_GENERATE,
    DEFAULT_ALLOW_OFFICIAL_FALLBACK,
    DEFAULT_ENABLE_AI,
    DEFAULT_USE_SERVICE,
    VERSION,
)

HEALTH_KEYS = ("ok", "error", "since", "latest_round", "core_version")


def _options(options: dict[str, Any]) -> dict[str, Any]:
    counts = options.get(CONF_GAME_COUNTS)
    return {
        "selected_methods": [str(item) for item in options.get(CONF_SELECTED_METHODS) or []],
        "game_counts": (
            {str(key): value for key, value in counts.items() if isinstance(value, int)}
            if isinstance(counts, dict) else {}
        ),
        "enable_ai_recommendation": bool(options.get(CONF_ENABLE_AI, DEFAULT_ENABLE_AI)),
        "ai_auto_generate": bool(options.get(CONF_AI_AUTO_GENERATE, DEFAULT_AI_AUTO_GENERATE)),
        "allow_official_direct_fallback": bool(
            options.get(CONF_ALLOW_OFFICIAL_FALLBACK, DEFAULT_ALLOW_OFFICIAL_FALLBACK)
        ),
        "use_lotto_lab_service": bool(options.get(CONF_USE_SERVICE, DEFAULT_USE_SERVICE)),
        "saju_profile_saved": bool(options.get(CONF_SAJU_BIRTH_DATE)),
        "saju_remote_consent": bool(options.get(CONF_PERSONAL_CONSENT)),
    }


def build_diagnostics(entry: Any) -> dict[str, Any]:
    """Return counts, statuses and versions for one config entry."""
    result: dict[str, Any] = {"version": VERSION, "options": _options(dict(entry.options))}
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        result["loaded"] = False
        return result
    service = coordinator.service
    data = coordinator.data
    history = coordinator.history
    analysis = data.analysis if data is not None else None
    result.update({
        "loaded": True,
        "service": {
            "status": service.status,
            "connection_type": (service.connection_manager.state or {}).get("source"),
            "health": {key: service.health.get(key) for key in HEALTH_KEYS},
            "catalog_core_version": service.catalog.core_version if service.catalog else None,
        },
        "history": {
            "latest_round": history[-1].round if history else None,
            "draw_count": len(history),
            "source_status": data.source_status if data is not None else None,
        },
        "recommendations": {
            "target_round": analysis.target_round if analysis else None,
            "game_count": len(analysis.recommendations) if analysis else 0,
            "game_shortfall": dict(analysis.summary.get("game_shortfall") or {}) if analysis else {},
            "ai_status": data.ai_status if data is not None else None,
        },
        "purchases": {
            "ticket_count": len(coordinator.purchase_book.tickets),
            "storage_error": bool(coordinator.purchase_storage_error),
        },
        "reviews": {"storage_error": bool(coordinator.review_storage_error)},
    })
    return result


async def async_get_config_entry_diagnostics(hass: Any, entry: Any) -> dict[str, Any]:
    """Home Assistant diagnostics platform entry point."""
    del hass
    return build_diagnostics(entry)
