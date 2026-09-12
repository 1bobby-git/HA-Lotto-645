from __future__ import annotations

from datetime import UTC, datetime

from custom_components.lotto_645.models import LottoDraw, Recommendation
from custom_components.lotto_645.result_evaluator import (
    evaluate_recommendations,
    evaluate_ticket,
)


DRAW = LottoDraw(
    round=2000,
    draw_date="2026-09-12",
    numbers=(1, 2, 3, 4, 5, 6),
    bonus=7,
)


def test_official_prize_rules():
    assert evaluate_ticket((1, 2, 3, 4, 5, 6), DRAW)["prize"] == "1등"
    assert evaluate_ticket((1, 2, 3, 4, 5, 7), DRAW)["prize"] == "2등"
    assert evaluate_ticket((1, 2, 3, 4, 5, 8), DRAW)["prize"] == "3등"
    assert evaluate_ticket((1, 2, 3, 4, 8, 9), DRAW)["prize"] == "4등"
    assert evaluate_ticket((1, 2, 3, 8, 9, 10), DRAW)["prize"] == "5등"
    assert evaluate_ticket((1, 2, 8, 9, 10, 11), DRAW)["prize"] == "미당첨"


def test_evaluate_all_saved_recommendations():
    recommendations = (
        Recommendation(
            1,
            "method_a",
            "센서 A",
            "test",
            (1, 2, 3, 8, 9, 10),
            "reason",
            0.5,
            {},
        ),
        Recommendation(
            2,
            "method_b",
            "센서 B",
            "test",
            (10, 11, 12, 13, 14, 15),
            "reason",
            0.4,
            {},
        ),
    )
    evaluated = evaluate_recommendations(
        DRAW,
        recommendations,
        prediction_snapshot={
            "based_on_round": 1999,
            "local_generation_sequence": 3,
            "local_generated_at": "2026-09-12T09:00:00+00:00",
        },
        evaluated_at=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
    )
    assert evaluated["round"] == 2000
    assert evaluated["checked_game_count"] == 2
    assert evaluated["winning_game_count"] == 1
    assert evaluated["highest_prize"] == "5등"
    assert evaluated["highest_prize_sensor"] == "센서 A"
    assert evaluated["results"][0]["status"] == "당첨"
    assert evaluated["results"][1]["status"] == "미당첨"
