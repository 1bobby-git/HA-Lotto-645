"""Public release boundary and multi-ticket migration regressions."""
from pathlib import Path
from datetime import UTC,datetime
import json
import pytest
from test_analysis_engine import models,ROOT
from custom_components.lotto_645.purchased_tickets import PurchaseBook,PurchaseInputError
from custom_components.lotto_645.service_contract import Catalog
from custom_components.lotto_645.review import ReviewBook

R=ROOT/'custom_components/lotto_645'
GOOD='1 2 3 4 5 6'

def test_no_private_code_in_component():
    assert not any(p.is_file() for p in (R/'lotto_core').rglob('*'))  # Git does not track empty directories
    for name in ('analysis','sampling','consensus','voting_consensus','saju_rules','formula_cache','formula_settings'):
        assert not (R/(name+'.py')).exists()
    for p in R.glob('*.py'):
        assert 'from .lotto_core' not in p.read_text()
    assert json.loads((R/'manifest.json').read_text())['requirements']==[]
    assert len(Catalog.parse(json.loads((R/'catalog_seed.json').read_text())).methods)==22

def test_legacy_ticket_migration_multiple_slips_and_idempotency():
    old={'version':1,'selected_round':40,'records':{'40':{'round':40,'saved_at':'2026-09-16T00:00:00+00:00',
        'games':[{'slot':'A','numbers':[1,2,3,4,5,6]}]}}}
    book=PurchaseBook.from_storage(old)
    assert book.selected_ticket_id=='legacy-40'
    book=book.updated(40,{'game_a':GOOD},new_ticket=True,ticket_id='test-slip-2')
    assert len(book.tickets)==2
    duplicate=book.updated(40,{'game_a':GOOD},new_ticket=True,ticket_id='test-slip-2')
    assert duplicate.to_storage()==book.to_storage()
    restored=PurchaseBook.from_storage(json.loads(json.dumps(book.to_storage())))
    report=restored.report([models.LottoDraw(40,'2003-09-06',(1,2,3,4,5,6),7)],40)
    assert report['winning_game_count']==2
    changed=book.updated(40,{},clear=True,ticket_id='test-slip-2')
    assert list(changed.tickets)==['legacy-40']
    assert changed.form_values(40)=={'game_a':'1, 2, 3, 4, 5, 6'}
    assert old['records']['40']['games'][0]['numbers']==[1,2,3,4,5,6]

def test_same_request_different_wallet_payload_is_rejected():
    book=PurchaseBook().updated(40,{'game_a':GOOD},new_ticket=True,ticket_id='same-request')
    with pytest.raises(PurchaseInputError):
        book.updated(40,{'game_a':'8 9 10 11 12 13'},new_ticket=True,ticket_id='same-request')

def test_actual_review_keeps_core_provenance():
    stamp='2026-09-16T01:00:00+00:00';book=ReviewBook()
    snapshot={'target_round':1242,'based_on_round':1241,'local_generated_at':stamp,
      'recommendations':[{'method_id':'uniform_fisher_yates','numbers':[1,2,3,4,5,6],
        'source':'core_service','label':'example','details':{'core_version':'1.22.1','formula_version':'1','generation_id':'test-id'}}]}
    assert book.record_snapshot(snapshot,now=datetime(2026,9,16,2,tzinfo=UTC))
    restored=ReviewBook.from_storage(book.to_storage())
    assert restored.rounds['1242']['predictions']['uniform_fisher_yates']['core_version']=='1.22.1'
