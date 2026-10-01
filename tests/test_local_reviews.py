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


def multi_game_snapshot(method='weighted_frequency', when=BEFORE, round_no=ROUND):
    """One formula, three games: the snapshot shape the coordinator archives."""
    rows = [models.Recommendation(
        index, method, method, 'test', tuple(sorted(numbers)), '', None, {}, 'analysis',
        formula_game=index,
    ) for index, numbers in enumerate(((1, 2, 3, 4, 5, 6), (2, 3, 4, 5, 6, 7),
                                      (11, 13, 18, 22, 31, 32)), start=1)]
    return {'target_round': round_no, 'based_on_round': round_no - 1,
            'local_generated_at': when.isoformat(), 'ai_generated_at': when.isoformat(),
            'recommendations': [row.to_storage() for row in rows]}


def test_archiving_keeps_every_game_but_still_votes_once_per_formula():
    book = review.ReviewBook()
    assert book.record_snapshot(multi_game_snapshot(), now=BEFORE, archive_all=True)
    row = book.rounds[str(ROUND)]
    assert list(row['games']) == ['weighted_frequency#1', 'weighted_frequency#2', 'weighted_frequency#3']
    assert row['games']['weighted_frequency#3']['numbers'] == [11, 13, 18, 22, 31, 32]
    assert row['games']['weighted_frequency#3']['formula_game'] == 3
    # One prediction per formula: the review ledger keeps its single vote.
    assert list(row['predictions']) == ['weighted_frequency']
    assert row['predictions']['weighted_frequency']['numbers'] == [1, 2, 3, 4, 5, 6]
    book.set_result(DRAW, confirmed=True, status='official_history')
    assert len(book.round_review(ROUND)['methods']) == 1
    assert book.summary('weighted_frequency')['reviewed_rounds'] == 1


def test_a_game_is_never_overwritten_by_an_older_generation():
    book = review.ReviewBook()
    book.record_snapshot(multi_game_snapshot(), now=BEFORE, archive_all=True)
    older = multi_game_snapshot(when=BEFORE - timedelta(hours=1))
    for row in older['recommendations']:
        row['numbers'] = [40, 41, 42, 43, 44, 45]
    book.record_snapshot(older, now=BEFORE, archive_all=True)
    assert book.rounds[str(ROUND)]['games']['weighted_frequency#2']['numbers'] == [2, 3, 4, 5, 6, 7]


def test_the_game_archive_survives_restart_and_broken_rows_are_skipped():
    book = review.ReviewBook()
    book.record_snapshot(multi_game_snapshot(), now=BEFORE, archive_all=True)
    restored = review.ReviewBook.from_storage(book.to_storage())
    assert restored.rounds[str(ROUND)]['games'] == book.rounds[str(ROUND)]['games']
    payload = book.to_storage()
    payload['rounds'][str(ROUND)]['games']['broken'] = {'numbers': [1, 2, 3], 'label': 5}
    payload['rounds'][str(ROUND)]['games']['also-broken'] = 'not-a-row'
    healed = review.ReviewBook.from_storage(payload)
    assert list(healed.rounds[str(ROUND)]['predictions']) == ['weighted_frequency']
    assert 'broken' not in healed.rounds[str(ROUND)]['games']


def test_plain_snapshots_are_not_archived():
    book = review.ReviewBook()
    book.record_snapshot(snapshot(), now=BEFORE)
    assert 'games' not in book.rounds[str(ROUND)]
    assert book.rounds[str(ROUND)]['predictions']['weighted_frequency']['numbers'] == list(DRAW.numbers)


def _coordinator_methods(*names):
    """Execute the real coordinator snapshot builders without Home Assistant."""
    import ast
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'custom_components/lotto_645/coordinator.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Lotto645Coordinator')
    nodes = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names), f'missing coordinator methods: {names}'
    ns = {'AnalysisResult': object, 'Recommendation': models.Recommendation,
          'datetime': datetime, 'UTC': UTC, 'draw_cutoff': pub.draw_cutoff,
          'METHOD_SELECTED_MEDIAN': 'selected_median_consensus',
          'METHOD_SELECTED_VOTE': 'selected_vote_consensus',
          'Any': object}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), 'exec'), ns)
    return ns


def test_the_coordinator_archives_every_game_but_still_snapshots_one_per_formula():
    ns = _coordinator_methods('_build_prediction_snapshot', '_set_prediction_snapshot')
    games = [models.Recommendation(
        index, 'weighted_frequency', '가중 빈도', 'test', tuple(sorted(numbers)), '', None, {},
        'analysis', formula_game=index,
    ) for index, numbers in enumerate(((1, 2, 3, 4, 5, 6), (2, 3, 4, 5, 6, 7),
                                       (11, 13, 18, 22, 31, 32)), start=1)]
    analysis = models.AnalysisResult(ROUND, ROUND - 1, tuple(games), {})
    owner = SimpleNamespace(
        _local_generation_nonce=5, _local_generated_at=BEFORE, _fast_result={},
        review_book=review.ReviewBook(), review_storage_error=False,
        _review_dirty=False, _needs_storage_save=True, _prediction_snapshot=None,
    )
    owner._build_prediction_snapshot = ns['_build_prediction_snapshot'].__get__(owner)
    ns['_set_prediction_snapshot'](owner, analysis, None, None)
    row = owner.review_book.rounds[str(ROUND)]
    assert list(row['games']) == ['weighted_frequency#1', 'weighted_frequency#2', 'weighted_frequency#3']
    assert row['games']['weighted_frequency#3']['numbers'] == [11, 13, 18, 22, 31, 32]
    # The evaluated snapshot still holds one game per formula.
    assert list(row['predictions']) == ['weighted_frequency']
    assert [item['formula_game'] for item in owner._prediction_snapshot['recommendations']] == [1]


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
