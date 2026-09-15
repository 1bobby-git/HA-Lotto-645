"""Exact winning numbers, cycle-global run indices and honest legacy history."""
from copy import deepcopy
import asyncio
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
h = importlib.import_module('custom_components.lotto_645.validation_hit_history')
m = importlib.import_module('custom_components.lotto_645.models')
evaluate_ticket = importlib.import_module('custom_components.lotto_645.result_evaluator').evaluate_ticket


def result(matches=3, bonus=False, method='a', target=1200):
    draw = m.LottoDraw(target,'2025-11-29',(1,2,3,4,5,6),7)
    numbers = list(draw.numbers[:matches]) + ([7] if bonus else [])
    numbers += [10,11,12,13,14,15][:6-len(numbers)]
    row = {'method_id':method,'sensor_name':method,'generation_status':'generated',
           'recommended_numbers':numbers,**evaluate_ticket(tuple(numbers),draw)}
    return {'target_round':target,'generated_at':'2026-09-15T01:00:00Z','results':[row],'draw':draw.to_storage()}


def cycle(): return s.rotate(s._empty(),1241)


@pytest.mark.parametrize('matches,bonus,rank', [(3,False,5),(3,True,5),(4,False,4),(4,True,4),(5,False,3),(5,True,2),(6,False,1)])
def test_exact_event_outcomes_and_persistent_roundtrip(matches,bonus,rank):
    data=result(matches,bonus);data['birth_profile']='must never enter hit events'
    p=s.apply_result(cycle(),data)
    event=p['methods']['a']['hit_history'][0]
    assert event['run']==1 and event['round']==1200 and event['prize_rank']==rank
    assert event['matched_main_numbers']==list(range(1,matches+1))
    assert event['bonus_match'] is bonus and event['matched_bonus_number']==(7 if bonus else None)
    assert event['recommended_numbers']==data['results'][0]['recommended_numbers']
    assert event['winning_numbers']==list(range(1,7))
    assert event['details_available'] and 'birth_profile' not in event
    assert s._validate(deepcopy(p))==p
    assert s.summary(p)['methods'][0]['hit_history_omitted']==0


@pytest.mark.parametrize('matches,bonus',[(0,False),(0,True),(1,False),(2,True)])
def test_below_three_main_matches_never_creates_winning_history(matches,bonus):
    p=s.apply_result(cycle(),result(matches,bonus))
    assert p['methods']['a']['hit_history']==[]
    assert s.revision(p)==s.revision(s._validate(p))  # restart must not break the consent revision


def test_run_number_is_global_not_method_attempt_or_hit_count():
    p=cycle()
    for method,matches in [('b',3),('a',0),('b',4),('a',3),('a',4)]:
        p=s.apply_result(p,result(matches,method=method))
    assert p['total_runs']==5 and p['methods']['a']['attempts']==3
    assert [e['run'] for e in p['methods']['a']['hit_history']]==[4,5]
    assert [e['run'] for e in p['methods']['b']['hit_history']]==[1,3]


def test_more_than_fifty_runs_keeps_exact_hits_and_bounds_storage():
    p=cycle()
    for i in range(h.MAX_HIT_HISTORY+3): p=s.apply_result(p,result(3,target=100+i))
    events=p['methods']['a']['hit_history']
    assert len(events)==100 and events[0]['run']==4 and events[-1]['run']==103
    assert p['total_runs']==103 and len(p['recent'])==50
    assert p['methods']['a']['points']==103
    assert s.summary(p)['methods'][0]['hit_history_omitted']==3
    assert s._validate(p)==p


def test_legacy_metadata_and_only_exact_latest_numbers_recovered():
    p=s.apply_result(cycle(),result(3))
    p=s.apply_result(p,result(5,True))
    del p['methods']['a']['hit_history']  # exact v1.17 shape
    original=deepcopy(p)
    migrated=s._validate(p)
    old,last=migrated['methods']['a']['hit_history']
    assert old['run']==1 and old['main_match_count']==3 and not old['details_available']
    assert 'recommended_numbers' not in old and 'prize_rank' not in old
    assert last['run']==2 and last['details_available'] and last['prize_rank']==2
    assert last['matched_main_numbers']==[1,2,3,4,5]
    assert original==p and migrated['methods']['a']['points']==11
    assert s._validate(migrated)==migrated


