from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_bonus_match_does_not_raise_validation_score():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    payload = apply_result(payload, {
        "target_round": 777,
        "generated_at": "2026-09-15T00:00:00+00:00",
        "results": [{
            "method_id": "formula", "sensor_name": "공식",
            "generation_status": "generated", "main_match_count": 2,
            "bonus_match": True,
        }],
    })
    method = summary(payload)["methods"][0]
    assert method["points"] == 0
    assert method["three_plus_hits"] == 0
