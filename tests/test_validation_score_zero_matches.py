from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_zero_to_two_matches_do_not_score():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    for matches in range(3):
        payload = apply_result(payload, {
            "target_round": 950 + matches,
            "generated_at": "2026-09-15T00:00:00+00:00",
            "results": [{"method_id": "formula", "sensor_name": "공식", "generation_status": "generated", "main_match_count": matches}],
        })
    method = summary(payload)["methods"][0]
    assert method["points"] == 0
    assert method["three_plus_hits"] == 0
    assert method["generated"] == 3
