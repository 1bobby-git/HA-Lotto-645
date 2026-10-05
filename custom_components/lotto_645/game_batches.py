"""Per-formula game counts: normalization, batch planning, and safe merging.

This module is importable without Home Assistant and contains no lottery
calculation. It only decides how many six-number games each selected formula
should produce and how durable per-batch service results are combined into one
ordered set of recommendations.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from .const import DEFAULT_GAMES_PER_FORMULA, MAX_GAMES_PER_FORMULA
from .models import Recommendation


def normalize_counts(raw: Any, known_ids: Iterable[str]) -> dict[str, int]:
    """Return the stored ``{formula_id: games}`` mapping without unusable values."""
    allowed = set(known_ids)
    if not isinstance(raw, Mapping):
        return {}
    counts: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or key not in allowed or type(value) is not int:
            continue
        if 1 <= value <= MAX_GAMES_PER_FORMULA:
            counts[key] = value
    return counts


def requested_count(counts: Mapping[str, int] | None, method_id: str) -> int:
    """Return the configured game count for one formula, defaulting to a single game."""
    value = (counts or {}).get(method_id)
    if type(value) is not int or not 1 <= value <= MAX_GAMES_PER_FORMULA:
        return DEFAULT_GAMES_PER_FORMULA
    return value


def distinct_games(rows: Iterable[Recommendation]) -> list[Recommendation]:
    """Keep the first game per distinct six-number set, preserving request order.

    A service that does not yet honour a multi-game request can repeat the same
    combination. Showing it twice would inflate the entity's game count without
    adding a different ticket.
    """
    kept: list[Recommendation] = []
    seen: set[tuple[int, ...]] = set()
    for item in rows:
        if item.numbers in seen:
            continue
        seen.add(item.numbers)
        kept.append(item)
    return kept


def next_batch(
    ids: Sequence[str],
    counts: Mapping[str, int] | None,
    collected: Mapping[str, Sequence[Recommendation]],
) -> tuple[str, ...]:
    """Return the formula set of the next still-needed generation batch.

    The first batch always covers the whole selection, so an existing
    single-game result is reused instead of regenerated. Later batches only ask
    the service for formulas whose configured count is not satisfied by what has
    already been collected, and an empty tuple means every formula has enough.
    """
    have = {method_id: len(distinct_games(rows)) for method_id, rows in collected.items()}
    return tuple(
        method_id
        for method_id in ids
        if have.get(method_id, 0) < requested_count(counts, method_id)
    )


def merge_batches(
    ids: Sequence[str],
    counts: Mapping[str, int] | None,
    collected: Mapping[str, Sequence[Recommendation]],
) -> tuple[Recommendation, ...]:
    """Return the ordered, deduplicated games of every selected formula.

    ``index`` stays a running sequence across the whole analysis while
    ``formula_game`` counts one to N inside a single formula, so existing
    consumers that assume one game per method keep a stable primary game.
    """
    rows: list[Recommendation] = []
    for method_id in ids:
        games = distinct_games(collected.get(method_id, ()))[:requested_count(counts, method_id)]
        for formula_game, item in enumerate(games, start=1):
            rows.append(
                replace(item, index=len(rows) + 1, formula_game=formula_game)
            )
    return tuple(rows)


def shortfalls(
    ids: Sequence[str],
    counts: Mapping[str, int] | None,
    rows: Iterable[Recommendation],
) -> dict[str, int]:
    """Return formulas that produced fewer distinct games than configured."""
    have = Counter(item.method_id for item in rows)
    return {
        method_id: requested_count(counts, method_id) - have[method_id]
        for method_id in ids
        if have[method_id] < requested_count(counts, method_id)
    }
