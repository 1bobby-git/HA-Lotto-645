from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_validation_scoreboard_and_mobile_contract():
    js = (ROOT / 'custom_components/lotto_645/www/lotto-panel-validation.js').read_text()
    assert 'validation_scoreboard' in js
    assert '누적 과거 검증 점수' in js
    assert '총 ${Number(score.total_runs' in js
    assert '3개 이상' in js
    assert '@container wallet (max-width:560px)' in js
    assert '.validation-score-grid{grid-template-columns:1fr' in js
    assert '.validation-form .primary{width:100%;min-height:48px' in js
    assert 'localStorage' not in js and 'setInterval' not in js
