from custom_components.lotto_645.historical_validation_scores import summary


def test_score_policy_text_is_explicit():
    board = summary({"version": 1, "total_runs": 0, "rounds": [], "methods": {}, "recent": []})
    assert board["point_policy"] == "3개=1점 · 4개=3점 · 5개=10점 · 6개=50점"
    assert board["threshold"] == 3
