"""Legacy saved evaluation migration without fabricated historical predictions."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
import pytest
from test_local_reviews import review, state, DRAW, BEFORE, AFTER, ROUND, snapshot, Fake
from custom_components.lotto_645.review_recovery import record_evaluation


def legacy(numbers=DRAW.numbers, source='analysis', when=BEFORE):
    return {'round': ROUND, 'prediction_based_on_round': ROUND-1,
            'prediction_generated_at': when.isoformat() if when else None,
            'evaluated_at': AFTER.isoformat(),
            'results': [{'method_id': 'public_ensemble', 'sensor_name':'종합 앙상블',
                         'source':source, 'recommended_numbers':list(numbers)}]}


def test_stored_evaluation_recovers_after_next_snapshot_replaced_old_one():
    f=Fake();f.review_book=review.ReviewBook();f.history=[DRAW]
    f._prediction_snapshot=None;f._frozen_result_snapshot=None;f._draw_evaluation=legacy()
    f._sync_reviews()
    assert f.review_for_method('public_ensemble')['mean_score']==100
    assert f.review_for_method('public_ensemble')['reviewed_rounds']==1
    for _ in range(4):f._sync_reviews()
    assert f.review_for_method('public_ensemble')['reviewed_rounds']==1
    restored=review.ReviewBook.from_storage(f.review_book.to_storage())
    assert restored.summary('public_ensemble')['mean_score']==100


@pytest.mark.parametrize('when',[None, AFTER])
def test_unknown_or_late_time_not_backfilled_but_reason_is_visible(when):
    f=Fake();f.review_book=review.ReviewBook();f.history=[DRAW];f._draw_evaluation=legacy(when=when)
    f._sync_reviews();summary=f.review_for_method('public_ensemble')
    assert summary.get('reviewed_rounds',0)==0
    assert summary['unrated_result']['comparison']['prize']=='1등'
    assert summary['unrated_result']['counts_toward_rating'] is False
    assert f.review_book.rounds=={}


def test_evaluation_timestamp_never_substitutes_for_generation():
    b=review.ReviewBook();e=legacy(when=None);e['evaluated_at']=BEFORE.isoformat()
    assert not record_evaluation(b, e,now=AFTER)


def test_ai_cannot_borrow_local_generation_time_but_accepts_own_timestamp():
    b=review.ReviewBook();e=legacy(source='ai_task')
    assert not record_evaluation(b, e,now=AFTER)
    e['results'][0]['generated_at']=BEFORE.isoformat()
    assert record_evaluation(b, e,now=AFTER)


def test_purchase_and_invalid_or_future_basis_are_rejected():
    b=review.ReviewBook()
    assert not record_evaluation(b, legacy(source='purchased'),now=AFTER)
    e=legacy();e['prediction_based_on_round']=ROUND
    assert not record_evaluation(b, e,now=AFTER)
    e=legacy();e['results'][0]['recommended_numbers']=[1]*6
    assert not record_evaluation(b, e,now=AFTER)


def test_existing_frozen_prediction_not_overwritten_by_migration():
    b=review.ReviewBook();b.record_snapshot(snapshot(method='public_ensemble'),now=BEFORE)
    assert not record_evaluation(b, legacy((1,2,3,4,5,6),when=BEFORE+timedelta(minutes=10)),now=AFTER)
    assert b.rounds[str(ROUND)]['predictions']['public_ensemble']['numbers']==list(DRAW.numbers)


def test_migration_does_not_trust_old_winning_numbers_or_prize():
    f=Fake();f.review_book=review.ReviewBook();f.history=[DRAW];f._draw_evaluation=legacy()
    f._draw_evaluation['winning_numbers']=[1,2,3,4,5,6]
    f._draw_evaluation['results'][0]['prize']='미당첨'
    f._sync_reviews()
    assert f.review_for_method('public_ensemble')['latest_confirmed']['prize']=='1등'


def test_screenshot_example_is_fifth_prize_not_only_waiting():
    from dataclasses import replace
    d=replace(DRAW,numbers=(7,13,16,23,24,43),bonus=9)
    f=Fake();f.review_book=review.ReviewBook();f.history=[d]
    f._draw_evaluation=legacy((7,13,15,24,38,42));f._sync_reviews()
    s=f.review_for_method('public_ensemble')
    assert s['reviewed_rounds']==1 and s['latest_confirmed']['prize']=='5등'
    assert s['latest_confirmed']['exact_match_count']==3
    assert s['latest_confirmed']['near_match_count']==2
    assert round(s['mean_score'],1)==57.1
