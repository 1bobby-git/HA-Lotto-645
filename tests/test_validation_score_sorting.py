from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_weighted_points_drive_scoreboard_order():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    payload = apply_result(payload, {
        "target_round": 900,
        "generated_at": "2026-09-15T00:00:00+00:00",
        "results": [
            {"method_id": "three", "sensor_name": "3개 공식", "generation_status": "generated", "main_match_count": 3},
            {"method_id": "five", "sensor_name": "5개 공식", "generation_status": "generated", "main_match_count": 5},
        ],
    })
    board = summary(payload)
    assert [row["method_id"] for row in board["methods"]] == ["five", "three"]
