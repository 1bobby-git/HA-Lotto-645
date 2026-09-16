"""Independent rule, conditional-cover, privacy, cache and prefix regression checks."""
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
import importlib
import json
import random

import pytest

from test_analysis_engine import methods, models, analysis, _history
from test_consensus import row, payload, sample

rules = importlib.import_module('custom_components.lotto_645.constraints')
portfolio = importlib.import_module('custom_components.lotto_645.portfolio')
lucky = importlib.import_module('custom_components.lotto_645.personal_lucky')
vote = importlib.import_module('custom_components.lotto_645.voting_consensus')
consensus = importlib.import_module('custom_components.lotto_645.consensus')
cache = importlib.import_module('custom_components.lotto_645.formula_cache')
CID, LID, VID = 'constraint_uniform', 'personal_lucky', 'selected_vote_consensus'
A, B = 'uniform_fisher_yates', 'uniform_floyd'


@pytest.mark.parametrize('data,code', [
    ({'fixed':[7], 'excluded':[7]},'conflicting_rules'),
    ({'fixed':[True]},'invalid_rules'), ({'fixed':[1,1]},'invalid_rules'),
    ({'fixed':[0]},'invalid_rules'), ({'fixed':[46]},'invalid_rules'),
    ({'fixed':list(range(1,8))},'invalid_rules'),
    ({'excluded':list(range(1,41))},'infeasible_rules'),
    ({'total':'200-100'},'invalid_rules'), ({'odd':[4,3]},'invalid_rules'),
    ({'unknown':1},'invalid_rules'), ({'ac_min':11},'invalid_rules'),
    ({'max_run':0},'invalid_rules'), ({'fixed':[1,3,5,7], 'odd':[0,3]},'infeasible_rules'),
    ({'fixed':[40,41,42,43,44,45], 'total':[21,100]},'infeasible_rules'),
])
def test_invalid_and_proven_infeasible_rules(data, code):
    with pytest.raises(rules.ConstraintError) as e:
        rules.Rules.parse(data)
    assert e.value.code == code


def test_range_parsing_and_arithmetic_edge_cases():
    assert rules.bounds(' 2 ~ 4 ',0,6) == (2,4)
    assert rules.bounds('3',0,6) == (3,3)
    assert 1 not in rules.PRIMES and 2 in rules.PRIMES
    assert rules.neighbor_set((1,2,44,45)) == {3,43}
    bad = rules.violations((1,2,3,11,21,31),rules.Rules(max_run=2,max_same_ending=3),())
    assert '최대 연속 길이 초과' in bad and '같은 끝수 개수 초과' in bad
    assert rules.violations((1,2,3,4,5,6),rules.Rules(ac_min=7)) == ['AC 최솟값 미달']


def test_exact_remaining_six_and_no_allowed_fixed_six():
    r=rules.Rules.parse({'excluded':list(range(7,46))})
    assert rules.generate(r) == (1,2,3,4,5,6)
    with pytest.raises(rules.ConstraintError) as e:
        rules.generate(r,blocked=[(1,2,3,4,5,6)])
    assert e.value.code=='infeasible_rules'
    r=rules.Rules.parse({'fixed':[1,2,3,4,5,6]})
    assert rules.generate(r)==(1,2,3,4,5,6)


def test_small_space_all_and_only_allowed_tickets_are_reachable():
    r=rules.Rules.parse({'fixed':[1,2,3,4], 'excluded':list(range(9,46)), 'odd':[3,3]})
    expected={tuple(sorted((1,2,3,4,*x))) for x in combinations(range(5,9),2)
              if sum(n%2 for n in x)==1}
    outputs=Counter(rules.generate(r,rng=random.Random(seed)) for seed in range(1000))
    assert set(outputs)==expected
    assert min(outputs.values())>180 and max(outputs.values())<320


def test_large_space_bounded_rejection_not_proof_of_impossibility():
    class Zero:
        def randrange(self, stop): return 0
    calls=[]
    with pytest.raises(rules.ConstraintError) as e:
        rules.generate({'ac_min':7},rng=Zero(),attempt_limit=3,checkpoint=lambda *v:calls.append(v))
    assert e.value.code=='search_limit'
    assert calls==[(1,3)]


def test_cooperative_cancel_does_not_return_partial_success():
    def stop(*_): raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError,match='cancelled'):
        rules.generate(checkpoint=stop)
    with pytest.raises(RuntimeError,match='cancelled'):
        portfolio.generate_portfolio(list(range(1,10)),3,mode='wheel9',checkpoint=stop)


@pytest.mark.parametrize('seed',range(8))
def test_constraints_always_apply_and_blocked_combos_not_reused(seed):
    r=rules.Rules.parse({'fixed':[7], 'excluded':[13], 'odd':'2-4','max_run':2,
                         'max_same_ending':2,'ac_min':7,'carryover':[0,2]})
    ticket=rules.generate(r,previous=(1,2,3,4,5,6),rng=random.Random(seed))
    assert not rules.violations(ticket,r,(1,2,3,4,5,6))
    again=rules.generate(r,previous=(1,2,3,4,5,6),blocked=[ticket],rng=random.Random(seed))
    assert again!=ticket


