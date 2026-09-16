"""Data models for Lotto 6/45 Analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


PUBLIC_DETAIL_KEYS = frozenset({
    "formula_id", "formula_version", "core_version", "generation_id", "generated_at",
    "target_round", "based_on_round", "history_cutoff_round", "generation_sequence",
    "method_description", "method_category", "number_sum", "odd_count", "low_count_1_22",
    "number_source", "ai_role", "base_formula_id", "provider", "basis", "first_prize_odds",
    "disclaimer", "public_reason", "consensus_updated_at", "consensus_source_method_ids",
    "consensus_status", "reason_code", "status", "rng", "uniformity", "exclusions",
    "history_used_for_weighting", "exact_past_first_prize_match", "latest_draw_overlap",
    "max_numbers_matching_any_past_first_prize"
})

def public_details(value):
    return {k: v for k, v in value.items() if k in PUBLIC_DETAIL_KEYS}


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
        raw = data["numbers"]
        if not isinstance(raw, (list, tuple)) or any(type(n) is not int for n in raw):
            raise ValueError("Recommendation numbers must be integers")
        numbers = tuple(sorted(raw))
        if len(numbers) != 6 or len(set(numbers)) != 6:
            raise ValueError("A Lotto draw must contain six distinct numbers")
        if any(number < 1 or number > 45 for number in numbers):
            raise ValueError("Lotto numbers must be between 1 and 45")
        bonus = int(data["bonus"])
        if bonus < 1 or bonus > 45 or bonus in numbers:
            raise ValueError("Bonus number must be between 1 and 45 and not a main number")
        return cls(
            round=int(data["round"]),
            draw_date=str(data.get("draw_date", "")),
            numbers=numbers,  # type: ignore[arg-type]
            bonus=bonus,
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
    method_id: str
    label: str
    method: str
    numbers: tuple[int, int, int, int, int, int]
    reason: str
    score: float | None
    details: dict[str, Any]
    source: str = "local"

    def as_attributes(self) -> dict[str, Any]:
        """Return Home Assistant-safe attributes."""
        attributes: dict[str, Any] = {
            "game": self.index,
            "method_id": self.method_id,
            "formula_id": self.method_id,
            "formula": self.method_id,
            "formula_version": self.details.get("formula_version", 1),
            "label": self.label,
            "method": self.method,
            "source": self.source,
            "numbers": list(self.numbers),
            "core_reason": self.reason,
            **public_details(self.details),
        }
        if self.score is not None:
            attributes["analysis_score"] = round(self.score, 4)
        return attributes

    def to_storage(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for cached AI results."""
        return {
            "index": self.index,
            "method_id": self.method_id,
            "formula_id": self.method_id,
            "formula": self.method_id,
            "formula_version": self.details.get("formula_version", 1),
            "label": self.label,
            "method": self.method,
            "numbers": list(self.numbers),
            "reason": self.reason,
            "score": self.score,
            "details": public_details(self.details),
            "source": self.source,
        }

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> "Recommendation":
        """Restore a cached recommendation."""
        raw = data["numbers"]
        if not isinstance(raw, (list, tuple)) or any(type(n) is not int for n in raw):
            raise ValueError("Recommendation numbers must be integers")
        numbers = tuple(sorted(raw))
        if len(numbers) != 6 or len(set(numbers)) != 6:
            raise ValueError("Recommendation must contain six distinct numbers")
        if any(number < 1 or number > 45 for number in numbers):
            raise ValueError("Recommendation numbers must be between 1 and 45")
        score = data.get("score")
        return cls(
            index=int(data.get("index", 1)),
            method_id=str(data.get("formula_id", data.get("formula", data.get("method_id", "unknown")))),
            label=str(data.get("label", "추천")),
            method=str(data.get("method", "")),
            numbers=numbers,  # type: ignore[arg-type]
            reason=str(data.get("reason", "")),
            score=float(score) if score is not None else None,
            details=public_details(dict(data.get("details", {}))),
            source=str(data.get("source", "local")),
        )


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Analysis result derived from historical draws."""

    target_round: int
    based_on_round: int
    recommendations: tuple[Recommendation, ...]
    summary: dict[str, Any]

    def recommendation_by_method(self, method_id: str) -> Recommendation | None:
        """Return the recommendation generated by a selected method."""
        return next(
            (
                recommendation
                for recommendation in self.recommendations
                if recommendation.method_id == method_id
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class Lotto645Data:
    """Coordinator payload."""

    latest_draw: LottoDraw
    analysis: AnalysisResult
    history_count: int
    generated_at: datetime
    source_status: str
    ai_recommendation: Recommendation | None = None
    ai_status: str = "disabled"
    ai_error: str | None = None
    ai_generated_at: datetime | None = None
