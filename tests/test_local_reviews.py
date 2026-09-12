"""Local review correctness, provenance, correction and non-winning near matches."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from dataclasses import replace
import importlib
from itertools import permutations
import random
from types import SimpleNamespace
import pytest
from test_analysis_engine import models

review = importlib.import_module('custom_components.lotto_645.review')
state = importlib.import_module('custom_components.lotto_645.review_state')
pub = importlib.import_module('custom_components.lotto_645.published_results')

ROUND=1241
DRAW=models.LottoDraw(ROUND,'2026-09-12',(5,10,15,20,25,30),40)
BEFORE=pub.draw_cutoff(ROUND)-timedelta(hours=2)
AFTER=pub.draw_cutoff(ROUND)+timedelta(hours=2)

def snapshot(numbers=DRAW.numbers, method='weighted_frequency', when=BEFORE, source='analysis', round_no=ROUND):
    row=models.Recommendation(1,method,method,'test',tuple(numbers),'',None,{},source)
    return {'target_round':round_no,'based_on_round':round_no-1,
            'local_generated_at':when.isoformat() if when else None,
            'ai_generated_at':when.isoformat() if when else None,
            'recommendations':[row.to_storage()]}


def test_exact_prize_and_review_maximum():
    r=review.compare_numbers(DRAW.numbers,DRAW)
    assert r['prize']=='1등' and r['review_score']==100 and r['stars']==5
    assert r['exact_match_count']==6 and r['near_match_count']==0
    assert sum(r['score_components'].values())==pytest.approx(r['review_score'],abs=1e-4)


def test_nearby_numbers_never_win_or_reuse_an_actual_ball():
    r=review.compare_numbers((4,9,14,19,24,29),DRAW)
    assert r['near_match_count']==6 and r['prize_rank'] is None
    assert r['review_score']<=20
    r=review.compare_numbers((4,5,6,12,42,45),DRAW)
    assert r['exact_match_count']==1 and all(p['drawn']!=5 for p in r['near_pairs'])
    assert len({p['drawn'] for p in r['near_pairs']})==r['near_match_count']
    # 45 and 1 are not adjacent (no cyclic matching).
    r=review.compare_numbers((2,10,20,25,30,45),replace(DRAW,numbers=(1,10,20,25,30,35)))
    assert not any(p['recommended']==45 for p in r['near_pairs'])


def test_assignment_against_exhaustive_independent_oracle():
    rng=random.Random(319)
    for _ in range(24):
        pred=tuple(sorted(rng.sample(range(1,46),6)))
        actual=tuple(sorted(rng.sample(range(1,46),6)))
        bonus=next(n for n in range(1,46) if n not in actual)
        d=replace(DRAW,numbers=actual,bonus=bonus)
        exact=set(pred)&set(actual)
        left=[x for x in pred if x not in exact];right=[x for x in actual if x not in exact]
        expected=max((sum(abs(a-b)==1 for a,b in zip(left,order)) for order in permutations(right)),default=0)
        result=review.compare_numbers(pred,d)
        assert result['near_match_count']==expected
        assert 0<=result['review_score']<=100 and 0<=result['stars']<=5


def test_freeze_latest_actual_snapshot_per_method_and_deselected_retained():
    b=review.ReviewBook()
    assert b.record_snapshot(snapshot(),now=BEFORE)
    changed=snapshot((1,2,3,4,5,6),when=BEFORE+timedelta(minutes=3))
    assert b.record_snapshot(changed,now=BEFORE+timedelta(minutes=4))
    assert b.record_snapshot(snapshot(method='old_deselected'),now=BEFORE)
    assert not b.record_snapshot(snapshot((2,3,4,5,6,7),when=AFTER),now=AFTER)
    assert not b.record_snapshot(snapshot((2,3,4,5,6,7),when=BEFORE+timedelta(minutes=5)),now=AFTER)
    b.set_result(DRAW,confirmed=True,status='official_history')
    assert len(b.round_review(ROUND)['methods'])==2
    assert b.rounds[str(ROUND)]['predictions']['weighted_frequency']['numbers']==[1,2,3,4,5,6]


def test_no_old_history_invented_no_purchase_in_review_no_missing_time():
    b=review.ReviewBook()
    assert not b.set_result(DRAW,confirmed=True,status='official_history')
    for sample in (snapshot(when=None),snapshot(when=AFTER),snapshot(source='purchased')):
        assert not b.record_snapshot(sample,now=AFTER)
    assert b.to_storage()['rounds']=={}
    assert b.summary('weighted_frequency')['reviewed_rounds']==0
    assert '평가대기' in review.review_name('test',{})


def test_provisional_separate_official_upsert_and_restart():
    b=review.ReviewBook();b.record_snapshot(snapshot(),now=BEFORE)
    assert b.set_result(DRAW,confirmed=False,status='provisional')
    assert b.summary('weighted_frequency')['reviewed_rounds']==0
    assert '잠정' in review.review_name('test',b.summary('weighted_frequency'))
    assert b.invalidate_provisional(ROUND)
    assert b.summary('weighted_frequency')['latest_provisional'] is None
    assert b.set_result(DRAW,confirmed=True,status='official_history')
    summary=b.summary('weighted_frequency')
    assert summary['mean_score']==100 and summary['reviewed_rounds']==1
    assert not b.set_result(DRAW,confirmed=True,status='official_history')
    assert not b.set_result(replace(DRAW,bonus=41),confirmed=False,status='provisional')
    corrected=replace(DRAW,numbers=(5,10,15,20,25,35),bonus=30)
    assert b.set_result(corrected,confirmed=True,status='official_history')
    changed=b.summary('weighted_frequency')
    assert changed['reviewed_rounds']==1 and changed['mean_score']<100
    assert changed['latest_confirmed']['prize']=='2등'
    restored=review.ReviewBook.from_storage(b.to_storage())
    assert restored.summary('weighted_frequency')==changed


def test_accumulation_counts_draws_not_refresh_clicks_and_ties_share_rank():
    b=review.ReviewBook()
    for r in (1240,1241):
        when=pub.draw_cutoff(r)-timedelta(hours=1)
        for m in ('one','two'):
            b.record_snapshot(snapshot(method=m,round_no=r,when=when),now=when)
        b.set_result(replace(DRAW,round=r),confirmed=True,status='official_history')
    assert b.summary('one')['reviewed_rounds']==2
    assert b.summary('one')['total_score']==200
    assert {r['rank_this_round'] for r in b.round_review(1241)['methods']}=={1}
    payload=b.to_storage();payload['rounds']['1241']['predictions']['one']['numbers']=[1]*6
    with pytest.raises(ValueError):review.ReviewBook.from_storage(payload)


class Fake(state.ReviewState): pass

def test_cached_state_sync_preserves_official_over_overlay_and_all_methods():
    f=Fake();f.review_book=review.ReviewBook();f.review_storage_error=False
    f.history=[];f._prediction_snapshot=snapshot();f._frozen_result_snapshot=None
    f._sync_reviews()
    f.history=[DRAW];f._sync_reviews()
    assert f.review_for_method('weighted_frequency')['mean_score']==100
    assert f.recorded_evaluation(DRAW)['winning_game_count']==1
    f._fast_result={'status':'conflict','round':ROUND}
    f._sync_reviews()
    assert f.review_for_method('weighted_frequency')['reviewed_rounds']==1
    before=f.review_book.to_storage();f.review_storage_error=True
    f.history=[replace(DRAW,bonus=41)];f._sync_reviews()
    assert f.review_book.to_storage()==before
