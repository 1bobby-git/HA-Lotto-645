from custom_components.lotto_645.historical_validation_scores import apply_result, summary


def result(round_no, rows):
    return {
        "target_round": round_no,
        "generated_at": "2026-09-15T00:00:00+00:00",
        "results": rows,
    }


def row(method_id, matches, status="generated"):
    return {
        "method_id": method_id,
        "sensor_name": method_id,
        "generation_status": status,
        "main_match_count": matches,
    }


def test_scores_every_completed_run_and_only_three_plus_matches():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    payload = apply_result(payload, result(100, [row("a", 2), row("b", 3), row("c", 4)]))
    payload = apply_result(payload, result(100, [row("a", 5), row("b", 3), row("c", 0, "unavailable")]))
    board = summary(payload)

    assert board["total_runs"] == 2
    assert board["unique_rounds"] == 1
    methods = {item["method_id"]: item for item in board["methods"]}
    assert methods["a"]["points"] == 10
    assert methods["a"]["three_plus_hits"] == 1
    assert methods["b"]["points"] == 2
    assert methods["b"]["three_plus_hits"] == 2
    assert methods["c"]["points"] == 3
    assert methods["c"]["unavailable"] == 1
    assert board["methods"][0]["method_id"] == "a"


def test_weight_policy_tracks_3_4_5_6_separately():
    payload = {"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []}
    for round_no, matches in enumerate((3, 4, 5, 6), 200):
        payload = apply_result(payload, result(round_no, [row("formula", matches)]))
    method = summary(payload)["methods"][0]

    assert method["points"] == 64
    assert method["match_3"] == 1
    assert method["match_4"] == 1
    assert method["match_5"] == 1
    assert method["match_6"] == 1
    assert method["hit_rate"] == 100.0
    assert method["best_match"] == 6
