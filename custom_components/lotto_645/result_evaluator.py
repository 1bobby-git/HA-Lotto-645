"""Evaluate saved Lotto recommendations against a completed draw."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable

from .models import LottoDraw, Recommendation


def evaluate_ticket(
    numbers: tuple[int, int, int, int, int, int],
    draw: LottoDraw,
) -> dict[str, Any]:
    """Return the official Lotto 6/45 prize classification for one ticket."""
    if (len(numbers) != 6 or len(set(numbers)) != 6
            or any(type(n) is not int or not 1 <= n <= 45 for n in numbers)):
        raise ValueError("Ticket needs six distinct integers between 1 and 45")
    values = set(numbers)
    winning = set(draw.numbers)
    matched = tuple(sorted(values & winning))
    main_matches = len(matched)
    bonus_match = draw.bonus in values

    if main_matches == 6:
        rank, prize = 1, "1등"
    elif main_matches == 5 and bonus_match:
        rank, prize = 2, "2등"
    elif main_matches == 5:
        rank, prize = 3, "3등"
    elif main_matches == 4:
        rank, prize = 4, "4등"
    elif main_matches == 3:
        rank, prize = 5, "5등"
    else:
        rank, prize = None, "미당첨"

    return {
        "status": "당첨" if rank is not None else "미당첨",
        "prize": prize,
        "prize_rank": rank,
        "main_match_count": main_matches,
        "matched_main_numbers": list(matched),
        "bonus_match": bonus_match,
        "matched_bonus_number": draw.bonus if bonus_match else None,
    }


def evaluate_recommendations(
    draw: LottoDraw,
    recommendations: Iterable[Recommendation],
    *,
    prediction_snapshot: dict[str, Any] | None = None,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate every recommendation that was saved for ``draw.round``."""
    results: list[dict[str, Any]] = []
    for recommendation in recommendations:
        ticket = evaluate_ticket(recommendation.numbers, draw)
        results.append(
            {
                "method_id": recommendation.method_id,
                "sensor_name": recommendation.label,
                "source": recommendation.source,
                "recommended_numbers": list(recommendation.numbers),
                **ticket,
            }
        )

    winners = [item for item in results if item["status"] == "당첨"]
    losers = [item for item in results if item["status"] == "미당첨"]
    ranked_winners = [item for item in winners if item["prize_rank"] is not None]
    highest = (
        min(ranked_winners, key=lambda item: item["prize_rank"])
        if ranked_winners
        else None
    )
    when = evaluated_at or datetime.now(UTC)

    snapshot = prediction_snapshot or {}
    return {
        "round": draw.round,
        "draw_date": draw.draw_date,
        "winning_numbers": list(draw.numbers),
        "bonus_number": draw.bonus,
        "evaluated_at": when.isoformat(),
        "prediction_based_on_round": snapshot.get("based_on_round"),
        "prediction_generation_sequence": snapshot.get("local_generation_sequence"),
        "prediction_generated_at": snapshot.get("local_generated_at"),
        "checked_game_count": len(results),
        "winning_game_count": len(winners),
        "losing_game_count": len(losers),
        "highest_prize": highest["prize"] if highest else "미당첨",
        "highest_prize_sensor": highest["sensor_name"] if highest else None,
        "results": results,
        "winners": winners,
        "losers": losers,
    }
