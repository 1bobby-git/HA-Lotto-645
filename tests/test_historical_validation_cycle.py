"""Cycle reset, full-outcome review import, concurrency and descriptive evidence."""
from __future__ import annotations
import asyncio
from copy import deepcopy
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for name, path in [('custom_components', ROOT/'custom_components'),
                   ('custom_components.lotto_645', ROOT/'custom_components/lotto_645')]:
    module = ModuleType(name); module.__path__ = [str(path)]
    sys.modules.setdefault(name, module)
s = importlib.import_module('custom_components.lotto_645.historical_validation_scores')


def result(match=3, target=100, version='1'):
    return {'target_round': target, 'generated_at': '2026-09-15T00:00:00Z', 'results': [
        {'method_id': 'a', 'sensor_name': '공식 A', 'generation_status': 'generated',
         'main_match_count': match, 'bonus_match': True, 'formula_version': version},
        {'method_id': 'b', 'sensor_name': '공식 B', 'generation_status': 'generated',
         'main_match_count': 0, 'formula_version': version},
        {'method_id': 'c', 'generation_status': 'unavailable', 'main_match_count': 6}]}


def cycle():
    return s.rotate(s._empty(), 1241)


@pytest.mark.parametrize('match,points', [(0,0),(1,0),(2,0),(3,1),(4,3),(5,10),(6,50)])
def test_all_outcomes_and_bonus_policy(match, points):
    old = cycle(); p = s.apply_result(old, result(match)); view = s.summary(p)
    assert old['total_runs'] == 0
    assert p['total_runs'] == 1 and p['methods']['a']['points'] == points
    assert p['methods']['b']['generated'] == 1 and p['methods']['b']['three_plus_hits'] == 0
    assert p['methods']['c']['unavailable'] == 1 and p['methods']['c']['points'] == 0
    assert view['unimported_runs'] == 1
    s._validate(p)


def test_reset_preserves_explicit_review_only():
    p = s.apply_result(cycle(), result())
    p = s.apply_import(p, s.revision(p))
    p = s.apply_result(p, result(6, 101))  # unimported, must not survive as review
    assert s.rotate(p, 1241) == p and s.rotate(p, 1240) == p
    reset = s.rotate(p, 1242)
    assert reset['total_runs'] == 0 and not reset['methods'] and not reset['recent']
    assert not reset['rounds'] and reset['last_result'] is None
    assert reset['cycle_id'] != p['cycle_id'] and reset['reset_at']
    assert reset['reviews']['a']['points'] == 1 and reset['review_runs'] == 1
    assert reset['imported_runs'] == 0 and not reset['imported_current']
    with pytest.raises(s.ScoreConflict): s.apply_import(reset, s.revision(p))
    assert s.rotate(reset, 1242) == reset


def test_import_is_revision_checked_full_delta_and_idempotent():
    p = s.apply_result(cycle(), result(3))
    rev = s.revision(p); p = s.apply_import(p, rev)
    assert s.apply_import(p, rev) == p
    assert p['reviews']['b']['attempts'] == 1 and p['reviews']['c']['unavailable'] == 1
    p = s.apply_result(p, result(4, 101))
    with pytest.raises(s.ScoreConflict): s.apply_import(p, rev)
    p = s.apply_import(p, s.revision(p))
    assert p['review_runs'] == 2 and p['reviews']['a']['points'] == 4
    assert p['reviews']['a']['generated'] == 2
    p = s.rotate(p, 1242); p = s.apply_result(p, result(5))
    p = s.apply_import(p, s.revision(p))
    assert p['reviews']['a']['points'] == 14 and len(p['reviews']['a']['first_rounds']) == 2
    assert p['last_import']['source'] == 'historical_validation'


def test_legacy_migration_does_not_invent_round_evidence():
    p = s.apply_result(cycle(), result())
    old = {k:deepcopy(p[k]) for k in ('version','total_runs','rounds','methods','recent')}
    for row in old['methods'].values():
        row.pop('first_rounds'); row.pop('formula_versions')
    migrated = s.rotate(s._validate(old), 1241)
    assert migrated['total_runs'] == 1 and migrated['methods']['a']['points'] == 1
    assert s.summary(migrated)['methods'][0]['interval_99'] is None
    assert migrated['cycle_round'] == 1241 and old['total_runs'] == 1
    assert s.rotate(migrated, 1242)['total_runs'] == 0


