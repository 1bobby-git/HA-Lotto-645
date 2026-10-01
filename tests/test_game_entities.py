"""Per-game formula sensor identity and naming (does not import Home Assistant)."""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
PACKAGE = 'lotto_game_entities_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
entities = __import__(PACKAGE + '.game_entities', fromlist=['game_entities'])


def test_first_game_keeps_the_legacy_unique_id():
    assert entities.game_unique_id('entry', 'hot_numbers', 1) == 'entry_method_hot_numbers'


def test_extra_games_use_a_stable_suffix():
    assert entities.game_unique_id('entry', 'hot_numbers', 2) == 'entry_method_hot_numbers_g2'
    assert entities.game_unique_id('entry', 'hot_numbers', 10) == 'entry_method_hot_numbers_g10'


def test_configured_count_lists_every_sensor_identity():
    assert entities.game_unique_ids('entry', 'hot_numbers', 3) == {
        'entry_method_hot_numbers',
        'entry_method_hot_numbers_g2',
        'entry_method_hot_numbers_g3',
    }


def test_a_count_below_one_still_keeps_the_primary_sensor():
    assert entities.game_unique_ids('entry', 'hot_numbers', 0) == {'entry_method_hot_numbers'}


def test_names_carry_the_game_number_without_review_stars():
    plain = entities.game_entity_name(1, '빈도 프리셋 · 핫넘버')
    assert plain == '1번 | 빈도 프리셋 · 핫넘버'
    assert '☆' not in plain and '★' not in plain
    bought = entities.game_entity_name(5, '빈도 프리셋 · 핫넘버', purchased=True)
    assert bought == '5번 | ✓구매일치 | 빈도 프리셋 · 핫넘버'
