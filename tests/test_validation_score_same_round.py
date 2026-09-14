from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_repeated_same_round_counts_as_separate_validation_runs():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    sample = {
        "target_round": 500,
        "generated_at": "2026-09-15T00:00:00+00:00",
        "results": [{
            "method_id": "formula", "sensor_name": "공식",
            "generation_status": "generated", "main_match_count": 3,
        }],
    }
    payload = apply_result(payload, sample)
    payload = apply_result(payload, sample)
    board = summary(payload)
    assert board["total_runs"] == 2
    assert board["unique_rounds"] == 1
    assert board["methods"][0]["three_plus_hits"] == 2
