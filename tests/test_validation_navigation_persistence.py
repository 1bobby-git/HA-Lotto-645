from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_historical_validation_survives_panel_navigation_contract():
    backend = (ROOT / 'custom_components/lotto_645/ticket_panel.py').read_text()
    frontend = (ROOT / 'custom_components/lotto_645/www/lotto-panel-validation.js').read_text()
    assert 'hass.async_create_task(' in backend and 'await asyncio.shield(task)' in backend
    assert 'lotto_645/historical_validation_state' in backend and "'validation_states'" in backend
    assert "request('historical_validation_state')" in frontend
    compact = frontend.replace(' ', '')
    assert "state.status==='running'" in compact and "state.status==='completed'" in compact
    assert 'this.render(state.result)' in frontend
    assert '페이지를 이동해도 계속됩니다' in frontend
    assert 'expected_cycle' in (ROOT / 'custom_components/lotto_645/historical_validation_runtime.py').read_text()
