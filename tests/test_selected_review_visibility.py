"""Selected formulas determine both lists; old records are retained, not erased."""
from copy import deepcopy
from datetime import datetime, UTC
from types import SimpleNamespace
import pytest
from test_analysis_engine import models
from test_panel_live_payload import production_function
from custom_components.lotto_645.const import AI_METHOD_ID
from custom_components.lotto_645.review_selection import review_method_ids, selected_round_review
from custom_components.lotto_645.purchased_tickets import PurchaseBook

SELECTED=('balance_formula','delta_system','uniform_sequential','uniform_combination_rank',
          'calibrated_stratified','uniform_rejection','uniform_floyd','bayesian_shrinkage',
          'selected_median_consensus','ac_range_filter')
STORED=(*SELECTED,'personal_lucky',*(f'old_{i}' for i in range(11)),AI_METHOD_ID)
STAMP='2026-09-16T10:00:00+00:00'

def owner_for(ids=SELECTED,ai=True):
    rows=[{'method_id':key,'label':key,'numbers':[1,2,3,4,5,6], 'target_round':1242,
           'generated_at':STAMP,'generation_id':'saved-'+key,'review_score':None,'prize_rank':None}
          for key in STORED]
    report={'round':1242,'status':'waiting','methods':rows,'peer_count':len(rows)}
    recs=tuple(models.Recommendation(i,key,key,'local',(1,2,3,4,5,6),'',None,
               {'target_round':1242,'generation_id':'saved-'+key}) for i,key in enumerate(STORED,1))
    owner=SimpleNamespace(configured_method_ids=ids,ai_enabled=ai,_review_summaries={key:{} for key in STORED},
        review_for_method=lambda key:{'reviewed_rounds':0},review_for_round=lambda _:report,
        result_draw=None,purchase_book=PurchaseBook(),result_metadata={'status':'official_history'},
        result_round=1241,result_history=[],winning_summary={'round':1241,'results':[]},
        data=SimpleNamespace(analysis=models.AnalysisResult(1242,1241,recs,{}),
            generated_at=datetime(2026,9,16,10,tzinfo=UTC),ai_recommendation=None),
        entry=SimpleNamespace(entry_id='test'),purchase_storage_error=False,local_generation_sequence=1)
    return owner,report

def render(owner):
    rows=production_function('_review_rows',{})
    fn=production_function('_view',{'Any':object,'_review_rows':rows,
        'panel_metadata':lambda *args:{'draw_schedule':{'round':1242}}})
    return fn(owner)

def test_23_saved_methods_show_only_10_selected_and_enabled_ai():
    owner,stored=owner_for();before=deepcopy(stored)
    view=render(owner);expected=[*SELECTED,AI_METHOD_ID]
    assert len(STORED)==23
    assert view['selected_method_ids']==expected
    assert [r['method_id'] for r in view['reviews']]==expected
    assert [r['method_id'] for r in view['review_round']['methods']]==expected
    assert [r['method_id'] for r in view['recommendations']]==expected
    assert view['review_round']['peer_count']==11
    assert stored==before and len(owner._review_summaries)==23
    assert all(r['review_score'] is None for r in view['review_round']['methods'])

@pytest.mark.parametrize('ids,ai,expected',[(SELECTED,False,list(SELECTED)),((),False,[]),((),True,[AI_METHOD_ID])])
def test_disabling_ai_or_clearing_selection_never_restores_hidden_history(ids,ai,expected):
    owner,stored=owner_for(ids,ai);view=render(owner)
    for group in (view['reviews'],view['review_round']['methods'],view['recommendations']):
        assert [r['method_id'] for r in group]==expected
    assert view['review_round']['peer_count']==len(expected) and len(stored['methods'])==23

def test_reselect_restores_same_saved_numbers_without_mutating_history():
    owner,stored=owner_for();before=deepcopy(stored)
    initial=render(owner)['review_round']['methods']
    owner.configured_method_ids=SELECTED[:2];owner.ai_enabled=False
    assert len(render(owner)['review_round']['methods'])==2
    owner.configured_method_ids=SELECTED;owner.ai_enabled=True
    assert render(owner)['review_round']['methods']==initial
    assert stored==before

def test_visible_rank_and_peer_count_agree_without_changing_stored_ranks():
    stored={'round':1242,'status':'confirmed','peer_count':4,'methods':[
        {'method_id':k,'review_score':score,'rank_this_round':rank,'numbers':[1,2,3,4,5,6]}
        for k,score,rank in [('hidden',100,1),('a',30,2),('b',30,2),('c',10,4)]]}
    before=deepcopy(stored);view=selected_round_review(stored,('a','b','c'))
    assert view['peer_count']==3
    assert [r['rank_this_round'] for r in view['methods']]==[1,1,3]
    assert [r['review_score'] for r in view['methods']]==[30,30,10]
    assert stored==before

def test_selected_without_saved_numbers_is_not_fabricated_or_substituted():
    owner,stored=owner_for(('myungri_hetu_day_pillar',),False)
    view=render(owner)
    assert view['selected_method_ids']==['myungri_hetu_day_pillar']
    assert len(view['reviews'])==1 and view['review_round']['methods']==[]
    assert view['recommendations']==[] and len(stored['methods'])==23
