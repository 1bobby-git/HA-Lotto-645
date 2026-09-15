"""Bounded, auditable winning simulations; never reconstruct unstored numbers."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import LottoDraw
from .result_evaluator import evaluate_ticket

MAX_HIT_HISTORY = 100
OUTCOME_FIELDS = ('main_match_count', 'matched_main_numbers', 'bonus_match',
                  'matched_bonus_number', 'prize_rank', 'prize')


def hit_event(result: dict, row: dict, run: int) -> dict[str, Any]:
    """Capture a winning game using this cycle's global execution number."""
    match = row['main_match_count']
    if type(run) is not int or run < 1 or type(match) is not int or not 3 <= match <= 6:
        raise ValueError('invalid hit history event')
    target = result['target_round']
    if type(target) is not int or target < 1:
        raise ValueError('invalid hit target')
    event = {'run': run, 'round': target, 'generated_at': str(result.get('generated_at', ''))[:80],
             'main_match_count': match, 'details_available': False}
    # v1.16/17 recent summaries contain counts only. Null/absent numbers are
    # explicitly unavailable, never inferred from a formula or another run.
    if row.get('recommended_numbers') is None and result.get('draw') is None:
        return event
    if type(result['draw'].get('round')) is not int or type(result['draw'].get('bonus')) is not int:
        raise ValueError('invalid hit draw types')
    draw = LottoDraw.from_storage(result['draw'])
    if draw.round != target:
        raise ValueError('hit draw differs from target')
    numbers = row['recommended_numbers']
    if not isinstance(numbers, (list, tuple)):
        raise ValueError('invalid hit numbers')
    if not isinstance(row.get('matched_main_numbers'), list) or any(type(n) is not int for n in row['matched_main_numbers']):
        raise ValueError('invalid matched hit number types')
    outcome = evaluate_ticket(tuple(numbers), draw)
    if any(type(row.get(k)) is not type(outcome[k]) or row[k] != outcome[k] for k in OUTCOME_FIELDS):
        raise ValueError('hit numbers and outcome disagree')
    return {**event, **{k: outcome[k] for k in OUTCOME_FIELDS}, 'details_available': True,
            'recommended_numbers': sorted(numbers),
            'winning_numbers': list(draw.numbers), 'bonus_number': draw.bonus,
            'draw_date': draw.draw_date}


def migrate_hits(payload: dict, method_id: str) -> list[dict]:
    """Recover only known run/count metadata plus the one exact saved result."""
    recovered = {}
    for batch in payload.get('recent', []):
        if not isinstance(batch, dict):
            continue
        run, target = batch.get('run'), batch.get('round')
        if type(run) is not int or not 1 <= run <= payload['total_runs'] or type(target) is not int or target < 1:
            continue
        for raw in batch.get('methods', []):
            if not isinstance(raw, dict):
                continue
            match = raw.get('match')
            if raw.get('method_id') == method_id and type(match) is int and 3 <= match <= 6:
                recovered[run] = hit_event({'target_round': target, 'generated_at': batch.get('generated_at', '')},
                                           {'main_match_count': match}, run)
    latest = payload.get('last_result')
    if isinstance(latest, dict):
        for row in latest.get('results', []):
            if (row.get('method_id') == method_id and row.get('generation_status') == 'generated'
                    and type(row.get('main_match_count')) is int and row['main_match_count'] >= 3):
                run = payload['total_runs']
                known = recovered.get(run)
                if known and (known['round'] != latest.get('target_round')
                              or known['main_match_count'] != row['main_match_count']
                              or known['generated_at'] != str(latest.get('generated_at', ''))[:80]):
                    continue  # Conflicting metadata is not evidence for this run.
                try:
                    recovered[run] = hit_event(latest, row, run)
                except (ValueError, TypeError, KeyError):
                    pass  # Preserve counters; don't manufacture corrupted legacy details.
    return [recovered[n] for n in sorted(recovered)][-MAX_HIT_HISTORY:]


def validate_hits(events: Any, total_runs: int, hits: int) -> list[dict]:
    """Reject corrupt new history without overwriting the existing HA Store."""
    if not isinstance(events, list) or len(events) > min(MAX_HIT_HISTORY, hits):
        raise ValueError('invalid hit history size')
    last_run = 0
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('invalid hit event')
        run = event.get('run')
        if (type(run) is not int or not last_run < run <= total_runs
                or type(event.get('details_available')) is not bool
                or not isinstance(event.get('generated_at'), str)):
            raise ValueError('invalid hit chronology')
        last_run = run
        source = {'target_round': event.get('round'), 'generated_at': event['generated_at']}
        row = {'main_match_count': event.get('main_match_count')}
        if event['details_available']:
            source['draw'] = {'round': event['round'], 'draw_date': event.get('draw_date'),
                              'numbers': event.get('winning_numbers'), 'bonus': event.get('bonus_number')}
            row = {**event}
        elif any(k in event for k in ('recommended_numbers', 'matched_main_numbers', 'prize_rank')):
            raise ValueError('unavailable history must not contain guessed numbers')
        checked = hit_event(source, row, run)
        if checked != event:
            raise ValueError('inconsistent hit history fields')
    return deepcopy(events)
