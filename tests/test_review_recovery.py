"""Recover persisted evaluated tickets only when pre-draw evidence survives."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
import pytest
from test_local_reviews import review, state, DRAW, ROUND, BEFORE, AFTER, snapshot


def legacy(source='analysis'):
    return {'round': ROUND, 'prediction_based_on_round': ROUND-1,
            'prediction_generated_at': BEFORE.isoformat(), 'evaluated_at': AFTER.isoformat(),
            'results': [{'method_id':'public_ensemble', 'sensor_name':'공개 공식 · 종합 앙상블',
                         'source':source, 'recommended_numbers':list(DRAW.numbers), 'prize':'1등'}]}


def test_legacy_evaluated_ticket_restores_once_with_current_official_result():
    f=type('Fake',(state.ReviewState,),{})()
    f.review_book=review.ReviewBook();f.history=[DRAW];f._prediction_snapshot=None
    f._draw_evaluation=legacy()
    f._sync_reviews()
    assert f.review_for_method('public_ensemble')['reviewed_rounds']==1
    assert f.review_for_method('public_ensemble')['mean_score']==100
    assert f.recorded_evaluation(DRAW)['results'][0]['prize']=='1등'
    before=f.review_book.to_storage();f._sync_reviews()
    assert f.review_book.to_storage()==before
    restored=review.ReviewBook.from_storage(before)
    assert restored.summary('public_ensemble')['reviewed_rounds']==1


@pytest.mark.parametrize('change',[{'prediction_generated_at':None},{'prediction_generated_at':AFTER.isoformat()},
                                    {'prediction_generated_at':BEFORE.replace(tzinfo=None).isoformat()},
                                    {'prediction_based_on_round':ROUND}, {'prediction_based_on_round':True}])
def test_after_draw_or_unknown_not_fabricated(change):
    b=review.ReviewBook(); changed,excluded=b.record_evaluation(legacy()|change,now=AFTER)
    assert not changed and excluded and not b.rounds
    assert '누적평가 제외' in excluded[0]['reason']


def test_ai_does_not_borrow_local_timestamp_or_count_purchase():
    b=review.ReviewBook();data=legacy('ai_task')
    assert not b.record_evaluation(data,now=AFTER)[0]
    data['prediction_ai_generated_at']=BEFORE.isoformat()
    assert b.record_evaluation(data,now=AFTER)[0]
    assert not review.ReviewBook().record_evaluation(legacy('purchased'),now=AFTER)[0]


def test_prior_ledger_is_never_overwritten_from_evaluation():
    b=review.ReviewBook();b.record_snapshot(snapshot(method='public_ensemble'),now=BEFORE)
    original=b.to_storage();data=legacy();data['results'][0]['recommended_numbers']=[1,2,3,4,5,6]
    assert not b.record_evaluation(data,now=AFTER)[0]
    assert b.to_storage()==original


def test_excluded_reason_is_available_without_mutating_cached_summary():
    f=type('Fake',(state.ReviewState,),{})();f.review_book=review.ReviewBook();f.history=[DRAW]
    f._draw_evaluation=legacy()|{'prediction_generated_at':None};f._sync_reviews()
    assert f.review_for_method('public_ensemble')['current_review_exclusion']['round']==ROUND
    assert f.review_for_round(ROUND)['excluded_methods'][0]['method_id']=='public_ensemble'
    assert f._review_summaries=={}


def test_supplied_visible_ensemble_is_fifth_prize_not_a_pending_score():
    d=type(DRAW)(1241,'2026-09-12',(7,13,16,23,24,43),9)
    r=review.compare_numbers((7,13,15,24,38,42),d)
    assert r['prize']=='5등' and r['exact_match_count']==3 and r['near_match_count']==2
    assert round(r['review_score'],1)==57.1
