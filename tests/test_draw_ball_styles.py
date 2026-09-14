"""Lock the Donghaeng Lotto 6/45 palette across every rendered number ball."""
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


def test_every_number_ball_uses_donghaeng_palette():
    base = rule(
        SHELL,
        '.draw-numbers .ball[data-band],\n.ticket-balls .ball[data-band]',
    )
    assert 'color:#fff;' in base
    assert 'border:0;' in base
    assert 'background-image:none;' in base
    assert 'box-shadow:none;' in base

    expected = {
        1: ('#fbc400', 'rgba(73,57,0,.8)'),
        2: ('#69c8f2', 'rgba(0,49,70,.8)'),
        3: ('#ff7272', 'rgba(64,0,0,.8)'),
        4: ('#aaa', 'rgba(61,61,61,.8)'),
        5: ('#b0d840', 'rgba(41,56,0,.8)'),
    }
    for band, (color, shadow) in expected.items():
        css = rule(
            SHELL,
            f'.draw-numbers .ball[data-band="{band}"],.ticket-balls .ball[data-band="{band}"]',
        )
        assert f'background:{color};' in css
        assert f'text-shadow:0 0 3px {shadow};' in css


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
    assert "import './lotto-panel.js?v=1.11.5';" in SHELL
    assert (WWW / 'lotto-panel.js').exists()
    assert (WWW / 'lotto-panel-core.js').exists()
