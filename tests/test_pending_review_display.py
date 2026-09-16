"""Round isolation and persisted pending review; no API or HA credentials."""
from datetime import datetime, UTC
from types import SimpleNamespace
from test_analysis_engine import models
from test_panel_live_payload import production_function
from custom_components.lotto_645.review import ReviewBook
from custom_components.lotto_645.purchased_tickets import PurchaseBook

STAMP='2026-09-16T10:00:00+00:00'
NOW=datetime(2026,9,16,12,tzinfo=UTC)
def pending():
    book=ReviewBook()
    snapshot={'target_round':1242,'based_on_round':1241,'local_generated_at':STAMP,
              'recommendations':[{'method_id':'uniform_floyd','label':'공식',
                  'numbers':[1,2,3,4,5,6],'source':'core_service',
                  'details':{'core_version':'1.22.1','generation_id':'saved-example'}}]}
    assert book.record_snapshot(snapshot,now=NOW)
    return book

def test_pending_numbers_survive_reload_without_rating():
    book=ReviewBook.from_storage(pending().to_storage())
    review=book.round_review(1242)
    assert review['status']=='waiting' and len(review['methods'])==1
    row=review['methods'][0]
    assert row['numbers']==[1,2,3,4,5,6] and row['generation_id']=='saved-example'
    assert row['review_score'] is None and row['prize_rank'] is None
    assert row['counts_toward_rating'] is False
    assert book.summary('uniform_floyd')['reviewed_rounds']==0

def test_only_matching_draw_changes_pending_into_result():
    book=pending()
    old=models.LottoDraw(1241,'2026-09-12',(1,2,3,4,5,6),7)
    assert not book.set_result(old,confirmed=True,status='official_history')
    assert book.round_review(1242)['status']=='waiting'
    draw=models.LottoDraw(1242,'2026-09-19',(1,2,3,4,5,6),7)
    assert book.set_result(draw,confirmed=True,status='official_history')
    assert not book.set_result(draw,confirmed=True,status='official_history')
    assert book.round_review(1242)['methods'][0]['prize_rank']==1
    assert book.summary('uniform_floyd')['reviewed_rounds']==1

def view_for(target):
    rec=models.Recommendation(1,'uniform_floyd','공식','local',(1,2,3,4,5,6),'',None,{'target_round':target})
    owner=SimpleNamespace(result_draw=None,purchase_book=PurchaseBook(),result_metadata={'status':'official_history'},
        result_round=1241,data=SimpleNamespace(analysis=models.AnalysisResult(target,target-1,(rec,),{}),
        generated_at=NOW,ai_recommendation=None),result_history=[],winning_summary={'round':1241,'results':[]},
        entry=SimpleNamespace(entry_id='example'),purchase_storage_error=False,
        review_for_round=pending().round_review,local_generation_sequence=1,
        configured_method_ids=('uniform_floyd',),ai_enabled=False)
    namespace={'Any':object,'_review_rows':lambda _:[],
               'panel_metadata':lambda *args:{'draw_schedule':{'round':1242}}}
    return production_function('_view',namespace)(owner)

def test_current_review_is_not_previous_published_result():
    view=view_for(1242)
    assert view['review_round']['round']==1242 and view['review_round']['methods']
    assert view['result_round']==1241 and len(view['recommendations'])==1

def test_stale_numbers_are_not_relabelled_as_current():
    view=view_for(1241)
    assert view['recommendation_target']==1242 and view['recommendations']==[]
    assert view['recommendation_record_target']==1241
