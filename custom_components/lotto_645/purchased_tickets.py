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


class PurchaseBook:
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
            games.append({'method_id': f"purchased_{row['slot']}", 'slot': row['slot'],
                          'sensor_name': f"직접 구매 {row['slot']}", 'source': 'purchased',
                          'recommended_numbers': list(row['numbers']), 'numbers': list(row['numbers']), **outcome})
        winners = [game for game in games if game['prize_rank'] is not None]
        return {**base, 'status': 'evaluated' if draw else 'waiting', 'saved_at': record['saved_at'],
                'saved_game_count': len(games), 'checked_game_count': len(games) if draw else 0,
                'winning_game_count': len(winners), 'losing_game_count': len(games) - len(winners) if draw else 0,
                'highest_prize': min(winners, key=lambda game: game['prize_rank'])['prize'] if winners else ('미당첨' if draw else None),
                'winning_numbers': list(draw.numbers) if draw else [], 'bonus_number': draw.bonus if draw else None,
                'games': games}


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
