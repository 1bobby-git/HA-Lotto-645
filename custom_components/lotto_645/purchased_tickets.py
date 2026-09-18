"""Local, round-scoped records of self-reported purchased Lotto tickets.

This is a number checker, not a purchase service or proof of ownership. The
book never participates in recommendation scoring, AI prompts or mirror data.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import re
import unicodedata
from typing import Any, Iterable

from .models import LottoDraw
from .result_evaluator import evaluate_ticket

SLOTS = tuple('ABCDE')


class PurchaseInputError(ValueError):
    """Validation error with a frontend field, without embedding ticket content."""

    def __init__(self, field: str, code: str) -> None:
        super().__init__(code)
        self.field, self.code = field, code


def parse_round(value: object) -> int:
    text = str(value).strip()
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,6}', text):
        raise PurchaseInputError('purchase_round', 'invalid_purchase_round')
    result = int(text)
    if result < 1:
        raise PurchaseInputError('purchase_round', 'invalid_purchase_round')
    return result


def parse_ticket(value: object, field: str = 'base') -> tuple[int, ...]:
    """Accept six separated numbers, or twelve zero-padded digits; never guess."""
    if isinstance(value, str):
        text = unicodedata.normalize('NFKC', value).strip()
        if re.fullmatch(r'[0-9]{12}', text):
            raw = [text[i:i + 2] for i in range(0, 12, 2)]
        elif re.fullmatch(r'[0-9]{1,2}(?:[\s,;/]+[0-9]{1,2}){5}', text):
            raw = re.split(r'[\s,;/]+', text)
        else:
            raise PurchaseInputError(field, 'invalid_purchase_numbers')
        numbers = tuple(int(n) for n in raw)
    elif isinstance(value, (tuple, list)) and all(type(n) is int for n in value):
        numbers = tuple(value)
    else:
        raise PurchaseInputError(field, 'invalid_purchase_numbers')
    if len(numbers) != 6 or len(set(numbers)) != 6 or any(not 1 <= n <= 45 for n in numbers):
        raise PurchaseInputError(field, 'invalid_purchase_numbers')
    return tuple(sorted(numbers))


def parse_games(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep A–E identity; identical numbers on different purchased lines are valid."""
    fields = {f'game_{slot.lower()}' for slot in SLOTS}
    if any(key.startswith('game_') and key not in fields for key in values):
        raise PurchaseInputError('base', 'purchase_game_limit')
    games = []
    for slot in SLOTS:
        field = f'game_{slot.lower()}'
        value = values.get(field, '')
        if value is None or isinstance(value, str) and not value.strip():
            continue
        games.append({'slot': slot, 'numbers': list(parse_ticket(value, field))})
    if not games:
        raise PurchaseInputError('base', 'purchase_games_required')
    return games


