"""Current catalogue and legacy-safe option projection."""
import importlib.util
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cleanup_methods',ROOT/'custom_components/lotto_645/methods.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)


def test_retired_profiles_are_not_selectable_or_generated():
    assert len(m.RETIRED_METHOD_LABELS)==5
    assert not set(m.RETIRED_METHOD_LABELS)&set(m.METHODS_BY_ID)
    assert m.normalize_method_ids(list(m.RETIRED_METHOD_LABELS))==m.DEFAULT_METHOD_IDS
    assert m.normalize_method_ids(['cycle_rhythm','ac_range_filter','uniform_floyd'])==('ac_range_filter','uniform_floyd')


def test_base_menu_and_advanced_variants_form_exact_catalogue():
    basic={row['value'] for row in m.method_selector_options()}
    advanced={row['value'] for row in m.method_selector_options(advanced=True)}
    assert len(basic)==15 and len(advanced)==7
    assert basic.isdisjoint(advanced) and basic|advanced==set(m.METHODS_BY_ID)
    assert m.DEFAULT_METHOD_IDS==('uniform_fisher_yates',)
    assert m.METHOD_MYUNGRI_HETU in basic and m.METHOD_SELECTED_MEDIAN in basic
    assert m.METHOD_CALIBRATED_STRATIFIED in advanced
    assert '권장' not in m.METHODS_BY_ID[m.METHOD_PUBLIC_ENSEMBLE].description
