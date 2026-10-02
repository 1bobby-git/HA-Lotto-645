"""Group OCR text from a ticket photo into A-E games.

Online purchases have no QR code, so the panel falls back to reading the printed
numbers. OCR is never trusted: a line is only accepted when it contains exactly
six distinct integers between 1 and 45. Ticket serials, dates, the round number
and the price are rejected by the same rule.
"""
from __future__ import annotations

import re

from .purchased_tickets import SLOTS, parse_ticket

_DIGITS = re.compile(r"\d+")
_MAX_TOKENS = 4000
_MAX_LINES = 60


def _tokens(line: object) -> list[int]:
    """Every standalone integer of one OCR line, ignoring text and noise."""
    if not isinstance(line, (list, tuple)):
        return []
    numbers: list[int] = []
    for raw in line[:64]:
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text or len(text) > 16:
            continue
        # Keep plain numbers only: "1,000", "10.02", "A1" are not tickets.
        if not re.fullmatch(r"\d{1,2}", text):
            continue
        numbers.append(int(text))
    return numbers


def _valid(values: list[int]) -> bool:
    return len(values) == 6 and len(set(values)) == 6 and all(1 <= value <= 45 for value in values)


def games_from_lines(lines: object) -> list[list[int]]:
    """Return every valid six-number game, in reading order, deduplicated.

    The page sends two passes: the engine's own line text followed by rows it
    rebuilt from word boxes. A game seen by both is kept once — token order
    inside a row differs between passes — and the first pass keeps its slot.
    """
    if not isinstance(lines, list) or len(lines) > _MAX_LINES:
        return []
    found: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for line in lines:
        numbers = _tokens(line)
        if not _valid(numbers):
            continue
        key = tuple(sorted(numbers))
        if key in seen:
            continue
        seen.add(key)
        found.append(list(numbers))
        if len(found) == len(SLOTS):
            break
    return found


def import_from_lines(lines: object) -> dict[str, object]:
    """Return round-scoped purchase values parsed from OCR lines.

    The photo may print the draw round; when it does, the games are only
    accepted for that round so numbers from another round are never saved into
    the current one.
    """
    games = games_from_lines(lines)
    if not games:
        raise ValueError("no_ticket_games")
    values: dict[str, str] = {}
    for slot, numbers in zip(SLOTS, games):
        # Reuse the canonical parser so storage rules stay identical to typing.
        values[f"game_{slot.lower()}"] = ", ".join(map(str, parse_ticket(numbers)))
    return {"values": values, "game_count": len(games), "purchase_verified": False}