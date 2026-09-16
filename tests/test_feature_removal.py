"""Prevent removed feature implementations from returning to shipped sources."""
import ast
import importlib
from pathlib import Path

from test_analysis_engine import ROOT, methods
migration=importlib.import_module('custom_components.lotto_645.migration')
COMPONENT=ROOT/'custom_components/lotto_645'


def test_removed_modules_and_endpoints_are_absent():
    for name in migration._REMOVED_MODULES:
        assert not (COMPONENT/(name+'.py')).exists()
    for name in migration._REMOVED_SCRIPTS:
        assert not (COMPONENT/'www'/name).exists()
    assert not set(migration._REMOVED_IDS)&set(methods.METHODS_BY_ID)
    tree=ast.parse((COMPONENT/'ticket_panel.py').read_text(encoding="utf-8"))
    defs={n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert 'subscribe_updates' in defs
    assert not any('historical' in name or 'portfolio' in name for name in defs)
    source=(COMPONENT/'www/lotto-panel-view.js').read_text(encoding="utf-8")
    assert 'tab-validation' not in source and 'current-recommendations' in source
    for name in ('home','wallet','review'):
        assert f'id="tab-{name}"' in source and f'aria-controls="screen-{name}"' in source
    assert not (ROOT/'scripts/audit_formulas.py').exists()


def test_option_cleanup_preserves_settings_and_does_not_mutate_input():
    raw={'selected_methods':['personal_lucky','uniform_floyd'],'advanced_methods':['portfolio_triplet_coverage'],
         'lucky_keyword':'private','lucky_theme':'dream','generation_rules':{'fixed':[7]},'saju_birth_date':'1990-01-01'}
    clean=migration.clean_options(raw)
    assert clean['selected_methods']==['uniform_floyd'] and clean['advanced_methods']==[]
    assert 'lucky_keyword' not in clean and 'lucky_theme' not in clean
    assert clean['generation_rules']==raw['generation_rules'] and clean['saju_birth_date']==raw['saju_birth_date']
    assert raw['lucky_keyword']=='private'
    assert migration.clean_options({'selected_methods':['personal_lucky']})['selected_methods']==list(methods.DEFAULT_METHOD_IDS)


def test_cleanup_removes_only_allowlisted_files_and_preserves_user_records(tmp_path):
    (tmp_path/'__pycache__').mkdir()
    (tmp_path/'www').mkdir()
    for name in migration._REMOVED_MODULES:
        (tmp_path/(name+'.py')).write_text('obsolete')
        (tmp_path/'__pycache__'/(name+'.cpython-313.pyc')).write_bytes(b'old')
    for name in ['purchased_tickets.py','review.py','user-records.json']:(tmp_path/name).write_text('preserve')
    migration.cleanup_files(tmp_path)
    for name in migration._REMOVED_MODULES:assert not (tmp_path/(name+'.py')).exists()
    for name in ['purchased_tickets.py','review.py','user-records.json']:assert (tmp_path/name).read_text(encoding="utf-8")=='preserve'
