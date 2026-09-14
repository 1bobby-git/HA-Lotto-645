"""Actual-ticket consensus, not hidden feature-score median or random refresh."""
from dataclasses import replace
from datetime import timedelta
import importlib
from itertools import product
from types import SimpleNamespace

import pytest
from test_analysis_engine import models, methods, analysis as engine, _history

consensus = importlib.import_module('custom_components.lotto_645.consensus')
MID = methods.METHOD_SELECTED_MEDIAN
A = methods.METHOD_UNIFORM_FISHER_YATES
B = methods.METHOD_UNIFORM_FLOYD
C = methods.METHOD_BAYESIAN_SHRINKAGE
T1 = '2026-09-14T07:00:00+00:00'
T2 = '2026-09-14T08:00:00+00:00'


def row(key, values, index=1, **details):
    return models.Recommendation(index, key, key, 'test', tuple(values), '', .9, details)


def payload(rows):
    return models.AnalysisResult(1242, 1241, tuple(rows), {'generation_sequence': 0})


def sample():
    return payload([row(A, (2, 10, 18, 26, 34, 42)), row(B, (4, 12, 20, 28, 36, 44), 2)])


def derive(value, ids=(A, B, MID), history=(), at=T1):
    return consensus.refresh_consensus(value, ids, history, updated_at=at)


def test_real_six_position_medians_and_not_score_medians():
    result = derive(sample()).recommendation_by_method(MID)
    assert result.numbers == (3, 11, 19, 27, 35, 43)
    assert result.details['consensus_position_medians'] == [3, 11, 19, 27, 35, 43]
    assert result.score is None
    assert result.details['formula_version'] == 2
    assert 'consensus_number_median_scores' not in result.details
    assert result.details['rng'] == 'not_used'
    assert result.details['consensus_source_count'] == 2


def test_source_update_changes_derived_value_without_changing_other_sources():
    first = derive(sample())
    rows = list(first.recommendations)
    rows[1] = replace(rows[1], numbers=(8, 16, 24, 32, 40, 45))
    changed = replace(first, recommendations=tuple(rows))
    final = derive(changed, at=T2)
    rec = final.recommendation_by_method(MID)
    assert rec.numbers != first.recommendation_by_method(MID).numbers
    assert rec.details['consensus_updated_at'] == T2
    assert final.recommendations[:2] == changed.recommendations[:2]


def test_identical_inputs_do_not_reroll_on_refresh_nonce_or_timestamp():
    first = derive(sample())
    assert derive(first, at=T2) is first
    changed = replace(first, summary={**first.summary, 'generation_sequence': 900})
    final = derive(changed, at=T2)
    assert final is changed
    assert final.recommendation_by_method(MID) is first.recommendation_by_method(MID)
    changed_scores = replace(first, recommendations=(
        replace(first.recommendations[0], score=.01), *first.recommendations[1:]))
    assert derive(changed_scores, at=T2).recommendation_by_method(MID) is first.recommendation_by_method(MID)


def test_add_remove_formula_changes_input_signature_and_excludes_deselected():
    third = row(C, (7, 15, 23, 31, 39, 45), 3)
    first = derive(payload([*sample().recommendations, third]))
    expanded = derive(first, (A, B, C, MID), at=T2)
    rec = expanded.recommendation_by_method(MID)
    assert rec.details['consensus_source_count'] == 3
    assert rec.details['consensus_source_numbers'][C] == list(third.numbers)
    assert rec.details['consensus_input_signature'] != first.recommendation_by_method(MID).details['consensus_input_signature']
    reduced = derive(expanded, (A, B, MID), at=T2)
    assert reduced.recommendation_by_method(MID).numbers == first.recommendation_by_method(MID).numbers
    assert C not in reduced.recommendation_by_method(MID).details['consensus_source_numbers']
    disabled = derive(expanded, (A, B, C))
    assert disabled.recommendation_by_method(MID) is None
    assert 'selected_median_consensus' not in disabled.summary


def test_source_order_and_self_output_never_affect_the_numbers():
    first = derive(sample())
    assert derive(first, (MID, B, A)).recommendation_by_method(MID).numbers == first.recommendation_by_method(MID).numbers
    wrong_self = replace(first.recommendations[-1], numbers=(1, 2, 3, 4, 5, 6))
    changed = replace(first, recommendations=(*first.recommendations[:2], wrong_self))
    assert derive(changed).recommendation_by_method(MID).numbers == first.recommendation_by_method(MID).numbers