def test_old_hit_without_latest_ticket_not_fabricated_on_next_run():
    p=s.apply_result(cycle(),result(3))
    p=s.apply_result(p,result(0))
    del p['methods']['a']['hit_history']
    p=s.apply_result(p,result(4))
    events=p['methods']['a']['hit_history']
    assert [e['run'] for e in events]==[1,3]
    assert events[0]['details_available'] is False and events[1]['details_available'] is True
    assert 'recommended_numbers' not in events[0]


def test_legacy_older_than_recent_window_stays_in_aggregate():
    p=cycle()
    for i in range(60): p=s.apply_result(p,result(3))
    del p['methods']['a']['hit_history']
    p['last_result']=None
    migrated=s._validate(p)
    board=s.summary(migrated)['methods'][0]
    assert board['points']==60 and len(board['hit_history'])==50
    assert board['hit_history'][0]['run']==11 and board['hit_history_omitted']==10
    assert all(not e['details_available'] for e in board['hit_history'])


def test_migration_preserves_existing_review_deltas_and_reset():
    p=s.apply_result(cycle(),result(3))
    p=s.apply_import(p,s.revision(p))
    oldreview=deepcopy(p['reviews'])
    del p['methods']['a']['hit_history']
    p=s._validate(p)
    assert s.apply_import(p,s.revision(p))['reviews']==oldreview
    p=s.apply_result(p,result(4));p=s.apply_import(p,s.revision(p))
    assert p['reviews']['a']['points']==4 and p['review_runs']==2
    p=s.rotate(p,1242)
    assert p['total_runs']==0 and not p['methods'] and p['reviews']['a']['points']==4
    p=s.apply_result(p,result(5))
    assert p['methods']['a']['hit_history'][0]['run']==1


@pytest.mark.parametrize('change',[
    lambda r:r['results'][0].__setitem__('matched_main_numbers',[1,2,9]),
    lambda r:r['results'][0].__setitem__('prize_rank',1),
    lambda r:r['results'][0].__setitem__('recommended_numbers',[1,1,3,10,11,12]),
    lambda r:r['draw'].__setitem__('round',1201),
    lambda r:r['draw'].__setitem__('bonus',True),
])
def test_inconsistent_number_evidence_never_added(change):
    p=cycle();data=result();change(data)
    with pytest.raises(ValueError): s.apply_result(p,data)
    assert not p['methods'] and p['total_runs']==0


@pytest.mark.parametrize('change',[
    lambda e:e.__setitem__('run',True),
    lambda e:e.__setitem__('run',2),
    lambda e:e.__setitem__('matched_main_numbers',[1,2,8]),
    lambda e:e.__setitem__('details_available',False),
    lambda e:e.__setitem__('main_match_count',2),
])
def test_corrupt_persisted_history_is_not_overwritten(change):
    p=s.apply_result(cycle(),result());change(p['methods']['a']['hit_history'][0])
    with pytest.raises(ValueError): s._validate(p)


def test_storage_failure_and_restart_keep_hit_evidence_atomic(monkeypatch):
    class Store:
        disk=None;fail=False
        async def async_load(self): return deepcopy(self.disk)
        async def async_save(self,p):
            if self.fail:raise OSError('disk full')
            self.disk=deepcopy(p)
    async def run():
        store=Store();monkeypatch.setattr(s,'_store',lambda *_:store)
        hass=SimpleNamespace(data={})
        p=await s.async_access(hass,'one',1241,result=result())
        before=deepcopy(store.disk);store.fail=True
        failed=await s.async_record(hass,'one',result(4),current_round=1241)
        assert failed['storage_error'] and failed['total_runs']==1 and store.disk==before
        store.fail=False
        restored=await s.async_access(SimpleNamespace(data={}),'one',1241)
        assert restored==p and restored['methods']['a']['hit_history'][0]['matched_main_numbers']==[1,2,3]
    asyncio.run(run())
