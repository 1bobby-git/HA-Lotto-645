"""Separate final bundle purchase provenance, never a regular formula review row."""
from copy import deepcopy
import re
from .purchased_tickets import parse_ticket


def normalize_links(raw,tickets):
    if not isinstance(raw,dict) or len(raw)>10000:raise ValueError('invalid_final_purchase_links')
    clean={}
    for ticket_id,slots in raw.items():
        if ticket_id not in tickets or not isinstance(slots,dict) or len(slots)>5:raise ValueError('invalid_final_purchase_links')
        games={g['slot']:g for g in tickets[ticket_id]['games']};entries={}
        for slot,link in slots.items():
            if slot not in games or not isinstance(link,dict) or link.get('finalizer_id')!='candidate_covering_recombination':raise ValueError('invalid_final_purchase_source')
            if set(link)!={'finalizer_id','bundle_generation_id','game_id','input_snapshot_hash','numbers'}:raise ValueError('invalid_final_purchase_source')
            if any(not isinstance(link.get(k),str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',link[k]) for k in ('bundle_generation_id','game_id')):raise ValueError('invalid_final_purchase_source')
            if not isinstance(link['input_snapshot_hash'],str) or not re.fullmatch('[a-f0-9]{64}',link['input_snapshot_hash']):raise ValueError('invalid_final_purchase_source')
            if parse_ticket(link['numbers'])!=tuple(games[slot]['numbers']):raise ValueError('final_purchase_numbers_changed')
            entries[slot]=deepcopy(link)
        if entries:clean[ticket_id]=entries
    return clean


from .purchased_tickets import PurchaseBook as OriginalPurchaseBook

class FinalizationPurchaseBook(OriginalPurchaseBook):
    """Add provenance outside legacy ticket rows, preserving their exact contract."""
    def __init__(self):
        super().__init__();self.finalization_links={}

    @classmethod
    def from_storage(cls,payload):
        book=super().from_storage(payload)
        book.finalization_links=normalize_links((payload or {}).get('finalization_links',{}),book.tickets)
        return book

    def to_storage(self):
        payload=super().to_storage()
        if self.finalization_links:payload['finalization_links']=deepcopy(self.finalization_links)
        return payload

    def updated(self,round_no,values,*,finalization_links_by_slot=None,**kwargs):
        previous=self.finalization_links
        result=super().updated(round_no,values,**kwargs)
        # Removed or changed purchased lines cannot retain unrelated evidence.
        clean={}
        for key,ticket in result.tickets.items():
            entries={}
            for game in ticket['games']:
                old=previous.get(key,{}).get(game['slot'])
                same_round=self.tickets.get(key,{}).get('round')==ticket['round']
                if old and same_round and old['numbers']==game['numbers']:entries[game['slot']]=old
            if entries:clean[key]=entries
        if not kwargs.get('clear'):
            key=result.selected_ticket_id;entries=clean.setdefault(key,{})
            for game in result.tickets[key]['games']:
                proposed=(finalization_links_by_slot or {}).get(game['slot'])
                if game['slot'] not in entries and proposed:entries[game['slot']]=proposed
        result.finalization_links=normalize_links(clean,result.tickets)
        return result

    def report(self,history,round_no=None,ticket_id=None):
        result=super().report(history,round_no,ticket_id)
        for game in result.get('games',[]):
            link=self.finalization_links.get(game.get('ticket_id'),{}).get(game.get('slot'))
            if link:game['finalization_ref']=deepcopy(link)
        return result