def test_ai_and_unknown_sensors_never_vote():
    ai = replace(row('home_assistant_ai', (1, 2, 3, 4, 5, 6)), source='ai_task')
    unknown = row('latest_draw', (40, 41, 42, 43, 44, 45))
    result = derive(payload([*sample().recommendations, ai, unknown]), (A, B, MID, 'home_assistant_ai', 'latest_draw'))
    assert result.recommendation_by_method(MID).numbers == (3, 11, 19, 27, 35, 43)
    assert result.recommendation_by_method(MID).details['consensus_source_count'] == 2


@pytest.mark.parametrize('invalid', [None, (), '1,2,3,4,5,6', (True,2,3,4,5,6),
    (1,1,3,4,5,6), (0,2,3,4,5,6), (1,2,3,4,5,46), (1.,2,3,4,5,6)])
def test_invalid_and_unavailable_source_values_do_not_form_fake_numbers(invalid):
    original = derive(sample())
    broken = replace(original.recommendations[1], numbers=invalid)
    changed = replace(original, recommendations=(original.recommendations[0], broken, original.recommendations[-1]))
    result = derive(changed, at=T2)
    assert result.recommendation_by_method(MID) is None
    assert result.summary['selected_median_consensus']['status'] == 'waiting_for_sources'
    assert result.summary['selected_median_consensus']['missing_source_method_ids'] == [B]


def test_missing_or_previous_round_source_clears_stale_consensus_then_recovers():
    original = derive(sample())
    stale = replace(original.recommendations[1], details={'target_round':1241})
    changed = replace(original, recommendations=(original.recommendations[0], stale, original.recommendations[-1]))
    assert derive(changed).recommendation_by_method(MID) is None
    missing = replace(original, recommendations=(original.recommendations[0], original.recommendations[-1]))
    assert derive(missing).recommendation_by_method(MID) is None
    assert derive(original).recommendation_by_method(MID) is not None


def test_half_integer_medians_and_endpoints_keep_true_tolerance():
    for tickets in [((1,2,3,4,5,6),(2,3,4,5,6,7)),
                    ((1,2,3,43,44,45),(1,2,3,43,44,45))]:
        combo, centers = consensus.select_near_medians(tickets, tickets)
        assert combo is not None
        assert len(set(combo)) == 6 and all(1 <= n <= 45 for n in combo)
        assert all(abs(n-c) <= 1 for n,c in zip(combo,centers))
        assert combo not in tickets


def test_no_candidate_does_not_expand_tolerance_or_return_previous_winner():
    centers = (3,11,19,27,35,43)
    forbidden = list(product(*(range(c-1,c+2) for c in centers)))
    assert consensus.select_near_medians([tuple(centers)]*2, forbidden)[0] is None
    history = [SimpleNamespace(round=i+1, numbers=t) for i,t in enumerate(forbidden)]
    result = derive(sample(), history=history)
    assert result.recommendation_by_method(MID) is None
    assert result.summary['selected_median_consensus']['status'] == 'no_candidate_within_tolerance'


def test_past_winner_excluded_and_history_correction_recomputes():
    first = derive(sample())
    winner = first.recommendation_by_method(MID).numbers
    result = derive(first, history=[SimpleNamespace(round=1241,numbers=winner)], at=T2)
    assert result.recommendation_by_method(MID).numbers != winner
    assert all(abs(n-c) <= 1 for n,c in zip(result.recommendation_by_method(MID).numbers, winner))
    assert derive(first, history=[SimpleNamespace(round=1243,numbers=winner)]).recommendation_by_method(MID).numbers == winner


def test_uniform_sources_work_without_hidden_score_candidate_optimizer(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Consensus must not enter source score optimization')
    monkeypatch.setattr(engine, '_select_candidate', forbidden)
    result = engine.build_analysis(_history(40), (MID,A,B))
    assert result.recommendation_by_method(MID).details['consensus_source_count'] == 2
    assert result.summary['execution_method_ids'][-1] == MID


def test_new_aggregate_timestamp_is_not_backdated_for_reviews_or_prizes():
    from test_local_reviews import BEFORE, AFTER, DRAW, snapshot, review
    state = importlib.import_module('custom_components.lotto_645.fast_result_state')
    value = snapshot(method=MID)
    value['recommendations'][0]['generated_at'] = AFTER.isoformat()
    book = review.ReviewBook()
    assert not book.record_snapshot(value, now=AFTER)
    assert state.evaluate_saved(value, DRAW)['checked_game_count'] == 0
    value['recommendations'][0]['generated_at'] = None
    assert not book.record_snapshot(value, now=BEFORE)
    value['recommendations'][0]['generated_at'] = (BEFORE+timedelta(minutes=1)).isoformat()
    assert book.record_snapshot(value, now=BEFORE+timedelta(minutes=2))
    assert state.evaluate_saved(value, DRAW)['checked_game_count'] == 1
