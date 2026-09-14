"""Lock the screenshot-matched Lotto 6/45 palette across every number ball."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'custom_components/lotto_645/www'
VIEW = (WWW / 'lotto-panel-view.js').read_text(encoding='utf-8')
SHELL = (WWW / 'lotto-panel-shell.js').read_text(encoding='utf-8')


def rule(source: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r'\{([^}]+)\}', source)
    assert match, selector
    return match.group(1)


def test_recent_draw_geometry_remains_flat_and_readable():
    css = rule(VIEW, '.draw-numbers .ball')
    assert 'color:#fff;' in css
    assert 'font-weight:700;' in css
    assert 'box-shadow:none;' in css
    assert 'border:0' in css
    assert 'gradient' not in css
    assert '--ball-size:60px;' in rule(VIEW, '.draw-numbers')
    assert 'gap:18px;' in rule(VIEW, '.draw-numbers')


def test_every_number_ball_uses_user_reference_palette():
    base = rule(
        SHELL,
        '.draw-numbers .ball[data-band],\n.ticket-balls .ball[data-band]',
    )
    assert 'color:#fff;' in base
    assert 'border:0;' in base
    assert 'background-image:none;' in base
    assert 'box-shadow:none;' in base
    assert 'text-shadow:0 1px 1px rgba(0,0,0,.16);' in base

    # 1/10, 10/20, 20/30 and 40/45 bands are sampled from the first supplied
    # result image.  The 31~40 blue-gray comes from the second supplied image.
    expected = {
        1: '#e08f00',
        2: '#0063cc',
        3: '#d8314f',
        4: '#6d7381',
        5: '#2c9e44',
    }
    for band, color in expected.items():
        css = rule(
            SHELL,
            f'.draw-numbers .ball[data-band="{band}"],.ticket-balls .ball[data-band="{band}"]',
        )
        assert css == f'background:{color}'


def test_wallet_and_review_number_sizes_are_preserved():
    # Color changes must not change the existing responsive chip sizes.
    assert '--ball-size:33px' in rule(VIEW, '.ticket-balls')
    assert '--ball-size:43px' in rule(VIEW, '.wallet-paper .ticket-balls')
    assert '--ball-size:29px' in VIEW
    assert '--ball-size:clamp(26px,calc((100cqw - 142px)/7),45px)' in VIEW
    assert '@media(forced-colors:active)' in SHELL


def test_panel_shell_is_the_versioned_production_entry():
    ticket_panel = (WWW.parent / 'ticket_panel.py').read_text(encoding='utf-8')
    version = json.loads((WWW.parent / 'manifest.json').read_text(encoding='utf-8'))['version']
    assert f"module_url': f'/lotto_645_static/lotto-panel-shell.js?v={{VERSION}}'" in ticket_panel
    assert f"data-lotto-ha-host-header', '{version}'" in SHELL
    assert f"data-lotto-official-ball-colors', '{version}'" in SHELL
    assert f"import './lotto-panel.js?v={version}';" in SHELL
    assert (WWW / 'lotto-panel.js').exists()
    assert (WWW / 'lotto-panel-core.js').exists()


def test_countdown_is_rendered_in_home_hero_not_as_standalone_card():
    assert 'hero-draw-countdown' in SHELL
    assert "oldSection.hidden = true" in SHELL
    assert "0일 00시간 00분 00초" in SHELL
    assert 'sales_reopen_at' in SHELL
