"""Public generation API and installed package parity; no historical test runner."""
import ast
from dataclasses import asdict
import importlib
import json
from pathlib import Path
import random
import subprocess
import sys
import zipfile
from hashlib import sha256

import pytest
from test_analysis_engine import analysis, methods, models, _history, ROOT
api=importlib.import_module('custom_components.lotto_645.lotto_core.api')


def test_same_engine_object_and_same_generated_numbers():
    assert api.build_analysis is analysis.build_analysis
    ids=['uniform_fisher_yates','constraint_uniform','crowd_pattern_avoidance','selected_median_consensus','selected_vote_consensus']
    history=_history(30)
    options={'generation_rules': {'fixed':[7], 'odd':[2,4]}}
    a=api.generate(history,ids,target_round=31,generation_nonce=17,formula_options=options,rng=random.Random(52))
    b=analysis.build_analysis(history,ids,generation_nonce=17,formula_options=options,rng=random.Random(52))
    assert a==b
    assert len(a.recommendations)==5
    assert 7 in a.recommendation_by_method('constraint_uniform').numbers


@pytest.mark.parametrize('bad',[[],['missing'],['uniform_floyd','uniform_floyd'],['selected_vote_consensus']])
def test_invalid_method_contract_fails_closed(bad):
    with pytest.raises(ValueError):api.validate_method_ids(bad)


@pytest.mark.parametrize('target',[True,30,32,0])
def test_reject_misaligned_target_instead_of_slicing_it(target):
    with pytest.raises(ValueError):api.generate(_history(30),target_round=target)


def test_future_included_and_malformed_history_rejected():
    with pytest.raises(ValueError):api.generate(_history(31),target_round=31)
    with pytest.raises(ValueError):api.generate(list(reversed(_history(30))))
    rows=[r.to_storage() for r in _history(30)]
    rows[0]['round']=True
    with pytest.raises(ValueError):api.generate(rows)


def test_catalog_is_the_live_catalog_not_a_copy():
    description=api.describe()
    assert description['api_version']==1
    assert len(description['methods'])==22
    assert [r['method_id'] for r in description['methods']]==list(methods.METHODS_BY_ID)
    assert description['capabilities']==['generate','catalog','progress']


def test_stream_copies_match_final_records_and_cannot_mutate_them():
    snapshots=[]
    def record(row):
        snapshots.append(row['numbers'][:]);row['numbers'].clear();row['details'].clear()
    result=api.generate(_history(30),['uniform_fisher_yates','uniform_floyd','selected_vote_consensus'],
                        rng=random.Random(4),recommendation_callback=record)
    assert snapshots==[list(r.numbers) for r in result.recommendations]
    assert all(r.details for r in result.recommendations)
    def cancel(event):raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):api.generate(_history(30),progress_callback=cancel)


def test_core_has_no_ha_or_evaluation_runtime_dependencies():
    root=ROOT/'custom_components/lotto_645/lotto_core'
    for path in root.glob('*.py'):
        tree=ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert not (node.module or '').startswith(('homeassistant','requests','aiohttp','sqlite3'))
                assert node.level<=1
            elif isinstance(node,ast.Import):
                assert all(not n.name.startswith(('homeassistant','requests','aiohttp','sqlite3')) for n in node.names)


def test_exported_wheel_installs_and_executes_identical_core(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('exporter',ROOT/'scripts/build_core.py')
    exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
    dist=tmp_path/'dist';manifest=exporter.build(dist,'a'*40)
    wheel=next(dist.glob('*.whl'));installed=tmp_path/'installed'
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--target',str(installed),str(wheel)],check=True,capture_output=True)
    for name,digest in manifest['files'].items():
        assert sha256((installed/name).read_bytes()).hexdigest()==digest
    request=tmp_path/'input.json';request.write_text(json.dumps([r.to_storage() for r in _history(30)]))
    code='''import json,random,sys
sys.path.insert(0,sys.argv[1])
import lotto_core
assert not any(k.startswith("homeassistant") for k in sys.modules)
result=lotto_core.generate(json.load(open(sys.argv[2])),["uniform_fisher_yates","constraint_uniform"],rng=random.Random(12),generation_nonce=8)
print(json.dumps([list(r.numbers) for r in result.recommendations]))
'''
    output=subprocess.check_output([sys.executable,'-c',code,str(installed),str(request)],cwd=tmp_path,text=True)
    local=api.generate(_history(30),['uniform_fisher_yates','constraint_uniform'],rng=random.Random(12),generation_nonce=8)
    assert json.loads(output)==[list(r.numbers) for r in local.recommendations]
    source=next(dist.glob('*.zip'))
    with zipfile.ZipFile(source) as z:
        assert 'core-manifest.json' in z.namelist()
        assert not any('custom_components/' in n or 'historical_validation' in n for n in z.namelist())
    assert len(manifest['files'])>=15
