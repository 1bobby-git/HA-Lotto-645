from copy import deepcopy
import pytest
from test_analysis_engine import models
from custom_components.lotto_645.purchased_tickets import PurchaseBook
from custom_components.lotto_645.finalization_purchase import FinalizationPurchaseBook

def link(bundle='bundle-1'):
    return {'finalizer_id':'candidate_covering_recombination','bundle_generation_id':bundle,
            'game_id':'g01','input_snapshot_hash':'a'*64,'numbers':[1,2,3,4,5,6]}

def test_purchase_provenance_is_separate_and_immutable():
    book=FinalizationPurchaseBook()
    assert book.to_storage()==PurchaseBook().to_storage()
    first=book.updated(1243,{'game_a':'1 2 3 4 5 6'},new_ticket=True,ticket_id='ticket-1',finalization_links_by_slot={'A':link()})
    assert len(first.tickets)==1
    assert first.finalization_links['ticket-1']['A']['bundle_generation_id']=='bundle-1'
    assert 'formula_links' not in first.tickets['ticket-1']['games'][0]
    nextbook=first.updated(1243,{'game_a':'1 2 3 4 5 6'},ticket_id='ticket-1',finalization_links_by_slot={'A':link('bundle-new')})
    assert nextbook.finalization_links==first.finalization_links
    restored=FinalizationPurchaseBook.from_storage(deepcopy(nextbook.to_storage()))
    assert restored.finalization_links==first.finalization_links
    legacy=PurchaseBook.from_storage(restored.to_storage())
    assert legacy.tickets==nextbook.tickets
    cleared=restored.updated(1243,{},clear=True,ticket_id='ticket-1')
    assert not cleared.finalization_links

def test_changed_numbers_do_not_keep_wrong_bundle_link():
    first=FinalizationPurchaseBook().updated(1243,{'game_a':'1 2 3 4 5 6'},new_ticket=True,ticket_id='ticket-1',finalization_links_by_slot={'A':link()})
    changed=first.updated(1243,{'game_a':'7 8 9 10 11 12'},ticket_id='ticket-1')
    assert not changed.finalization_links
    with pytest.raises(ValueError):
        first.updated(1243,{'game_a':'7 8 9 10 11 12'},ticket_id='ticket-1',finalization_links_by_slot={'A':link()})

def test_changed_round_cannot_reuse_prior_provenance():
    first=FinalizationPurchaseBook().updated(1243,{'game_a':'1 2 3 4 5 6'},new_ticket=True,ticket_id='ticket-1',finalization_links_by_slot={'A':link()})
    from custom_components.lotto_645.purchased_tickets import PurchaseInputError
    with pytest.raises(PurchaseInputError):
        first.updated(1244,{'game_a':'1 2 3 4 5 6'},ticket_id='ticket-1')
    assert first.finalization_links['ticket-1']['A']==link()
