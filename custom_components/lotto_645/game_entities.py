"""Registry identity and display names for per-game formula sensors.

Kept free of Home Assistant imports so the naming rules are unit testable.
"""
from __future__ import annotations

from .const import CONF_GAME_COUNTS, CONF_SELECTED_METHODS
from .game_batches import normalize_counts, requested_count


def game_unique_id(entry_id: str, method_id: str, game_no: int = 1) -> str:
    """Game 1 keeps the pre-2.4.10 unique_id so existing entities survive."""
    suffix = '' if game_no <= 1 else f'_g{game_no}'
    return f'{entry_id}_method_{method_id}{suffix}'


def game_unique_ids(entry_id: str, method_id: str, count: int) -> set[str]:
    """Every sensor identity a configured game count must keep registered."""
    total = max(1, int(count))
    return {game_unique_id(entry_id, method_id, n) for n in range(1, total + 1)}


def configured_game_unique_ids(entry_id: str, options, fallback_ids) -> set[str]:
    """Read saved selection without depending on a yet-to-load remote catalog."""
    selected = options.get(CONF_SELECTED_METHODS, fallback_ids)
    if not isinstance(selected, (list, tuple)):
        selected = fallback_ids
    ids = tuple(key for key in selected if isinstance(key, str))
    counts = normalize_counts(options.get(CONF_GAME_COUNTS), ids)
    return {unique_id for key in ids
            for unique_id in game_unique_ids(entry_id, key, requested_count(counts, key))}


def game_entity_name(game_no: int, label: str, *, purchased: bool = False) -> str:
    """Keep the formula first so HA groups its games together when sorting."""
    name = f'{label} | {game_no}번'
    return f'{name} | ✓구매일치' if purchased else name
