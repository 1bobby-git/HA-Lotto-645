"""Persistent score ledger for user-triggered historical validations.

This ledger is intentionally separate from the pre-draw recommendation review.
Every successfully completed historical validation counts as one validation run.
A generated formula earns weighted points only from exact main-number matches:
3=1, 4=3, 5=10, 6=50. Bonus matches never raise this validation score.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORE_VERSION = 1
CACHE_KEY = f"{DOMAIN}_historical_validation_score_ledgers"
POINTS = {3: 1, 4: 3, 5: 10, 6: 50}
MAX_RECENT = 50


def _empty() -> dict[str, Any]:
    return {"version": STORE_VERSION, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}


def _validate(payload: Any) -> dict[str, Any]:
    if payload is None:
        return _empty()
    if not isinstance(payload, dict) or payload.get("version") != STORE_VERSION:
        raise ValueError("invalid validation score ledger")
    if type(payload.get("total_runs")) is not int or payload["total_runs"] < 0:
        raise ValueError("invalid validation run count")
    if not isinstance(payload.get("methods"), dict) or not isinstance(payload.get("recent"), list):
        raise ValueError("invalid validation score ledger")
    rounds = payload.get("rounds", [])
    if not isinstance(rounds, list) or any(type(value) is not int for value in rounds):
        raise ValueError("invalid validation score rounds")
    return deepcopy(payload)


def _method_row(method_id: str, label: str) -> dict[str, Any]:
    return {
        "method_id": method_id,
        "label": label,
        "attempts": 0,
        "generated": 0,
        "unavailable": 0,
        "three_plus_hits": 0,
        "points": 0,
        "best_match": 0,
        "match_3": 0,
        "match_4": 0,
        "match_5": 0,
        "match_6": 0,
    }


def apply_result(payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Return a new ledger with exactly one completed validation appended."""
    updated = deepcopy(payload)
    target_round = result.get("target_round")
    if type(target_round) is not int:
        raise ValueError("validation result missing target round")
    rows = result.get("results")
    if not isinstance(rows, list):
        raise ValueError("validation result missing rows")

    updated["total_runs"] += 1
    rounds = set(updated.get("rounds", []))
    rounds.add(target_round)
    updated["rounds"] = sorted(rounds)
    run_methods = []

    for raw in rows:
        if not isinstance(raw, dict) or not isinstance(raw.get("method_id"), str):
            continue
        method_id = raw["method_id"]
        label = str(raw.get("sensor_name") or method_id)[:180]
        row = updated["methods"].setdefault(method_id, _method_row(method_id, label))
        row["label"] = label
        row["attempts"] += 1
        status = raw.get("generation_status")
        if status != "generated":
            row["unavailable"] += 1
            run_methods.append({"method_id": method_id, "match": None, "points": 0})
            continue
        row["generated"] += 1
        match = raw.get("main_match_count", 0)
        match = match if type(match) is int and 0 <= match <= 6 else 0
        row["best_match"] = max(row["best_match"], match)
        points = POINTS.get(match, 0)
        if match >= 3:
            row["three_plus_hits"] += 1
            row[f"match_{match}"] += 1
            row["points"] += points
        run_methods.append({"method_id": method_id, "match": match, "points": points})

    updated["recent"].append({
        "run": updated["total_runs"],
        "round": target_round,
        "generated_at": str(result.get("generated_at", ""))[:80],
        "methods": run_methods,
    })
    updated["recent"] = updated["recent"][-MAX_RECENT:]
    return updated


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    methods = []
    for raw in payload.get("methods", {}).values():
        row = deepcopy(raw)
        generated = row.get("generated", 0)
        hits = row.get("three_plus_hits", 0)
        row["hit_rate"] = round(hits * 100 / generated, 1) if generated else 0.0
        methods.append(row)
    methods.sort(key=lambda row: (-row["points"], -row["three_plus_hits"], -row["best_match"], row["label"]))
    return {
        "total_runs": payload.get("total_runs", 0),
        "unique_rounds": len(payload.get("rounds", [])),
        "point_policy": "3개=1점 · 4개=3점 · 5개=10점 · 6개=50점",
        "threshold": 3,
        "methods": methods,
        "recent": deepcopy(payload.get("recent", [])),
    }


async def async_record(hass, entry_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Atomically load, append, save and return the cumulative scoreboard."""
    cache = hass.data.setdefault(CACHE_KEY, {})
    state = cache.setdefault(entry_id, {"lock": asyncio.Lock(), "payload": None, "storage_error": False})
    async with state["lock"]:
        if state["storage_error"]:
            return {"total_runs": 0, "unique_rounds": 0, "methods": [], "recent": [], "storage_error": True}
        store = Store(hass, STORE_VERSION, f"{DOMAIN}.validation_scores.{entry_id}")
        if state["payload"] is None:
            try:
                state["payload"] = _validate(await store.async_load())
            except (ValueError, TypeError, KeyError, HomeAssistantError, OSError):
                state["storage_error"] = True
                return {"total_runs": 0, "unique_rounds": 0, "methods": [], "recent": [], "storage_error": True}
        updated = apply_result(state["payload"], result)
        try:
            await store.async_save(updated)
        except (HomeAssistantError, OSError):
            return {**summary(state["payload"]), "storage_error": True}
        state["payload"] = updated
        return summary(updated)
