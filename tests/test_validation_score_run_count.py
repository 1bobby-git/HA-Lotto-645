from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_one_validation_is_one_run_even_with_many_formulas():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    payload = apply_result(payload, {
        "target_round": 1100,
        "generated_at": "2026-09-15T00:00:00+00:00",
        "results": [
            {"method_id": f"f{i}", "sensor_name": f"공식 {i}", "generation_status": "generated", "main_match_count": i % 4}
            for i in range(8)
        ],
    })
    assert summary(payload)["total_runs"] == 1
