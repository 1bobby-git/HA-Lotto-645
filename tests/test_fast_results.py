"""Known published snippets plus synthetic adversarial inputs; no live timing claim."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import importlib
from types import SimpleNamespace

import pytest
from test_analysis_engine import models

pub = importlib.import_module('custom_components.lotto_645.published_results')
state_mod = importlib.import_module('custom_components.lotto_645.fast_result_state')
purchases = importlib.import_module('custom_components.lotto_645.purchased_tickets')
NOW = datetime(2026, 9, 5, 12, 30, tzinfo=UTC)
TITLE = '1240회 로또 1등 11, 13, 19, 20, 31, 44…보너스 27'
URL = 'https://www.newsis.com/view/NISX20260905_0003777757'
# The title is an actual publisher result. Tests do not claim the current RSS contains it.

def candidate(title=TITLE, content='', provider='newsis', url=URL, when=NOW, target=1240, now=NOW):
    return pub.parse_report(title, content, provider, url, when, target, now)


def test_real_headline_result_and_distinct_bonus():
    r = candidate()
    assert r.draw.round == 1240
    assert r.draw.numbers == (11, 13, 19, 20, 31, 44)
    assert r.draw.bonus == 27
    assert r.draw.draw_date == '2026-09-05'
    assert r.draw.first_prize_amount is None
    assert pub.PublishedDraw.from_dict(r.as_dict()) == r


def test_actual_body_punctuation_pattern():
    r = candidate(title='로또 1240회 1등 당첨번호', content="제1240회 당첨번호는 '11, 13, 19, 20, 31, 44'이다. 2등 보너스 번호는 '27'이다.")
    assert r.draw.bonus == 27


@pytest.mark.parametrize('changes', [
    {'title': TITLE.replace('1240','1239')}, {'title': TITLE.replace('1등','예상 1등')},
    {'title': TITLE.replace('27','11')}, {'title': TITLE.replace('11, 13','11, 11')},
    {'title': TITLE.replace('44','46')}, {'title': TITLE.replace('…보너스 27','')},
    {'title': TITLE.replace('11, 13','11, 12, 13')}, {'when': NOW-timedelta(hours=2)},
    {'when': NOW+timedelta(hours=2)}, {'target':1241},
    {'content':'1239회 로또 결과'}, {'content':'보너스 번호는 28'},
    {'url':'https://127.0.0.1/view/x'}, {'url':'https://www.newsis.com.evil/view/x'},
    {'url':'https://user:password@www.newsis.com/view/x'}, {'url':'http://www.newsis.com/view/x'},
])
def test_invalid_stale_ambiguous_or_untrusted_reports_rejected(changes):
    assert candidate(**changes) is None


def test_no_fabricated_after_broadcast_end():
    assert pub.current_draw_round(datetime(2026,9,12,11,34,tzinfo=UTC))==1240
    assert pub.current_draw_round(datetime(2026,9,12,11,35,tzinfo=UTC))==1241
    assert pub.poll_interval(datetime(2026,9,12,11,35,tzinfo=UTC))==60
    assert pub.poll_interval(datetime(2026,9,12,13,0,tzinfo=UTC))==300
    assert pub.poll_interval(datetime(2026,9,13,0,0,tzinfo=UTC))==900
    assert pub.poll_interval(datetime(2026,9,14,0,0,tzinfo=UTC)) is None


def test_one_publisher_provisional_two_publishers_and_conflict():
    a = candidate()
    b = candidate(provider='sbs',url='https://news.sbs.co.kr/news/endPage.do?news_id=fixture')
    assert pub.select_result([a])['status']=='provisional'
    assert pub.select_result([a,a])['status']=='provisional'
    assert pub.select_result([a,b])['status']=='cross_checked'
    wrong=replace(b,draw=replace(b.draw,bonus=28))
    assert pub.select_result([a,wrong])['status']=='conflict'
    assert pub.select_result([a,wrong])['draw'] is None


def test_rss_entity_and_size_limit_and_round_filter():
    with pytest.raises(ValueError):pub.rss_items(b'<!DOCTYPE bad []><rss/>','newsis',1240,NOW)
    with pytest.raises(ValueError):pub.rss_items(b'x'*2000001,'newsis',1240,NOW)
    rss=f'<rss><channel><item><title>{TITLE}</title><link>{URL}</link><pubDate>Sat, 05 Sep 2026 21:15:00 +0900</pubDate><description>결과</description></item></channel></rss>'.encode()
    assert len(pub.rss_items(rss,'newsis',1240,NOW))==1
    assert not pub.rss_items(rss,'newsis',1241,NOW)


class Fake(state_mod.FastResultState):
    pass


def snapshot(timestamp='2026-09-05T10:00:00+00:00'):
    rec=models.Recommendation(1,'test','시험 추천','test',(11,13,19,20,31,44),'',None,{})
    return {'target_round':1240,'based_on_round':1239,'local_generated_at':timestamp,
            'recommendations':[rec.to_storage()]}


def test_late_or_unknown_generated_recommendation_excluded_not_losing():
    draw=candidate().draw
    good=state_mod.evaluate_saved(snapshot(),draw)
    assert good['highest_prize']=='1등'
    assert state_mod.evaluate_saved(snapshot(None),draw)['checked_game_count']==0
    assert state_mod.evaluate_saved(snapshot(NOW.isoformat()),draw)['checked_game_count']==0


def test_provisional_does_not_mutate_analysis_history_and_official_corrects():
    f=Fake(); f.history=[models.LottoDraw(1239,'2026-08-29',(1,2,3,4,5,6),7)]
    f.data=SimpleNamespace(latest_draw=f.history[-1]);f._draw_evaluation=None
    f.purchase_book=purchases.PurchaseBook().updated(1240,{'game_a':'111319203144'})
    f.purchase_storage_error=False;f._prediction_snapshot=snapshot();original=f.history[:]
    assert f._accept_fast_state(pub.select_result([candidate()]))
    assert f.result_draw.round==1240 and f.result_round==1240
    assert f.history==original and f.data.latest_draw.round==1239
    assert f.winning_summary['winning_game_count']==2
    assert f.winning_summary['provisional'] is True
    # Same frozen forecast is checked against corrected official main numbers.
    correction=replace(candidate().draw,numbers=(10,13,19,20,31,44),bonus=27)
    f.history.append(correction);f.data.latest_draw=correction
    assert f.result_metadata['status']=='official_corrected'
    assert f.winning_summary['results'][0]['prize']=='3등'
    assert f.winning_summary['provisional'] is False


def test_conflict_never_graded_as_losing_and_snapshot_survives_restart():
    f=Fake();f.history=[models.LottoDraw(1239,'2026-08-29',(1,2,3,4,5,6),7)]
    f.data=SimpleNamespace(latest_draw=f.history[-1]);f._prediction_snapshot=snapshot()
    f._draw_evaluation=None;f.purchase_book=purchases.PurchaseBook();f.purchase_storage_error=False
    a=candidate();b=replace(a,publisher='sbs',url='https://news.sbs.co.kr/news/endPage.do?news_id=x',draw=replace(a.draw,bonus=28))
    f._accept_fast_state(pub.select_result([a,b]))
    assert f.winning_summary['status']=='conflict'
    assert f.winning_summary['results']==[]
    f._accept_fast_state(pub.select_result([a]))
    old=f._frozen_result_snapshot
    f._prediction_snapshot=snapshot(NOW.isoformat())
    f._accept_fast_state(pub.select_result([a]))
    assert f._frozen_result_snapshot==old
    g=Fake();g._restore_fast_state({'fast_result':f._fast_result,'frozen_result_snapshot':old})
    assert g._frozen_result_snapshot==old


def test_current_real_rss_result_minimal_fixture():
    # Actual publisher headline and pubDate captured from its allowed RSS, not
    # full article redistribution and not a measured broadcast-end latency.
    title='1241회 로또 1등 7, 13, 16, 23, 24, 43…보너스 9'
    url='https://www.newsis.com/view/NISX20260912_0003786970'
    when=datetime.fromisoformat('2026-09-12T20:52:05+09:00')
    r=candidate(title=title,url=url,when=when,target=1241,now=when+timedelta(minutes=1))
    assert r.draw.numbers==(7,13,16,23,24,43) and r.draw.bonus==9


def coordinator_method(name):
    """Exercise the production body without replacing the real HA smoke test."""
    import ast
    import logging
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'custom_components/lotto_645/coordinator.py'
    cls=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Lotto645Coordinator')
    body=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),body],type_ignores=[])
    ns={'datetime':datetime,'UTC':UTC,'evaluate_saved':state_mod.evaluate_saved,
        'draw_cutoff':pub.draw_cutoff,'_LOGGER':logging.getLogger('test')}
    exec(compile(ast.fix_missing_locations(module),str(path),'exec'),ns)
    return ns[name]


def test_official_first_also_excludes_late_or_unknown_predictions():
    evaluate=coordinator_method('_evaluate_prediction_snapshot')
    for when,count in [('2026-09-05T10:00:00+00:00',1), (None,0), (NOW.isoformat(),0)]:
        obj=SimpleNamespace(_prediction_snapshot=snapshot(when),history=[candidate().draw],_draw_evaluation=None)
        evaluate(obj)
        assert obj._draw_evaluation['checked_game_count']==count
        assert obj._draw_evaluation['snapshot_policy']=='pre_draw_v1'
    # Migrate a cached v1.9 evaluation instead of preserving an invalid old win.
    obj._draw_evaluation.pop('snapshot_policy')
    obj._draw_evaluation['checked_game_count']=999
    evaluate(obj)
    assert obj._draw_evaluation['checked_game_count']==0


def test_post_cutoff_regeneration_keeps_last_pre_draw_snapshot():
    old=snapshot();new=snapshot(NOW.isoformat())
    obj=SimpleNamespace(_prediction_snapshot=old,_fast_result=None,
                        _build_prediction_snapshot=lambda *args:new,_needs_storage_save=False)
    coordinator_method('_set_prediction_snapshot')(obj,SimpleNamespace(target_round=1240),None,None)
    assert obj._prediction_snapshot is old


def test_corrupt_saved_snapshot_does_not_break_result_display():
    obj=snapshot();obj['based_on_round']='bad'
    assert state_mod.evaluate_saved(obj,candidate().draw)['checked_game_count']==0
    obj=snapshot();obj['recommendations']=None
    assert state_mod.evaluate_saved(obj,candidate().draw)['checked_game_count']==0
