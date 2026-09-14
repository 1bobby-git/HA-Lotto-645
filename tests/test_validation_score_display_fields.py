from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def test_score_summary_exposes_mobile_display_metrics():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    payload = apply_result(payload, {
        "target_round": 1000,
        "generated_at": "2026-09-15T00:00:00+00:00",
        "results": [{"method_id": "formula", "sensor_name": "공식", "generation_status": "generated", "main_match_count": 4}],
    })
    method = summary(payload)["methods"][0]
    for key in ("points", "three_plus_hits", "hit_rate", "best_match", "generated", "unavailable", "match_3", "match_4", "match_5", "match_6"):
        assert key in method
