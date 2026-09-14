from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_best_match_retains_maximum_observed_main_matches():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    for i, matches in enumerate((4, 2, 5, 3), 1):
        payload = apply_result(payload, {
            "target_round": 1400 + i,
            "generated_at": "2026-09-15T00:00:00+00:00",
            "results": [{"method_id": "formula", "sensor_name": "공식", "generation_status": "generated", "main_match_count": matches}],
        })
    assert summary(payload)["methods"][0]["best_match"] == 5
