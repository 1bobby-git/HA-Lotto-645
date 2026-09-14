"""Pure metadata/packaging regression tests without importing Home Assistant."""
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import re
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components/lotto_645'
PACKAGE = '_lotto_panel_metadata_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package
metadata = importlib.import_module(PACKAGE + '.panel_metadata')
methods = importlib.import_module(PACKAGE + '.methods')


def at(value):
    return datetime.fromisoformat(value)


def test_regular_schedule_matches_round_and_korean_timezone():
    schedule = metadata.draw_schedule(1241, 'official_history', now=at('2026-09-14T00:00:00+00:00'))
    assert schedule['round'] == 1242
    assert schedule['scheduled_at'] == '2026-09-19T20:35:00+09:00'
    assert schedule['sales_reopen_at'] == '2026-09-20T06:00:00+09:00'
    assert schedule['rollover_at'] == schedule['sales_reopen_at']
    assert schedule['server_now'] == '2026-09-14T09:00:00+09:00'
    assert schedule['basis'] == 'regular_schedule'
    assert '일요일 06:00' in schedule['notice']


@pytest.mark.parametrize('status', ['waiting', 'conflict', 'official_history', 'official_confirmed'])
def test_draw_deadline_stays_on_current_round_until_sales_reopen(status):
    schedule = metadata.draw_schedule(1241, status, now=at('2026-09-12T21:00:00+09:00'))
    assert schedule['round'] == 1241
    assert schedule['scheduled_at'] == '2026-09-12T20:35:00+09:00'
    assert schedule['sales_reopen_at'] == '2026-09-13T06:00:00+09:00'


def test_sunday_before_0600_keeps_completed_round_at_zero_window():
    schedule = metadata.draw_schedule(1241, 'official_confirmed', now=at('2026-09-13T05:59:59+09:00'))
    assert schedule['round'] == 1241
    assert schedule['scheduled_at'] == '2026-09-12T20:35:00+09:00'
    assert schedule['rollover_at'] == '2026-09-13T06:00:00+09:00'


def test_sunday_0600_starts_next_purchasable_round_countdown():
    schedule = metadata.draw_schedule(1241, 'official_confirmed', now=at('2026-09-13T06:00:00+09:00'))
    assert schedule['round'] == 1242
    assert schedule['scheduled_at'] == '2026-09-19T20:35:00+09:00'
    assert schedule['sales_reopen_at'] == '2026-09-20T06:00:00+09:00'


def test_anchor_and_date_validation():
    assert metadata.draw_schedule(now=at('2002-12-07T00:00:00+09:00'))['round'] == 1
    with pytest.raises(ValueError):
        metadata.draw_schedule(now=datetime(2026,9,14))
    with pytest.raises(ValueError):
        metadata.draw_schedule(now=at('2002-01-01T00:00:00+09:00'))
    kst = at('2026-09-19T20:34:59+09:00')
    assert metadata.draw_schedule(now=kst) == metadata.draw_schedule(now=kst.astimezone(timezone.utc))


def test_all_local_guides_are_packaged_verbatim_and_ai_is_separate():
    result = metadata.panel_metadata(1241, 'official_history')
    catalog = result['method_catalog']
    assert len(methods.METHODS) == 19
    assert len(catalog) == 20
    assert len({m['method_id'] for m in catalog}) == 20
    for method in methods.METHODS:
        source = ROOT / 'docs/methods' / (method.method_id + '.md')
        bundled = COMPONENT / 'www/methods' / source.name
        assert bundled.read_bytes() == source.read_bytes(), method.method_id
    assert (COMPONENT / 'www/methods/home_assistant_ai.md').read_bytes() == (ROOT / 'docs/AI_RECOMMENDATION.md').read_bytes()
    # Only public metadata, not profiles, prompts, tokens or dynamic AI calls.
    assert set(result) == {'method_catalog', 'archived_method_catalog', 'draw_schedule'}
    for item in catalog:
        assert {'method_id','name','category','description','requirements'} <= set(item)
    assert '생년월일' not in json.dumps(result, ensure_ascii=False).split('requirements')[0]


def test_shell_and_packaged_tools_use_the_same_tools_cache_version():
    # A presentation-only release may leave the tools module byte-for-byte
    # unchanged.  Its own cache version and the shell import must still match.
    tools = (COMPONENT / 'www/lotto-panel-tools.js').read_text()
    shell = (COMPONENT / 'www/lotto-panel-shell.js').read_text()
    tools_version = re.search(r"const VERSION = '([^']+)'", tools)
    shell_version = re.search(r"\./lotto-panel-tools\.js\?v=([0-9.]+)", shell)
    assert tools_version and shell_version
    assert tools_version.group(1) == shell_version.group(1)
    assert 'applyPanelTools(this)' in shell
