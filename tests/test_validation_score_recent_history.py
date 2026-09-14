from custom_components.lotto_645.historical_validation_scores import apply_result, summary, MAX_RECENT


def test_recent_validation_history_is_bounded_without_losing_totals():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    for run in range(MAX_RECENT + 7):
        payload = apply_result(payload, {
            "target_round": 100 + run,
            "generated_at": f"2026-09-15T00:{run % 60:02d}:00+00:00",
            "results": [{
                "method_id": "formula", "sensor_name": "공식",
                "generation_status": "generated", "main_match_count": 3,
            }],
        })
    board = summary(payload)
    assert board["total_runs"] == MAX_RECENT + 7
    assert board["unique_rounds"] == MAX_RECENT + 7
    assert len(board["recent"]) == MAX_RECENT
    assert board["methods"][0]["points"] == MAX_RECENT + 7