def test_portfolio_counts_exclusions_rules_and_coverage_metrics():
    r=rules.Rules.parse({'fixed':[7],'excluded':[13],'odd':[2,4]})
    out=portfolio.generate_portfolio(range_list:=list(range(1,16)),5,rules=r,max_overlap=4,rng=random.Random(2))
    tickets=[tuple(t) for t in out['tickets']]
    assert len(tickets)==5 and len(set(tickets))==5
    assert all(not rules.violations(t,r) for t in tickets)
    assert all(len(set(a)&set(b))<=4 for a,b in combinations(tickets,2))
    assert out['triple_coverage']==len({t for row in tickets for t in combinations(row,3)})
    assert not out['saved_as_purchase'] and not out['global_optimality_proven']
    assert range_list==list(range(1,16))


@pytest.mark.parametrize('mode',['balanced','coverage'])
def test_large_pool_does_not_claim_exact_conditional_verification(mode):
    out=portfolio.generate_portfolio(list(range(1,46)),2,mode=mode,rng=random.Random(7))
    assert len(out['tickets'])==2
    assert out['verification_complete'] is False
    assert out['conditional_min_match']=={} and out['counterexample_count'] is None


@pytest.mark.parametrize('seed',range(6))
def test_wheel9_exact_conditional_minima_independent_check(seed):
    pool=[1,5,10,15,20,25,30,35,45]
    out=portfolio.generate_portfolio(pool,3,mode='wheel9',max_overlap=3,rng=random.Random(seed))
    assert out['maximum_overlap']==3 and out['verification_complete']
    assert set(out['number_usage'].values())=={2}
    assert out['conditional_min_match']['4']==3
    assert out['conditional_min_match']['6']==4
    for k,total,want in [(4,126,3),(6,84,4)]:
        seen=0
        for subset in combinations(pool,k):
            assert max(len(set(subset)&set(row)) for row in out['tickets']) >= want
            seen+=1
        assert seen==total


@pytest.mark.parametrize('kwargs,code',[
    ({'ticket_count':6},'invalid_count'), ({'ticket_count':True},'invalid_count'),
    ({'ticket_count':5,'mode':'wheel9'},'invalid_wheel'),
    ({'ticket_count':3,'mode':'wheel9','max_overlap':2},'infeasible_rules'),
    ({'ticket_count':3,'mode':'wheel9','rules':{'fixed':[1]}},'infeasible_rules'),
    ({'ticket_count':2,'rules':{'fixed':[1,2]},'max_overlap':1},'conflicting_rules'),
])
def test_portfolio_invalid_constraints_never_change_budget(kwargs,code):
    with pytest.raises(rules.ConstraintError) as e:
        portfolio.generate_portfolio(list(range(1,10)),**kwargs)
    assert e.value.code==code


def test_fully_blocked_wheel_does_not_emit_altered_unverified_tickets():
    pool=list(range(1,10));blocked=list(combinations(pool,6))
    with pytest.raises(rules.ConstraintError) as e:
        portfolio.generate_portfolio(pool,3,mode='wheel9',blocked=blocked)
    assert e.value.code=='infeasible_rules'


def test_keyword_normalization_fresh_nonce_and_reproducible_test_rng():
    assert lucky.normalize_keyword('  나의   소망 ')== '나의 소망'
    first=lucky.generate('행운',target_round=100,rng=random.Random(1))
    assert lucky.generate('행운',target_round=100,rng=random.Random(1))==first
    assert lucky.generate('행운',target_round=100,rng=random.Random(2))!=first
    assert lucky.generate('행운',target_round=100,rng=random.Random(1),blocked=[first])!=first
    with pytest.raises(ValueError): lucky.normalize_keyword('x'*81)
    with pytest.raises(ValueError): lucky.normalize_keyword('x\x00y')


def test_family_weighting_and_optimal_allowed_vote_sum():
    sources={A:(1,2,3,4,5,6), B:(1,2,3,4,7,8), 'overdue_gap':(1,4,5,7,9,10)}
    blocked=set(sources.values())
    ticket,votes=vote.select_vote(sources,blocked,'synthetic')
    assert votes[1]==2 and votes[2]==Fraction(1) and votes[9]==Fraction(1)
    possible=[r for r in combinations(range(1,11),6) if r not in blocked]
    assert sum(votes[n] for n in ticket)==max(sum(votes[n] for n in r) for r in possible)
    assert vote.select_vote(sources,blocked,'synthetic')[0]==ticket


