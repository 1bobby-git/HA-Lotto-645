from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_validation_score_is_separate_from_recommendation_review():
    scoring = (ROOT / 'custom_components/lotto_645/historical_validation_scores.py').read_text()
    runtime = (ROOT / 'custom_components/lotto_645/historical_validation_runtime.py').read_text()
    assert 'POINTS = {3: 1, 4: 3, 5: 10, 6: 50}' in scoring
    assert 'async_record_validation_score' in runtime
    assert 'review_book' not in scoring
    assert 'review_score' not in scoring
