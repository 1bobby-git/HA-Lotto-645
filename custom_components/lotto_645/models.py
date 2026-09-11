"""Data models for Lotto 6/45 Analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class LottoDraw:
    """One Lotto 6/45 draw."""

    round: int
    draw_date: str
    numbers: tuple[int, int, int, int, int, int]
    bonus: int
    first_prize_winners: int | None = None
    first_prize_amount: int | None = None

    def to_storage(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "round": self.round,
            "draw_date": self.draw_date,
            "numbers": list(self.numbers),
            "bonus": self.bonus,
            "first_prize_winners": self.first_prize_winners,
            "first_prize_amount": self.first_prize_amount,
        }

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> "LottoDraw":
        """Create a draw from stored data."""
        numbers = tuple(int(value) for value in data["numbers"])
        if len(numbers) != 6:
            raise ValueError("A Lotto draw must contain exactly six numbers")
        return cls(
            round=int(data["round"]),
            draw_date=str(data.get("draw_date", "")),
            numbers=numbers,  # type: ignore[arg-type]
            bonus=int(data["bonus"]),
            first_prize_winners=(
                int(data["first_prize_winners"])
                if data.get("first_prize_winners") is not None
                else None
            ),
            first_prize_amount=(
                int(data["first_prize_amount"])
                if data.get("first_prize_amount") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class Recommendation:
    """One recommended six-number game."""

    index: int
    label: str
    method: str
    numbers: tuple[int, int, int, int, int, int]
    reason: str
    score: float
    details: dict[str, Any]

    def as_attributes(self) -> dict[str, Any]:
        """Return Home Assistant-safe attributes."""
        return {
            "game": self.index,
            "label": self.label,
            "method": self.method,
            "numbers": list(self.numbers),
            "core_reason": self.reason,
            "analysis_score": round(self.score, 4),
            **self.details,
        }


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Analysis result derived from historical draws."""

    target_round: int
    based_on_round: int
    recommendations: tuple[Recommendation, ...]
    summary: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Lotto645Data:
    """Coordinator payload."""

    latest_draw: LottoDraw
    analysis: AnalysisResult
    history_count: int
    generated_at: datetime
    source_status: str
