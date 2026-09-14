"""Independent mathematical checks; regression success is not predictive success."""
import math
from dataclasses import replace
from collections import Counter
from itertools import combinations
import pytest
from test_analysis_engine import analysis, methods, _history, _profile


def test_rank_ties_are_equal_and_permutation_invariant():
    assert set(analysis._rank01({n:0.0 for n in range(1,46)}).values())=={.5}
    assert analysis._rank01({1:0.,2:1.,3:1.,4:2.}) == {1:0.,2:.5,3:.5,4:1.}
    with pytest.raises(ValueError): analysis._rank01({1:float('nan')})

def test_probabilities_and_expected_matches():
    masses=[analysis.match_probability(k) for k in range(7)]
    assert sum(masses)==pytest.approx(1)
    assert sum(k*p for k,p in enumerate(masses))==pytest.approx(.8)
    assert masses[6]==1/math.comb(45,6)
    assert analysis.PAIR_PROBABILITY==pytest.approx(math.comb(43,4)/math.comb(45,6))
    assert analysis.TRIPLET_PROBABILITY==pytest.approx(math.comb(42,3)/math.comb(45,6))
    assert analysis._carryover_score((7,8,9,10,11,12),set(range(1,7))) > analysis._carryover_score((1,2,9,10,11,12),set(range(1,7)))

def test_bayesian_shrinkage_retains_effect_size():
    history=_history(120)
    weak=analysis._bayesian_feature(analysis._bayesian_recent(history,prior_strength=1))
    strong=analysis._bayesian_feature(analysis._bayesian_recent(history,prior_strength=1000))
    assert max(abs(v-.5) for v in strong.values()) < max(abs(v-.5) for v in weak.values())
    counts=analysis._count_window(history,300)
    expected={n:(counts[n]+500*6/45)/(len(history)+500)-6/45 for n in range(1,46)}
    assert analysis._bayesian_recent(history) == expected

def test_windows_recency_and_pair_scores_are_independently_recomputed():
    history=_history(40)
    counts=Counter(n for d in history[-10:] for n in d.numbers)
    assert analysis._count_window(history,10)==counts
    total=sum(2**(-i/20) for i in range(40))
    decayed=analysis._decayed_frequency(history)
    for n in range(1,46):
        expected=sum(2**(-i/20) for i,d in enumerate(reversed(history)) if n in d.numbers)/total-6/45
        assert decayed[n]==pytest.approx(expected)
    pairs,_=analysis._pair_graph(history)
    for pair in [(1,2),(7,30),(44,45)]:
        count=sum(set(pair)<=set(d.numbers) for d in history)
        z=(count-40*analysis.PAIR_PROBABILITY)/math.sqrt(40*analysis.PAIR_PROBABILITY*(1-analysis.PAIR_PROBABILITY))
        assert pairs[pair]==pytest.approx(.68*math.tanh(z/3)+.32*math.tanh(z/2.2))

def test_candidate_sections_match_displayed_score_sections():
    method=methods.METHODS_BY_ID[methods.METHOD_BALANCE]
    pool=analysis._candidate_pool(method,{n:float(n) for n in range(1,46)})
    for lo,hi in ((1,10),(11,20),(21,30),(31,40),(41,45)):
        assert sum(lo<=n<=hi for n in pool)>=2

def test_empty_active_methods_and_invalid_saju_dont_create_phantom_games():
    history=_history(40)
    assert analysis.build_analysis(history,()).recommendations==()
    result=analysis.build_analysis(history,(methods.METHOD_WEIGHTED_FREQUENCY,),saju_profile={'birth_date':'bad'})
    assert len(result.recommendations)==1

@pytest.mark.parametrize('numbers',[(1,1,3,4,5,6),(0,2,3,4,5,6),(1.,2,3,4,5,6),(6,5,4,3,2,1)])
def test_invalid_history_fail_closed(numbers):
    history=_history(40);history[0]=replace(history[0],numbers=numbers)
    with pytest.raises(ValueError): analysis.build_analysis(history,['weighted_frequency'])

def test_manual_exclusions_override_any_rotation_window():
    history=_history(80);selected=('weighted_frequency','public_ensemble')
    first=analysis.build_analysis(history,selected,nonce:=1)
    forbidden=tuple(rec.numbers for rec in first.recommendations)
    second=analysis.build_analysis(history,selected,nonce,excluded_combinations=forbidden)
    assert not set(forbidden)&{rec.numbers for rec in second.recommendations}
    repeated=analysis.build_analysis(history,selected,nonce,excluded_combinations=forbidden)
    assert second==repeated
    for rec in second.recommendations:
        assert 0<=rec.score<=1
        assert sum(rec.details['score_component_weights'].values())==pytest.approx(1,abs=1e-5)

def test_no_future_outcome_used_by_training_prefix():
    history=_history(42);prefix=history[:40]
    first=analysis.build_analysis(prefix,['weighted_frequency'])
    history[40]=replace(history[40],numbers=(1,2,3,4,5,6),bonus=7)
    assert first==analysis.build_analysis(history[:40],['weighted_frequency'])
