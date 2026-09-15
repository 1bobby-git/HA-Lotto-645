from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_validation_scoreboard_and_mobile_contract():
    js = (ROOT / 'custom_components/lotto_645/www/lotto-panel-validation.js').read_text()
    assert 'validation_scoreboard' in js and 'rankedRows' in js
    assert '총 ${fmt(score.total_runs)}회' in js
    assert 'validation-score-grid' not in js and 'validation-score-card' not in js
    assert '3개 이상' in js and 'points_per_100' in js
    assert '@container wallet (max-width:560px)' in js
    assert '.validation-form .primary{width:100%;min-height:44px' in js
    assert 'window.confirm(' in js and 'confirmed:true' in js
    assert 'validation-reset-notice' in js and '초기화' in js
    assert all(f'tr[data-rank="{rank}"]' in js for rank in (1,2,3))
    assert 'localStorage' not in js and 'setInterval' not in js