@pytest.mark.parametrize('bad', [True, -1, '1', None])
def test_corrupt_counter_never_accepted(bad):
    p = cycle(); p['total_runs'] = bad
    with pytest.raises(ValueError): s._validate(p)


def test_inconsistent_nested_data_and_duplicates_rejected():
    p = s.apply_result(cycle(), result())
    p['methods']['a']['points'] = 999
    with pytest.raises(ValueError): s._validate(p)
    p = cycle(); r=result(); r['results'].append(r['results'][0])
    with pytest.raises(ValueError): s.apply_result(p, r)
    assert p['total_runs'] == 0


def test_normalized_score_first_draw_only_and_version_warning():
    p = cycle()
    for _ in range(10): p = s.apply_result(p, result(3))
    row = s.summary(p)['methods'][0]
    assert row['points_per_100'] == 100 and row['unique_rounds'] == 1
    assert row['interval_99'] == s.wilson(1, 1)
    assert row['sample_notice'] == '표본 부족'
    p=s.apply_result(p,result(3,101,'2'));row=s.summary(p)['methods'][0]
    assert row['interval_99'] is None and '버전 혼합' in row['sample_notice']
    p=s.apply_result(p,{'target_round':102,'results':[result()['results'][0]]})
    assert not s.summary(p)['comparable_rounds']
    assert s.wilson(0,0) is None and s.wilson(0,100)[0] == 0 and s.wilson(100,100)[1] == 100
    assert s.BASELINE == pytest.approx(0.023834078569, abs=1e-10)


class MemoryStore:
    def __init__(self):
        self.disk=None; self.fail=False; self.after_save=None; self.saves=0
    async def async_load(self): return deepcopy(self.disk)
    async def async_save(self,p):
        if self.fail: raise OSError('disk full')
        await asyncio.sleep(0)
        self.disk=deepcopy(p);self.saves+=1
        if self.after_save: self.after_save()


def test_atomic_storage_restart_delta_and_save_failure(monkeypatch):
    async def run():
        store=MemoryStore();monkeypatch.setattr(s,'_store',lambda *_:store)
        hass=SimpleNamespace(data={})
        p=await s.async_access(hass,'one',1241,result=result())
        before=deepcopy(store.disk);store.fail=True
        board=await s.async_record(hass,'one',result(6),current_round=1241)
        assert board['storage_error'] and board['total_runs']==1 and store.disk==before
        with pytest.raises(OSError):await s.async_access(hass,'one',1241,import_revision=s.revision(p))
        assert not s.cached_reviews(hass,'one') and store.disk==before
        store.fail=False
        await s.async_access(hass,'one',1241,import_revision=s.revision(p))
        hass=SimpleNamespace(data={})
        recovered=await s.async_access(hass,'one',1241)
        assert recovered['last_result']['target_round']==100 and recovered['review_runs']==1
        assert s.cached_reviews(hass,'one')['a']['points']==1
        await s.async_access(hass,'one',1242)
        assert store.disk['total_runs']==0 and store.disk['reviews']['a']['points']==1
    asyncio.run(run())


def test_bad_disk_preserved_and_load_can_retry(monkeypatch):
    async def run():
        store=MemoryStore();store.disk={'version':1,'total_runs':'corrupt'}
        monkeypatch.setattr(s,'_store',lambda *_:store);hass=SimpleNamespace(data={})
        with pytest.raises(ValueError):await s.async_access(hass,'one',1241)
        assert store.saves==0 and store.disk['total_runs']=='corrupt'
        store.disk=None
        assert (await s.async_access(hass,'one',1241))['total_runs']==0
    asyncio.run(run())


