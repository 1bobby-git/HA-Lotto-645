"""Validate photo OCR by physical A-E slot, without guessing missing digits.

The panel supplies one row per position, not overlapping OCR passes. A repeated
number combination on two purchased lines is valid and must stay two games.
Incomplete, conflicting, or unlabelled readings are review-only.
"""
from __future__ import annotations

import re

from .purchased_tickets import SLOTS, parse_ticket

_MAX_LINES = 60


def _numbers(tokens: object) -> list[int] | None:
    if not isinstance(tokens, (list, tuple)) or len(tokens) != 6:
        return None
    if any(not isinstance(t, str) or not re.fullmatch(r"[0-9]{1,2}", t) for t in tokens):
        return None
    numbers = [int(t) for t in tokens]
    if len(set(numbers)) != 6 or any(not 1 <= n <= 45 for n in numbers):
        return None
    return list(parse_ticket(numbers))


def import_from_lines(lines: object, expected_games: int | None = None) -> dict[str, object]:
    """Return a reviewable reading; never erase an unreadable or conflicting slot."""
    if not isinstance(lines, list) or len(lines) > _MAX_LINES:
        raise ValueError("no_ticket_games")
    if expected_games is not None and (type(expected_games) is not int or not 1 <= expected_games <= 5):
        raise ValueError("invalid_expected_games")
    readings: dict[str, list[int]] = {}
    unreadable: set[str] = set()
    conflicts: set[str] = set()
    unlabelled = False
    provisional: list[tuple[str | None, list[int]]] = []
    for line in lines:
        if not isinstance(line, (list, tuple)) or not line:
            continue
        slot = line[0]
        if not isinstance(slot, str) or slot not in SLOTS:
            # Keep uncertain positions as reviewable drafts, without presenting
            # them as positively recognized A-E labels or dropping their digits.
            hint = slot[1:] if isinstance(slot, str) and slot.startswith('?') else None
            numbers = _numbers(line[1:] if hint is not None else line)
            if hint is not None or numbers is not None:
                unlabelled = True
            if numbers is not None:
                provisional.append((hint, numbers))
            continue
        numbers = _numbers(line[1:])
        if numbers is None:
            unreadable.add(slot)
            continue
        if slot in readings and readings[slot] != numbers:
            conflicts.add(slot)
        else:
            readings[slot] = numbers
    for slot in conflicts:
        readings.pop(slot, None)
    for hint, numbers in provisional:
        slot = hint if hint in SLOTS and hint not in readings and hint not in conflicts else next(
            (s for s in SLOTS if s not in readings and s not in conflicts), None)
        if slot is None:
            conflicts.add('?')
        else:
            readings[slot] = numbers
    unreadable.difference_update(readings)
    if not readings:
        raise ValueError("no_ticket_games")
    values = {f"game_{slot.lower()}": ", ".join(map(str, readings[slot]))
              for slot in SLOTS if slot in readings}
    expected = set(SLOTS[:expected_games]) if expected_games else set(SLOTS)
    missing = expected - readings.keys()
    extra = readings.keys() - expected
    return {"values": values, "game_count": len(values), "purchase_verified": False,
            "needs_review": bool(unlabelled or unreadable or conflicts or missing or extra),
            "missing_slots": sorted(missing | unreadable | conflicts),
            "expected_games": expected_games}


def games_from_lines(lines: object) -> list[list[int]]:
    """Compatibility helper for callers needing validated games in slot order."""
    try:
        result = import_from_lines(lines)
    except ValueError:
        return []
    return [list(parse_ticket(value)) for value in result["values"].values()]
