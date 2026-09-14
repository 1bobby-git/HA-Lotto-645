from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_hit_rate_uses_generated_attempts_only():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    for i, (status, matches) in enumerate((("generated", 3), ("generated", 1), ("unavailable", 0)), 1):
        payload = apply_result(payload, {
            "target_round": 1300 + i,
            "generated_at": "2026-09-15T00:00:00+00:00",
            "results": [{"method_id": "formula", "sensor_name": "공식", "generation_status": status, "main_match_count": matches}],
        })
    method = summary(payload)["methods"][0]
    assert method["hit_rate"] == 50.0