def test_votes_are_reactive_and_do_not_change_legacy_median():
    value=sample();ids=(A,B,methods.METHOD_SELECTED_MEDIAN,VID)
    output=consensus.refresh_consensus(value,ids,(),updated_at='one')
    assert output.recommendation_by_method(methods.METHOD_SELECTED_MEDIAN).numbers==(3,11,19,27,35,43)
    assert output.recommendation_by_method(VID) is not None
    assert len(set(r.numbers for r in output.recommendations))==4
    assert consensus.refresh_consensus(output,ids,(),updated_at='two') is output
    rows=list(output.recommendations);rows[1]=replace(rows[1],numbers=(8,16,24,32,40,45))
    changed=consensus.refresh_consensus(replace(output,recommendations=tuple(rows)),ids,(),updated_at='three')
    assert changed.summary[VID]['input_signature']!=output.summary[VID]['input_signature']
    waiting=consensus.refresh_consensus(payload([row(A,(1,2,3,4,5,6))]),(A,VID),())
    assert waiting.recommendation_by_method(VID) is None
    assert waiting.summary[VID]['status']=='waiting_for_sources'


def test_new_sampling_build_cache_rules_and_no_raw_keyword_leak():
    history=_history(30);ids=(CID,LID,A,VID);options={'generation_rules':{'fixed':[7],'excluded':[13],'odd':[2,4]},'lucky_keyword':'PRIVATE_KEYWORD_TEST','lucky_theme':'dream'}
    out=analysis.build_analysis(history,ids,formula_options=options,rng=random.Random(9))
    assert len(out.recommendations)==4
    assert not rules.violations(out.recommendation_by_method(CID).numbers,rules.Rules.parse(options['generation_rules']),history[-1].numbers)
    assert 'PRIVATE_KEYWORD_TEST' not in json.dumps([r.as_attributes() for r in out.recommendations])
    assert 'PRIVATE_KEYWORD_TEST' not in json.dumps(out.summary)
    stored=cache.store_tickets(out,history,ids,0,options)
    restored=cache.restore_tickets(stored,history,ids,0,options)
    assert set(restored)=={CID,LID,A}
    assert cache.restore_tickets(stored,history,ids,0,{**options,'lucky_keyword':'changed'})=={}
    assert cache.restore_tickets(stored,history,ids,0,{**options,'generation_rules':{'fixed':[8]}})=={}
    corrupted=json.loads(json.dumps(stored));corrupted['tickets'][CID]=[1,2,3,4,5,6]
    assert cache.restore_tickets(corrupted,history,ids,0,options)=={}
    assert 'formula_options_digest' not in cache.cache_key(history,(A,),0,options)
    again=analysis.build_analysis(history,ids,restored_tickets=restored,formula_options=options,rng=random.Random(10))
    assert [r.numbers for r in again.recommendations]==[r.numbers for r in out.recommendations]


def test_target_and_future_never_influence_new_formula_generation():
    hv=importlib.import_module('custom_components.lotto_645.historical_validation')
    history=_history(33);ids=(CID,LID,A,VID)
    options={'generation_rules':{'fixed':[7],'carryover':[0,1]},'lucky_keyword':'prefix_only'}
    first=hv.run_historical_validation(history,31,ids,formula_options=options,rng=random.Random(12))
    altered=history[:30]+[replace(d,numbers=(1,2,3,4,5,6),bonus=45) for d in history[30:]]
    second=hv.run_historical_validation(altered,31,ids,formula_options=options,rng=random.Random(12))
    assert first['training_sha256']==second['training_sha256']
    assert [r['recommended_numbers'] for r in first['results']]==[r['recommended_numbers'] for r in second['results']]
    assert not first['persisted'] and not first['counts_toward_reviews']


def test_vote_timestamp_filled_once_and_corrupted_self_is_not_a_source():
    ids=(A,B,VID)
    initial=consensus.refresh_consensus(sample(),ids,())
    assert initial.recommendation_by_method(VID).details['consensus_updated_at'] is None
    stamped=consensus.refresh_consensus(initial,ids,(),updated_at='first')
    assert stamped.recommendation_by_method(VID).details['consensus_updated_at']=='first'
    assert consensus.refresh_consensus(stamped,ids,(),updated_at='later') is stamped
    altered=replace(stamped,recommendations=(*stamped.recommendations[:-1],replace(stamped.recommendations[-1],numbers=(1,2,3,4,5,6))))
    fixed=consensus.refresh_consensus(altered,ids,(),updated_at='later')
    assert fixed.recommendation_by_method(VID).numbers==stamped.recommendation_by_method(VID).numbers


def test_vote_late_generation_is_not_backdated_as_a_pre_draw_prediction():
    from test_local_reviews import BEFORE, AFTER, DRAW, snapshot, review
    state=importlib.import_module('custom_components.lotto_645.fast_result_state')
    value=snapshot(method=VID);value['recommendations'][0]['generated_at']=AFTER.isoformat()
    assert not review.ReviewBook().record_snapshot(value,now=AFTER)
    assert state.evaluate_saved(value,DRAW)['checked_game_count']==0
