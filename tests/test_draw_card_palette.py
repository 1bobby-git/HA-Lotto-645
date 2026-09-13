"""White draw card palette regressions; not a whole-page WCAG conformance test."""
from pathlib import Path
import re

import pytest

VIEW = (Path(__file__).resolve().parents[1] / 'custom_components/lotto_645/www/lotto-panel-view.js').read_text(encoding='utf-8')


def rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r'\s*\{([^}]+)\}', VIEW)
    assert match, selector
    return match.group(1)


PALETTE = dict(re.findall(r'--draw-([a-z-]+):(#[a-f0-9]+)', rule('.draw-stage')))


def luminance(color: str) -> float:
    value = color.removeprefix('#')
    if len(value) == 3:
        value = ''.join(channel * 2 for channel in value)
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in channels]
    return sum(x * weight for x, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


@pytest.mark.parametrize(('foreground', 'background'), [
    ('ink', 'bg'), ('muted', 'bg'), ('ink', 'soft'), ('muted', 'soft'),
    ('accent', 'bg'), ('accent', 'soft'), ('accent', 'action-bg'),
    ('accent', 'action-hover'), ('positive', 'positive-bg'),
    ('warning', 'warning-bg'), ('danger', 'danger-bg'),
])
def test_surrounding_text_colors_meet_4_5_contrast(foreground: str, background: str):
    low, high = sorted((luminance(PALETTE[foreground]), luminance(PALETTE[background])))
    assert (high + 0.05) / (low + 0.05) >= 4.5


def test_card_is_plain_white_and_isolated_from_ha_dark_tokens():
    css = rule('.draw-stage')
    assert PALETTE['bg'] == '#fff'
    assert 'background:var(--draw-bg)' in css
    assert 'color:var(--draw-ink)' in css
    assert 'color-scheme:light' in css
    assert 'gradient' not in css
    assert '--draw-' not in rule(':host([data-theme="dark"])')
    assert '--bg:#11151c;' in rule(':host([data-theme="dark"])')


def test_statuses_keep_distinct_readable_backgrounds_and_symbols():
    assert 'color:var(--draw-positive)' in rule('.verification')
    assert 'background:var(--draw-positive-bg)' in rule('.verification')
    for state, name in (('pending', 'warning'), ('conflict', 'danger')):
        css = rule(f'.verification[data-state="{state}"]')
        assert f'color:var(--draw-{name})' in css
        assert f'background:var(--draw-{name}-bg)' in css
    assert "content:'✓'" in rule('.verification::before')
    assert "content:'◷'" in rule('.verification[data-state="pending"]::before')
    assert "content:'!'" in rule('.verification[data-state="conflict"]::before')


def test_descriptions_actions_and_focus_use_the_card_palette():
    for selector in ('.draw-kicker', '.bonus-caption', '.plus', '.result-copy .caption', '.draw-details'):
        assert 'color:var(--draw-muted)' in rule(selector)
    assert 'color:var(--draw-accent)' in rule('.draw-foot button')
    assert 'background:var(--draw-action-bg)' in rule('.draw-foot button')
    assert 'color:var(--draw-accent)' in rule('.draw-details a')
    assert 'outline-color:var(--draw-accent)' in rule('.draw-stage :focus-visible')
    assert 'border-top:1px solid var(--draw-line)' in rule('.draw-foot')


def test_small_card_labels_and_refresh_target_are_not_shrunk_on_mobile():
    for selector in ('.verification', '.bonus-caption', '.draw-details'):
        for css in re.findall(re.escape(selector) + r'\s*\{([^}]+)\}', VIEW):
            assert all(int(size) >= 12 for size in re.findall(r'font-size:(\d+)px', css)), selector
    for css in re.findall(re.escape('.draw-foot button') + r'\s*\{([^}]+)\}', VIEW):
        assert 'min-height:44px' in css
