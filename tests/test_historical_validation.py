"""Holdout isolation, fresh regeneration, and absolutely no live-state side effects."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
import importlib
from pathlib import Path
import random
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
for name, path in [('custom_components', ROOT/'custom_components'),
                   ('custom_components.lotto_645', ROOT/'custom_components/lotto_645')]:
    module = ModuleType(name); module.__path__ = [str(path)]
    sys.modules.setdefault(name, module)
v = importlib.import_module('custom_components.lotto_645.historical_validation')
rt = importlib.import_module('custom_components.lotto_645.historical_validation_runtime')
models = importlib.import_module('custom_components.lotto_645.models')
methods = importlib.import_module('custom_components.lotto_645.methods')


def history(count=65):
    rng = random.Random(13645)
    return [models.LottoDraw(i, (date(2002,12,7)+timedelta(weeks=i-1)).isoformat(),
                            tuple(sorted(values[:6])), values[6])
            for i in range(1,count+1) for values in [rng.sample(range(1,46),7)]]


def numbers(result):
    return [(r['method_id'],r['recommended_numbers']) for r in result['results']]


@pytest.mark.parametrize('ids', [
    ('uniform_fisher_yates','uniform_floyd','uniform_rejection','uniform_sequential',
     'calibrated_stratified','uniform_combination_rank','bayesian_shrinkage','ac_range_filter',
     'selected_median_consensus','home_assistant_ai'),
    ('weighted_frequency','hot_numbers','public_ensemble','selected_median_consensus'),
])
def test_target_and_future_results_cannot_influence_generated_numbers(ids):
    rows=history();before=deepcopy(rows)
    baseline=v.run_historical_validation(rows,61,ids,rng=random.Random(17))
    changed=[r if r.round<61 else replace(r,numbers=(1,2,3,4,5,6),bonus=7,
                                        first_prize_amount=999999999) for r in rows]
    altered=v.run_historical_validation(changed,61,ids,rng=random.Random(17))
    assert numbers(baseline)==numbers(altered)
    assert baseline['training_sha256']==altered['training_sha256']
    assert baseline['draw']['numbers']!=altered['draw']['numbers']
    assert rows==before
    assert baseline['counts_toward_reviews'] is False
    assert baseline['persisted'] is False and baseline['ai_called'] is False
    assert baseline['based_on_round']==60 and baseline['training_draw_count']==60
    assert baseline['target_and_future_used_for_generation'] is False


def test_training_change_changes_prefix_fingerprint():
    rows=history();a=v.run_historical_validation(rows,61,('uniform_floyd',))
    rows[20]=replace(rows[20],numbers=(1,2,3,4,5,6),bonus=7)
    b=v.run_historical_validation(rows,61,('uniform_floyd',))
    assert a['training_sha256']!=b['training_sha256']


def test_exact_target_jackpot_is_not_excluded_as_a_known_winning_combination(monkeypatch):
    rows=history();target=rows[60];captured={}
    def build(prefix, ids, nonce, profile, **kwargs):
        captured.update(prefix=prefix, ids=ids, nonce=nonce, options=kwargs)
        # Force the holdout winning ticket. Filtering with full history would
        # reject this; this test must be allowed to return a simulated 1st prize.
        rec=models.Recommendation(1,ids[0],'test','test',target.numbers,'',None,{})
        return models.AnalysisResult(61,60,(rec,),{})
    monkeypatch.setattr(v,'build_analysis',build)
    result=v.run_historical_validation(rows,61,('uniform_floyd',))
    assert result['results'][0]['prize_rank']==1
    assert result['winning_game_count']==1
    assert len(captured['prefix'])==60
    assert 'restored_tickets' not in captured['options']
    assert captured['options']['excluded_combinations']==()
    assert captured['nonce']>0


@pytest.mark.parametrize('target,code', [(1,'invalid_round'),(30,'invalid_round'),(True,'invalid_round'),
                                        (31.0,'invalid_round'),(66,'round_unavailable')])
def test_invalid_or_unpublished_targets_are_rejected(target,code):
    with pytest.raises(v.HistoricalValidationError) as err:
        v.run_historical_validation(history(),target,('uniform_floyd',))
    assert err.value.code==code


def test_minimum_valid_round_and_test_only_rng_injection():
    rows=history();ids=('uniform_floyd',)
    a=v.run_historical_validation(rows,31,ids,rng=random.Random(5))
    b=v.run_historical_validation(rows,31,ids,rng=random.Random(5))
    c=v.run_historical_validation(rows,31,ids,rng=random.Random(6))
    assert a['training_last_round']==30 and numbers(a)==numbers(b)
    assert numbers(a)!=numbers(c)
    assert a['rng']=='injected_test_rng' and 'seed' not in a
    assert a['generated_at']>a['draw']['draw_date']


def test_fresh_rng_and_previous_simulation_exclusion():
    rows=history();ids=('uniform_fisher_yates','ac_range_filter','selected_median_consensus','home_assistant_ai')
    prior=()
    for _ in range(5):
        result=v.run_historical_validation(rows,61,ids,previous_tickets=prior)
        current=tuple(tuple(r['recommended_numbers']) for r in result['results'] if r['generation_status']=='generated')
        assert set(current).isdisjoint(prior)
        assert len(current)==len(set(current))
        assert result['rng']=='system_csprng' and 'seed' not in result
        prior=current


def test_previous_exclusion_changes_even_identical_test_rng():
    rows=history();ids=('weighted_frequency', 'uniform_floyd')
    a=v.run_historical_validation(rows,61,ids,rng=random.Random(15))
    prior=tuple(tuple(r['recommended_numbers']) for r in a['results'])
    b=v.run_historical_validation(rows,61,ids,previous_tickets=prior,rng=random.Random(15))
    assert set(tuple(r['recommended_numbers']) for r in b['results']).isdisjoint(prior)


@pytest.mark.parametrize('bad', [(1,2,3), (1,1,2,3,4,5), (True,2,3,4,5,6)])
def test_malformed_prior_simulations_fail_closed(bad):
    with pytest.raises(v.HistoricalValidationError):
        v.run_historical_validation(history(),61,('uniform_floyd',),previous_tickets=(bad,))


@pytest.mark.parametrize('ids', [(),('unknown',),('uniform_floyd','uniform_floyd'),
                               ('selected_median_consensus','home_assistant_ai','uniform_floyd')])
def test_no_silent_formula_substitutions(ids):
    with pytest.raises(v.HistoricalValidationError):
        v.run_historical_validation(history(),61,ids)


@pytest.mark.parametrize('transform', [lambda rows:rows[1:],lambda rows:rows[:20]+rows[21:],
                                      lambda rows:rows+[rows[20]]])
def test_incomplete_or_duplicate_training_is_rejected(transform):
    with pytest.raises(v.HistoricalValidationError) as err:
        v.run_historical_validation(transform(history()),61,('uniform_floyd',))
    assert err.value.code=='history_incomplete'


def test_profile_required_without_disclosing_profile():
    with pytest.raises(v.HistoricalValidationError) as err:
        v.run_historical_validation(history(),61,(methods.METHOD_MYUNGRI_HETU,))
    assert err.value.code=='profile_required'


def test_ai_number_engine_only_and_no_extra_personal_output():
    result=v.run_historical_validation(history(),61,('home_assistant_ai',))
    row=result['results'][0]
    assert row['base_formula_id']=='calibrated_stratified'
    assert row['ai_called'] is False
    assert 'reason' not in row and 'details' not in row


def test_unavailable_consensus_is_not_scored_as_a_loss(monkeypatch):
    def build(prefix, ids, nonce, profile, **kwargs):
        return models.AnalysisResult(61,60,tuple(models.Recommendation(
            i,key,key,'test',(1,3,5,7,9,11),'',None,{})
            for i,key in enumerate(ids) if key!=methods.METHOD_SELECTED_MEDIAN),{})
    monkeypatch.setattr(v,'build_analysis',build)
    result=v.run_historical_validation(history(),61,('uniform_floyd','uniform_fisher_yates',methods.METHOD_SELECTED_MEDIAN))
    assert result['checked_game_count']==2 and result['unavailable_game_count']==1
    assert result['results'][-1]['status']=='판정 불가'
    assert result['results'][-1]['recommended_numbers']==[]


def test_runtime_calls_no_live_write_or_refresh_and_snapshots_inputs():
    async def run():
        loop=asyncio.get_running_loop();calls=[]
        obj=SimpleNamespace(entry=SimpleNamespace(entry_id='one'),history=history(),saju_profile_ready=False,
            _local_generation_nonce=941,_sampling_cache={'sentinel':[1,2]},_prediction_snapshot={'unchanged':True},
            _draw_evaluation={'unchanged':True},review_book={'scores':[80]},data={'live':[7,8]},
            async_request_refresh=Mock(),async_update_listeners=Mock(),_save_storage=Mock())
        before=deepcopy({k:val for k,val in vars(obj).items() if not isinstance(val,Mock)})
        def executor(fn):
            calls.append(fn);return loop.run_in_executor(None,fn)
        hass=SimpleNamespace(data={},async_add_executor_job=executor)
        result=await rt.async_validate_history(hass,obj,61,('uniform_floyd',))
        await asyncio.sleep(0)
        assert result['based_on_round']==60 and not hass.data[rt.KEY]
        assert before=={k:val for k,val in vars(obj).items() if not isinstance(val,Mock)}
        for name in ['async_request_refresh','async_update_listeners','_save_storage']:
            getattr(obj,name).assert_not_called()
        assert len(calls)==1
    asyncio.run(run())


@pytest.mark.parametrize('cancel', [True,False])
def test_cancel_or_timeout_keeps_single_worker_lease(monkeypatch,cancel):
    async def run():
        loop=asyncio.get_running_loop();worker=loop.create_future()
        executor=Mock(return_value=worker);hass=SimpleNamespace(data={},async_add_executor_job=executor)
        obj=SimpleNamespace(entry=SimpleNamespace(entry_id='one'),history=history(),saju_profile_ready=False)
        if not cancel:monkeypatch.setattr(rt,'TIMEOUT_SECONDS',.001)
        task=asyncio.create_task(rt.async_validate_history(hass,obj,61,('uniform_floyd',)))
        await asyncio.sleep(0)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
        else:
            with pytest.raises(v.HistoricalValidationError) as err:await task
            assert err.value.code=='validation_timeout'
        assert not worker.cancelled() and hass.data[rt.KEY]['one'] is worker
        with pytest.raises(v.HistoricalValidationError) as err:
            await rt.async_validate_history(hass,obj,61,('uniform_floyd',))
        assert err.value.code=='validation_busy'
        assert executor.call_count==1
        worker.set_result({'test':True});await asyncio.sleep(0)
        assert not hass.data[rt.KEY]
    asyncio.run(run())


def test_ui_and_websocket_separation_is_explicit():
    root=ROOT/'custom_components/lotto_645'
    endpoint=(root/'ticket_panel.py').read_text()
    handler=endpoint.split('async def historical_validate(')[1].split('\n\n@websocket_api.websocket_command')[0]
    assert '_view(' not in handler
    assert 'async_validate_history(' in handler
    js=(root/'www/lotto-panel-validation.js').read_text()
    assert "request('historical_validate'" in js
    generation = js.split('async run(){')[1].split('  render(data)')[0]
    assert "node('predictions')" not in js
    assert 'updateResults(' not in generation and 'historical_validation_import' not in generation
    assert "request('historical_validation_import'" in js and 'window.confirm(' in js
    assert 'sequence!==this.sequence' in js.replace(' ', '')
    assert 'validation-seed' not in js and 'data.seed' not in js
    assert "vol.Optional('seed'" not in endpoint
    assert "localStorage" not in js and "setInterval" not in js


def test_runtime_two_clicks_exclude_previous_and_keep_one_bounded_batch():
    async def run():
        loop=asyncio.get_running_loop()
        hass=SimpleNamespace(data={},async_add_executor_job=lambda fn:loop.run_in_executor(None,fn))
        obj=SimpleNamespace(entry=SimpleNamespace(entry_id='one'),history=history(),saju_profile_ready=False)
        a=await rt.async_validate_history(hass,obj,61,('uniform_floyd',))
        b=await rt.async_validate_history(hass,obj,61,('uniform_floyd',))
        assert numbers(a)!=numbers(b) and b['previous_simulation_excluded']
        c=await rt.async_validate_history(hass,obj,62,('uniform_floyd',))
        assert not c['previous_simulation_excluded']
        assert len(hass.data[rt.LAST_KEY])==1
        replacement=SimpleNamespace(entry=obj.entry,history=obj.history,saju_profile_ready=False)
        d=await rt.async_validate_history(hass,replacement,62,('uniform_floyd',))
        assert not d['previous_simulation_excluded']
    asyncio.run(run())
