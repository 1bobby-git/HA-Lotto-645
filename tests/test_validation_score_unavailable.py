from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_unavailable_formula_counts_attempt_without_score():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    payload = apply_result(payload, {
        "target_round": 1200,
        "generated_at": "2026-09-15T00:00:00+00:00",
        "results": [{"method_id": "formula", "sensor_name": "공식", "generation_status": "unavailable"}],
    })
    method = summary(payload)["methods"][0]
    assert method["attempts"] == 1 and method["unavailable"] == 1
    assert method["generated"] == 0 and method["points"] == 0