def _formula_link(value: object, round_no: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError('invalid_formula_link')
    formula_id = value.get('formula_id')
    label = value.get('formula_label')
    source = value.get('source', 'core_service')
    generated_at = value.get('generated_at')
    based_on_round = value.get('based_on_round')
    target_round = value.get('target_round', round_no)
    generation_sequence = value.get('generation_sequence', 0)
    if (not isinstance(formula_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', formula_id)
            or not isinstance(label, str) or not 1 <= len(label) <= 180
            or not isinstance(source, str) or not 1 <= len(source) <= 40
            or type(based_on_round) is not int or not 0 < based_on_round < round_no
            or type(target_round) is not int or target_round != round_no
            or type(generation_sequence) is not int or generation_sequence < 0):
        raise ValueError('invalid_formula_link')
    when = datetime.fromisoformat(str(generated_at))
    if when.tzinfo is None:
        raise ValueError('invalid_formula_link_timestamp')
    result = {
        'formula_id': formula_id,
        'formula_label': label,
        'source': source,
        'generated_at': when.isoformat(),
        'based_on_round': based_on_round,
        'target_round': round_no,
        'generation_sequence': generation_sequence,
    }
    for key in ('formula_version', 'core_version', 'generation_id'):
        raw = value.get(key)
        if raw is not None:
            raw = str(raw)
            if not 1 <= len(raw) <= 128:
                raise ValueError('invalid_formula_link')
            result[key] = raw
    return result


def normalize_formula_links(value: object, round_no: int) -> list[dict[str, Any]]:
    if value in (None, []):
        return []
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError('invalid_formula_links')
    result = []
    seen = set()
    for raw in value:
        item = _formula_link(raw, round_no)
        identity = (
            item['formula_id'], item.get('generation_id'), item['generated_at'],
            item['generation_sequence'],
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result


def _merge_formula_links(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for group in groups:
        for item in group:
            identity = (
                item['formula_id'], item.get('generation_id'), item['generated_at'],
                item['generation_sequence'],
            )
            if identity in seen:
                continue
            seen.add(identity)
            result.append(deepcopy(item))
    return result


def matching_purchase_games(
    book: "PurchaseBook", round_no: int | None, numbers: Iterable[int]
) -> list[dict[str, Any]]:
    """Return purchased lines whose six numbers exactly match in the same round."""
    if round_no is None:
        return []
    try:
        target_round = parse_round(round_no)
        canonical = parse_ticket(list(numbers), "numbers")
    except (PurchaseInputError, TypeError):
        return []

    matches: list[dict[str, Any]] = []
    ticket_number = 0
    for ticket in book.tickets.values():
        if ticket["round"] != target_round:
            continue
        ticket_number += 1
        for game in ticket["games"]:
            if tuple(game["numbers"]) != canonical:
                continue
            matches.append(
                {
                    "ticket_id": ticket["ticket_id"],
                    "ticket_number": ticket_number,
                    "slot": game["slot"],
                    "numbers": list(canonical),
                }
            )
    return matches


class _LegacyPurchaseBook:
    """Five lines per draw; rounds are retained until the user explicitly deletes."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.selected_round: int | None = None

    @classmethod
    def from_storage(cls, payload: object) -> 'PurchaseBook':
        book = cls()
        if payload is None:
            return book
        if not isinstance(payload, dict) or payload.get('version') != 1 or not isinstance(payload.get('records'), dict):
            raise ValueError('Invalid purchase storage; refusing to overwrite')
        for key, record in payload['records'].items():
            round_no = parse_round(key)
            if not isinstance(record, dict) or str(round_no) != key or type(record.get('round')) is not int or record['round'] != round_no:
                raise ValueError('Invalid purchase record round')
            rows = record.get('games')
            if not isinstance(rows, list) or not 1 <= len(rows) <= 5:
                raise ValueError('Invalid purchase record lines')
            slots = [row.get('slot') if isinstance(row, dict) else None for row in rows]
            if len(set(slots)) != len(slots) or any(slot not in SLOTS for slot in slots):
                raise ValueError('Invalid purchase record slots')
            saved_at = datetime.fromisoformat(record['saved_at'])
            if saved_at.tzinfo is None:
                raise ValueError('Purchase save timestamp must have a timezone')
            book.records[str(round_no)] = {
                'round': round_no, 'saved_at': saved_at.isoformat(),
                'games': [{'slot': row['slot'], 'numbers': list(parse_ticket(row['numbers']))} for row in rows],
            }
        selected = payload.get('selected_round')
        if selected is not None:
            book.selected_round = parse_round(selected)
        if str(book.selected_round) not in book.records:
            book.selected_round = max(map(int, book.records), default=None)
        return book

    def to_storage(self) -> dict[str, Any]:
        return {'version': 1, 'selected_round': self.selected_round, 'records': deepcopy(self.records)}

    def updated(self, round_no: int, values: dict[str, Any], *, clear: bool = False,
                now: datetime | None = None) -> 'PurchaseBook':
        round_no = parse_round(round_no)
        result = self.from_storage(self.to_storage())
        if clear:
            result.records.pop(str(round_no), None)
            result.selected_round = max(map(int, result.records), default=None)
        else:
            games = parse_games(values)  # validate ALL rows before applying any change
            when = now or datetime.now(UTC)
            if when.tzinfo is None:
                raise ValueError('Save timestamp must have a timezone')
            result.records[str(round_no)] = {'round': round_no, 'saved_at': when.isoformat(), 'games': games}
            result.selected_round = round_no
        return result

    def form_values(self, round_no: int) -> dict[str, str]:
        record = self.records.get(str(round_no), {})
        return {f"game_{row['slot'].lower()}": ', '.join(map(str, row['numbers'])) for row in record.get('games', [])}

    def report(self, history: Iterable[LottoDraw], round_no: int | None = None) -> dict[str, Any]:
        round_no = self.selected_round if round_no is None else round_no
        record = self.records.get(str(round_no))
        base = {'round': round_no, 'saved_rounds': sorted(map(int, self.records)),
                'purchase_verified': False,
                'notice': '사용자가 입력한 구매번호 대조입니다. 실제 구매·지급은 복권 원본과 공식 결과로 확인하세요.'}
        if record is None:
            return {**base, 'status': 'not_registered', 'games': [], 'checked_game_count': 0,
                    'winning_game_count': 0, 'losing_game_count': 0}
        draw = next((draw for draw in history if draw.round == round_no), None)
        games = []
        for row in record['games']:
            outcome = (evaluate_ticket(tuple(row['numbers']), draw) if draw else
                       {'status': '판정 대기', 'prize': None, 'prize_rank': None,
                        'main_match_count': None, 'matched_main_numbers': [], 'bonus_match': None})
            links = deepcopy(row.get('formula_links', []))
            applied_ids = list(dict.fromkeys(
                link.get('formula_id') for link in links if link.get('formula_id')
            ))
            applied_labels = list(dict.fromkeys(
                link.get('formula_label') or link.get('formula_id')
                for link in links if link.get('formula_label') or link.get('formula_id')
            ))
            games.append({'method_id': f"purchased_{row['slot']}", 'slot': row['slot'],
                          'sensor_name': f"직접 구매 {row['slot']}", 'source': 'purchased',
                          'recommended_numbers': list(row['numbers']), 'numbers': list(row['numbers']),
                          'formula_links': links, 'formula_match_count': len(links),
                          'applied_formula_ids': applied_ids,
                          'applied_formula_labels': applied_labels, **outcome})
        winners = [game for game in games if game['prize_rank'] is not None]
        return {**base, 'status': 'evaluated' if draw else 'waiting', 'saved_at': record['saved_at'],
                'saved_game_count': len(games), 'checked_game_count': len(games) if draw else 0,
                'winning_game_count': len(winners), 'losing_game_count': len(games) - len(winners) if draw else 0,
                'highest_prize': min(winners, key=lambda game: game['prize_rank'])['prize'] if winners else ('미당첨' if draw else None),
                'winning_numbers': list(draw.numbers) if draw else [], 'bonus_number': draw.bonus if draw else None,
                'games': games}


class PurchaseBook:
    """Ticket IDs separate multiple physical slips; legacy round records remain readable."""
    def __init__(self):
        self.tickets = {}
        self.selected_round = None
        self.selected_ticket_id = None

    @property
    def records(self):
        result={}
        for ticket in self.tickets.values():
            result[str(ticket['round'])]={k:deepcopy(v) for k,v in ticket.items() if k in ('round','saved_at','games')}
        selected=self.tickets.get(self.selected_ticket_id)
        if selected:
            result[str(selected['round'])]={k:deepcopy(v) for k,v in selected.items() if k in ('round','saved_at','games')}
        return result

    @classmethod
    def from_storage(cls,payload):
        book=cls()
        if payload is None:return book
        if not isinstance(payload,dict):raise ValueError('invalid_purchase_storage')
        if payload.get('version')==1:
            old=_LegacyPurchaseBook.from_storage(payload)
            for key,row in old.records.items():
                ticket_id='legacy-'+key
                book.tickets[ticket_id]={'ticket_id':ticket_id,**deepcopy(row)}
            book.selected_round=old.selected_round
            book.selected_ticket_id='legacy-'+str(old.selected_round) if old.selected_round else None
        elif payload.get('version') in (2,3):
            version=payload['version']
            tickets=payload.get('tickets')
            if not isinstance(tickets,dict) or len(tickets)>10000:
                raise ValueError('invalid_ticket_storage')
            for key,row in tickets.items():
                if (not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}',key)
                    or not isinstance(row,dict) or row.get('ticket_id')!=key):
                    raise ValueError('invalid_ticket_id')
                number=parse_round(row.get('round'))
                valid=_LegacyPurchaseBook.from_storage({'version':1,'records':{str(number):row},'selected_round':number})
                clean={'ticket_id':key,**valid.records[str(number)]}
                if version==3:
                    original_games=row.get('games',[])
                    for clean_game, raw_game in zip(clean['games'], original_games, strict=True):
                        links=normalize_formula_links(raw_game.get('formula_links',[]),number)
                        if links:
                            clean_game['formula_links']=links
                book.tickets[key]=clean
            book.selected_round=payload.get('selected_round')
            book.selected_ticket_id=payload.get('selected_ticket_id')
            if book.selected_ticket_id is not None and book.selected_ticket_id not in book.tickets:
                raise ValueError('invalid_selected_ticket')
            # The backward-readable index must agree, not silently hide a corrupt record.
            if payload.get('records')!=book.records:
                raise ValueError('purchase_index_mismatch')
        else:raise ValueError('unsupported_purchase_storage')
        return book

    def to_storage(self):
        return {'version':3,'tickets':deepcopy(self.tickets),'records':self.records,
                'selected_round':self.selected_round,'selected_ticket_id':self.selected_ticket_id}

    def ticket_record(self,round_no,ticket_id=None):
        if ticket_id:
            row=self.tickets.get(ticket_id)
            if row is None or row['round']!=round_no:
                raise PurchaseInputError('base','invalid_ticket_id')
            return row
        current=self.tickets.get(self.selected_ticket_id)
        if current and current['round']==round_no:return current
        return next((r for r in reversed(list(self.tickets.values())) if r['round']==round_no),{})

    def updated(self,round_no,values,*,clear=False,now=None,ticket_id=None,new_ticket=False,
                formula_links_by_slot=None):
        from uuid import uuid4
        round_no=parse_round(round_no)
        result=self.from_storage(self.to_storage())
        if clear:
            if ticket_id:
                result.ticket_record(round_no,ticket_id)
                result.tickets.pop(ticket_id)
            else:
                result.tickets={k:v for k,v in result.tickets.items() if v['round']!=round_no}
            if result.selected_ticket_id not in result.tickets:
                result.selected_ticket_id=next(reversed(result.tickets),None)
            result.selected_round=result.tickets[result.selected_ticket_id]['round'] if result.selected_ticket_id else None
            return result
        games=parse_games(values)
        when=now or datetime.now(UTC)
        if when.tzinfo is None:raise ValueError('timezone_required')
        if len(result.tickets)>=10000 and new_ticket:
            raise PurchaseInputError('base','purchase_storage_limit')
        if new_ticket and ticket_id:
            if not re.fullmatch(r'[a-zA-Z0-9-]{1,80}',ticket_id):
                raise PurchaseInputError('base','invalid_ticket_id')
            existing=result.tickets.get(ticket_id)
            if existing:
                comparable=[{'slot':row['slot'],'numbers':list(row['numbers'])} for row in existing['games']]
                if existing['round']!=round_no or comparable!=games:
                    raise PurchaseInputError('base','purchase_revision_conflict')
                result.selected_ticket_id=ticket_id;result.selected_round=round_no
                return result
        previous={} if new_ticket else result.ticket_record(round_no,ticket_id)
        previous_by_numbers={}
        for old_game in previous.get('games',[]):
            links=normalize_formula_links(old_game.get('formula_links',[]),round_no)
            if links:
                previous_by_numbers.setdefault(tuple(old_game['numbers']),[]).extend(links)
        provided=formula_links_by_slot or {}
        if not isinstance(provided,dict):
            raise ValueError('invalid_formula_links')
        enriched=[]
        for game in games:
            current=normalize_formula_links(provided.get(game['slot'],[]),round_no)
            retained=previous_by_numbers.get(tuple(game['numbers']),[])
            links=_merge_formula_links(retained,current)
            copy=deepcopy(game)
            if links:
                copy['formula_links']=links
            enriched.append(copy)
        key=previous.get('ticket_id') or (ticket_id if new_ticket else None) or str(uuid4())
        result.tickets[key]={'ticket_id':key,'round':round_no,'saved_at':when.isoformat(),'games':enriched}
        result.selected_ticket_id=key;result.selected_round=round_no
        return result

    def with_review_formula_links(self, review_rounds: object) -> 'PurchaseBook':
        """Backfill only exact, evidenced pre-draw formula matches from ReviewBook."""
        if not isinstance(review_rounds, dict):
            return self.from_storage(self.to_storage())
        result = self.from_storage(self.to_storage())
        for ticket in result.tickets.values():
            round_no = ticket["round"]
            review = review_rounds.get(str(round_no))
            predictions = review.get("predictions") if isinstance(review, dict) else None
            if not isinstance(predictions, dict):
                continue
            for game in ticket["games"]:
                discovered = []
                for formula_id, prediction in predictions.items():
                    if not isinstance(formula_id, str) or not isinstance(prediction, dict):
                        continue
                    try:
                        if parse_ticket(prediction.get("numbers")) != tuple(game["numbers"]):
                            continue
                        raw = {
                            "formula_id": formula_id,
                            "formula_label": str(prediction.get("label", formula_id))[:180],
                            "source": str(prediction.get("source", "analysis"))[:40],
                            "generated_at": prediction.get("generated_at"),
                            "based_on_round": prediction.get("based_on_round"),
                            "target_round": round_no,
                            "generation_sequence": 0,
                        }
                        for key in ("formula_version", "core_version", "generation_id"):
                            if prediction.get(key) is not None:
                                raw[key] = prediction[key]
                        discovered.append(_formula_link(raw, round_no))
                    except (PurchaseInputError, TypeError, ValueError):
                        continue
                links = _merge_formula_links(
                    normalize_formula_links(game.get("formula_links", []), round_no),
                    discovered,
                )
                if links:
                    game["formula_links"] = links
        return result

    def form_values(self,round_no,ticket_id=None):
        row=self.ticket_record(round_no,ticket_id)
        return {f"game_{r['slot'].lower()}":', '.join(map(str,r['numbers'])) for r in row.get('games',[])}

    def report(self,history,round_no=None,ticket_id=None):
        round_no=self.selected_round if round_no is None else round_no
        selected=([self.ticket_record(round_no,ticket_id)] if ticket_id else
                  [r for r in self.tickets.values() if r['round']==round_no])
        legacy=_LegacyPurchaseBook();legacy.selected_round=round_no
        if not selected:
            report=legacy.report(history,round_no)
        else:
            reports=[]
            for ticket in selected:
                legacy.records={str(round_no):ticket}
                report=legacy.report(history,round_no)
                for row in report['games']:
                    row['ticket_id']=ticket['ticket_id']
                    if len(selected)>1:
                        row['method_id']=row['method_id']+'_'+ticket['ticket_id']
                reports.append(report)
            report=reports[-1]
            if len(reports)>1:
                report['games']=[row for item in reports for row in item['games']]
                for field in ('saved_game_count','checked_game_count','winning_game_count','losing_game_count'):
                    report[field]=sum(item.get(field,0) for item in reports)
                winners=[r for r in report['games'] if r.get('prize_rank')]
                report['highest_prize']=min(winners,key=lambda r:r['prize_rank'])['prize'] if winners else ('미당첨' if report['status']=='evaluated' else None)
        report['saved_rounds']=sorted(map(int,self.records))
        report['ticket_count']=len(selected)
        return report

def combined_result(draw: LottoDraw, recommendation_result: dict[str, Any] | None,
                    purchased_result: dict[str, Any]) -> dict[str, Any]:
    """Combine only matching rounds; absence of tickets is never a losing ticket."""
    recommendation_result = recommendation_result or {}
    recommended = recommendation_result.get('results', []) if recommendation_result.get('round') == draw.round else []
    purchased = purchased_result.get('games', []) if purchased_result.get('round') == draw.round and purchased_result.get('status') == 'evaluated' else []
    results = [*deepcopy(recommended), *deepcopy(purchased)]
    winners = [row for row in results if row.get('prize_rank') is not None]
    highest = min(winners, key=lambda row: row['prize_rank']) if winners else None
    return {'round': draw.round, 'draw_date': draw.draw_date,
            'winning_numbers': list(draw.numbers), 'bonus_number': draw.bonus,
            'status': 'evaluated' if results else 'no_saved_tickets',
            'checked_game_count': len(results), 'winning_game_count': len(winners),
            'losing_game_count': len(results) - len(winners),
            'highest_prize': highest['prize'] if highest else ('미당첨' if results else None),
            'highest_prize_sensor': highest['sensor_name'] if highest else None,
            'recommendation_game_count': len(recommended), 'purchased_game_count': len(purchased),
            'recommendation_winning_count': sum(row.get('prize_rank') is not None for row in recommended),
            'purchased_winning_count': sum(row.get('prize_rank') is not None for row in purchased),
            'results': results, 'winners': winners,
            'losers': [row for row in results if row.get('prize_rank') is None],
            'prediction_based_on_round': recommendation_result.get('prediction_based_on_round') if recommended else None,
            'purchased_saved_at': purchased_result.get('saved_at') if purchased else None,
            'prediction_generation_sequence': recommendation_result.get('prediction_generation_sequence') if recommended else None,
            'prediction_generated_at': recommendation_result.get('prediction_generated_at') if recommended else None,
            'evaluated_at': recommendation_result.get('evaluated_at') if recommended else None,
            'message': '추천번호와 직접 구매번호는 별도 집계합니다. 실제 구매·당첨금 지급은 확인하지 않습니다.'}
