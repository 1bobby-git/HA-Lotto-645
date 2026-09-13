"""Lock the screenshot-matched style to the recent draw area, not ticket chips."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'custom_components/lotto_645/www'
VIEW = (WWW / 'lotto-panel-view.js').read_text(encoding='utf-8')


def rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r'\{([^}]+)\}', VIEW)
    assert match, selector
    return match.group(1)


def test_recent_draw_uses_flat_white_number_balls():
    css = rule('.draw-numbers .ball')
    assert 'color:#fff;' in css
    assert 'font-weight:700;' in css
    assert 'box-shadow:none;' in css
    assert 'border:0' in css
    assert 'gradient' not in css
    assert '--ball-size:60px;' in rule('.draw-numbers')
    assert 'gap:18px;' in rule('.draw-numbers')


def test_all_five_number_bands_have_solid_colors():
    # Gray (31-40) is a neutral continuation; not present in the supplied image.
    expected = {1: '#cd9234', 2: '#3e63c5', 3: '#bd4152', 4: '#8c8c8c', 5: '#5a9b50'}
    for band, color in expected.items():
        assert rule(f'.draw-numbers .ball[data-band="{band}"]') == f'background:{color}'
    # The plus sign now uses readable gray on the requested white background.
    assert 'color:var(--draw-muted)' in rule('.plus')


def test_wallet_chips_and_responsive_sizing_are_preserved():
    css = rule('.ticket-balls .ball')
    assert 'background:transparent;' in css
    assert 'border:1px solid var(--line);' in css
    assert 'color:var(--ink)' in css
    assert '--ball-size:clamp(26px,calc((100cqw - 142px)/7),45px)' in VIEW
    assert '@media(forced-colors:active)' in VIEW


def test_view_import_has_the_new_cache_key():
    controller = (WWW / 'lotto-panel.js').read_text(encoding='utf-8')
    version = json.loads((WWW.parent / 'manifest.json').read_text(encoding='utf-8'))['version']
    assert f"from './lotto-panel-view.js?v={version}';" in controller
