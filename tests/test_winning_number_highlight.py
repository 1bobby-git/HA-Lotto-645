from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VIEW=(ROOT/'custom_components/lotto_645/www/lotto-panel-view.js').read_text()
CORE=(ROOT/'custom_components/lotto_645/www/lotto-panel-core.js').read_text()


def test_winning_review_uses_exact_result_metadata_and_accessible_states():
    assert 'export function renderPredictionRows' in VIEW
    assert 'matched_main_numbers' in VIEW and 'matched_bonus_number' in VIEW
    assert "el.dataset.hit=matchedMain.has(n)?'main':n===matchedBonus?'bonus':'miss'" in VIEW
    assert '당첨번호 일치' in VIEW and '보너스 일치' in VIEW and '미일치' in VIEW
    assert "renderPredictionRows(this.node('predictions')" in CORE


def test_only_winning_games_are_dimmed_or_outlined():
    assert 'Number.isInteger(outcome?.prize_rank)' in VIEW
    assert '.result-balls[data-winning="true"] .ball[data-hit="main"]' in VIEW
    assert '.result-balls[data-winning="true"] .ball[data-hit="bonus"]' in VIEW
    assert '.result-balls[data-winning="true"] .ball[data-hit="miss"]' in VIEW
    assert 'opacity:.38' in VIEW
    assert '@media(forced-colors:active)' in VIEW
