"""Active families, reversible selection migration and private-data boundaries."""
from __future__ import annotations
import ast
import asyncio
import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components/lotto_645'
spec = importlib.util.spec_from_file_location('consolidation_catalog', COMPONENT / 'methods.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def test_active_catalog_and_legacy_registry_are_different():
    assert len(m.ACTIVE_METHOD_IDS) == 12
    assert len(m.METHODS_BY_ID) == 24
    assert m.DEFAULT_METHOD_IDS == (m.METHOD_UNIFORM_FISHER_YATES,)
    assert set(m.ACTIVE_METHOD_IDS).isdisjoint(m.RETIRED_METHOD_IDS)
    assert set(m.ACTIVE_METHOD_IDS).isdisjoint(m.CONSOLIDATED_METHOD_IDS)
    assert {o['value'] for o in m.method_selector_options()} == set(m.ACTIVE_METHOD_IDS)
    assert {v['method_id'] for v in m.method_catalog()} == set(m.ACTIVE_METHOD_IDS)
    assert len(m.method_catalog(include_legacy=True)) == 24
    assert m.ACTIVE_METHOD_IDS[-1] == m.METHOD_SELECTED_MEDIAN


@pytest.mark.parametrize('key', m.UNIFORM_ENGINES)
def test_old_uniform_selection_preserves_engine_but_not_extra_games(key):
    after = m.consolidate_options({'selected_methods': [key]})
    assert after['selected_methods'] == ['uniform_fisher_yates']
    assert after['uniform_engine'] == key
    resolved = m.resolve_method_definition('uniform_fisher_yates', after)
    assert resolved.method_id == 'uniform_fisher_yates'
    assert resolved.sampling == key


@pytest.mark.parametrize('key', m.FREQUENCY_PRESETS)
def test_old_frequency_selection_preserves_exact_scoring_preset(key):
    after = m.consolidate_options({'selected_methods': [key]})
    assert after['selected_methods'] == ['weighted_frequency']
    assert after['frequency_preset'] == key
    resolved = m.resolve_method_definition('weighted_frequency', after)
    assert resolved.method_id == 'weighted_frequency'
    assert resolved.weights == m.METHODS_BY_ID[key].weights
    assert resolved.pair_weight == m.METHODS_BY_ID[key].pair_weight
    assert resolved.balance_weight == m.METHODS_BY_ID[key].balance_weight


@pytest.mark.parametrize('key', sorted(m.RETIRED_METHOD_IDS))
def test_retired_only_falls_back_to_one_game_without_enabling_ai_or_saju(key):
    after = m.consolidate_options({'selected_methods': [key]})
    assert after['selected_methods'] == ['uniform_fisher_yates']
    assert after[m.CATALOG_MIGRATION_KEY]['fallback_uniform']
    assert 'enable_ai_recommendation' not in after


def test_all_formulas_collapse_to_12_preserving_first_variant_order():
    source = {'selected_methods': ['uniform_floyd', 'hot_numbers', *m.METHODS_BY_ID]}
    after = m.consolidate_options(source)
    assert len(after['selected_methods']) == 12
    assert after['uniform_engine'] == 'uniform_floyd'
    assert after['frequency_preset'] == 'hot_numbers'
    assert m.consolidate_options(after) == after
    assert source['selected_methods'][:2] == ['uniform_floyd','hot_numbers']


def test_consensus_is_not_rescued_with_unrequested_games():
    after = m.consolidate_options({'selected_methods':['uniform_floyd','uniform_rejection','selected_median_consensus']})
    assert after['selected_methods'] == ['uniform_fisher_yates']
    assert after[m.CATALOG_MIGRATION_KEY]['consensus_disabled']
    valid = m.consolidate_options({'selected_methods':['uniform_floyd','ac_range_filter','selected_median_consensus']})
    assert valid['selected_methods'] == ['uniform_fisher_yates','ac_range_filter','selected_median_consensus']
    assert not valid[m.CATALOG_MIGRATION_KEY]['consensus_disabled']


def test_explicit_preset_wins_and_private_values_are_untouched():
    before = {'selected_methods':['uniform_floyd','recency_decay'],
              'uniform_engine':'calibrated_stratified', 'frequency_preset':'hot_numbers',
              'saju_birth_date':'1990-01-01', 'saju_birth_time':'12:34',
              'saju_birth_place':'PRIVATE', 'ai_task_entity_id':'ai_task.private',
              'enable_ai_recommendation':False, 'ai_auto_generate':False,
              'unknown_extension':{'nested':[1,2,3]}}
    original = copy.deepcopy(before)
    after = m.consolidate_options(before)
    assert before == original
    for key in before.keys() - {'selected_methods'}:
        assert after[key] == before[key]
    audit = repr(after[m.CATALOG_MIGRATION_KEY])
    assert 'PRIVATE' not in audit and '1990-01-01' not in audit and 'ai_task.private' not in audit
    assert m.consolidate_options(after) == after


@pytest.mark.parametrize('value', [None, '', {}, [], [True, 3, {}, 'missing']])
def test_invalid_legacy_selection_has_bounded_safe_fallback(value):
    assert m.active_method_ids({'selected_methods': value}) == ('uniform_fisher_yates',)


def test_cache_identity_varies_by_preset_not_personal_data():
    # Compile only the pure key function to avoid importing HA during this test.
    tree = ast.parse((COMPONENT/'formula_cache.py').read_text())
    fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='cache_key')
    import hashlib, json
    ns = {'sha256':hashlib.sha256, 'json':json, 'FORMULA_VERSION':1, 'formula_settings':m.formula_settings}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'cache_key','exec'),ns)
    key=ns['cache_key']; history=[SimpleNamespace(round=1,numbers=(1,2,3,4,5,6),bonus=7)]
    a=key(history,['uniform_fisher_yates'],0,{})
    assert a==key(history,['uniform_fisher_yates'],0,{'saju_birth_place':'PRIVATE'})
    assert a!=key(history,['uniform_fisher_yates'],0,{'uniform_engine':'uniform_floyd'})
    assert a!=key(history,['uniform_fisher_yates'],0,{'frequency_preset':'hot_numbers'})


def test_config_entry_migration_changes_only_options_and_minor_version():
    tree=ast.parse((COMPONENT/'__init__.py').read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='async_migrate_entry')
    ns={'consolidate_options':m.consolidate_options, 'HomeAssistant':object,'ConfigEntry':object}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'migration','exec'),ns)
    calls=[]
    def update(entry, **kw):
        calls.append(kw)
        for key,value in kw.items():setattr(entry,key,value)
    hass=SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=update))
    data={'private':'untouched'}
    entry=SimpleNamespace(version=2,minor_version=1,entry_id='same',data=data,
                          options={'selected_methods':['hot_numbers'],'saju_birth_place':'private'})
    assert asyncio.run(ns['async_migrate_entry'](hass,entry))
    assert entry.version==2 and entry.minor_version==2 and entry.data is data and entry.entry_id=='same'
    assert set(calls[0])=={'version','minor_version','options'}
    assert entry.options['selected_methods']==['weighted_frequency']
    assert asyncio.run(ns['async_migrate_entry'](hass,entry)) and len(calls)==1
    entry.version=3
    assert not asyncio.run(ns['async_migrate_entry'](hass,entry)) and len(calls)==1