def test_concurrent_append_import_and_entry_isolation(monkeypatch):
    async def run():
        stores={};monkeypatch.setattr(s,'_store',lambda h,k:stores.setdefault(k,MemoryStore()))
        h=SimpleNamespace(data={})
        await asyncio.gather(*(s.async_access(h,'one',1241,result=result()) for _ in range(8)))
        p=await s.async_access(h,'one',1241);rev=s.revision(p)
        await asyncio.gather(*(s.async_access(h,'one',1241,import_revision=rev) for _ in range(8)))
        p=await s.async_access(h,'one',1241)
        assert p['total_runs']==8 and p['review_runs']==8 and p['reviews']['a']['points']==8
        assert (await s.async_access(h,'two',1241))['total_runs']==0
    asyncio.run(run())


def test_publication_during_disk_write_rejects_stale_result_not_saved_import(monkeypatch):
    async def run():
        store=MemoryStore();monkeypatch.setattr(s,'_store',lambda *_:store)
        h=SimpleNamespace(data={});latest=[1241]
        p=await s.async_access(h,'one',1241)
        store.after_save=lambda:latest.__setitem__(0,1242)
        with pytest.raises(s.ScoreConflict):
            await s.async_access(h,'one',1241,result=result(),expected_cycle=p['cycle_id'],cycle_reader=lambda:latest[0])
        assert store.disk['total_runs']==0 and store.disk['cycle_round']==1242
        store.after_save=None;p=await s.async_access(h,'one',1242,result=result())
        store.after_save=lambda:latest.__setitem__(0,1243)
        p=await s.async_access(h,'one',1242,import_revision=s.revision(p),cycle_reader=lambda:latest[0])
        assert p['total_runs']==0 and p['reviews']['a']['points']==1 and p['cycle_round']==1243
    asyncio.run(run())


def test_only_complete_confirmed_draw_resets():
    models=importlib.import_module('custom_components.lotto_645.models')
    old=models.LottoDraw(1241,'2026-09-12',(1,2,3,4,5,6),7)
    new=models.LottoDraw(1242,'2026-09-19',(1,2,3,4,5,6),7)
    obj=SimpleNamespace(history=[old],_fast_result={'round':1242,'draw':new.to_storage()})
    for status in ('provisional','conflict','waiting'):
        obj._fast_result['status']=status;assert s.published_round(obj)==1241
    obj._fast_result['status']='cross_checked';assert s.published_round(obj)==1242
    obj._fast_result['draw']['numbers']=[1,1,1,1,1,1];assert s.published_round(obj)==1241
    obj.history.append(new);assert s.published_round(obj)==1242


def test_publication_listener_coalesces_without_network_and_unsubscribes(monkeypatch):
    lifecycle=importlib.import_module('custom_components.lotto_645.validation_lifecycle')
    async def run():
        store=MemoryStore();monkeypatch.setattr(s,'_store',lambda *_:store)
        callbacks=[];unload=[];tasks=[];removed=[]
        def listen(fn):
            callbacks.append(fn)
            return lambda:removed.append(True)
        def create(fn,*_):
            task=asyncio.create_task(fn);tasks.append(task);return task
        obj=SimpleNamespace(entry=SimpleNamespace(entry_id='one',async_on_unload=unload.append),
                            history=[SimpleNamespace(round=1241)],async_add_listener=listen)
        h=SimpleNamespace(data={},async_create_task=create)
        await lifecycle.async_setup_validation(h,obj)
        p=await s.async_access(h,'one',1241,result=result())
        await s.async_access(h,'one',1241,import_revision=s.revision(p))
        h.data['lotto_645_panel']={'validation_states':{'one':{'status':'completed','cycle_id':p['cycle_id']}}}
        obj.history.append(SimpleNamespace(round=1242))
        for _ in range(8):callbacks[0]()
        assert len(tasks)==1
        await tasks[0]
        assert store.disk['cycle_round']==1242 and store.disk['total_runs']==0
        assert store.disk['reviews']['a']['points']==1
        assert not h.data['lotto_645_panel']['validation_states']
        callbacks[0]();assert len(tasks)==1
        unload[0]();assert removed==[True]
    asyncio.run(run())
