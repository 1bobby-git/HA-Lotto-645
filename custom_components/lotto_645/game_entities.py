"""Registry identity and display names for per-game formula sensors.

Kept free of Home Assistant imports so the naming rules are unit testable.
"""
from __future__ import annotations


def game_unique_id(entry_id: str, method_id: str, game_no: int = 1) -> str:
    """Game 1 keeps the pre-2.4.10 unique_id so existing entities survive."""
    suffix = '' if game_no <= 1 else f'_g{game_no}'
    return f'{entry_id}_method_{method_id}{suffix}'


def game_unique_ids(entry_id: str, method_id: str, count: int) -> set[str]:
    """Every sensor identity a configured game count must keep registered."""
    total = max(1, int(count))
    return {game_unique_id(entry_id, method_id, n) for n in range(1, total + 1)}


def game_entity_name(game_no: int, label: str, *, purchased: bool = False) -> str:
    """`N번 | 라벨` — review stars belong on the Lotto page, not in entity names."""
    prefix = f'{game_no}번 | '
    return f'{prefix}✓구매일치 | {label}' if purchased else f'{prefix}{label}'
