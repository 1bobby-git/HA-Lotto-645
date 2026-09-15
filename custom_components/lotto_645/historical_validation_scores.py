"""Cycle-scoped simulations and explicitly imported review evidence.

The HA Store envelope remains v1; the payload migrates additively to schema 2.
Real pre-draw ReviewBook records are never synthesized from simulations.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from math import comb, sqrt
from typing import Any
from uuid import uuid4

from .const import DOMAIN
from .validation_hit_history import MAX_HIT_HISTORY, hit_event, migrate_hits, validate_hits

STORE_VERSION = 1
CACHE_KEY = f"{DOMAIN}_historical_validation_score_ledgers"
POINTS = {3: 1, 4: 3, 5: 10, 6: 50}
MAX_RECENT = 50
COUNTERS = ('attempts', 'generated', 'unavailable', 'three_plus_hits', 'points',
            'match_3', 'match_4', 'match_5', 'match_6')
BASELINE = sum(comb(6, k) * comb(39, 6-k) for k in range(3, 7)) / comb(45, 6)
RESET_NOTICE = ('새 당첨회차가 공식 이력 또는 교차확인 결과로 확인되면 검증 횟수·점수·결과를 초기화합니다. '
                '이미 리뷰에 반영한 과거검증 성과와 실제 추천 리뷰는 유지됩니다.')


class ScoreConflict(ValueError):
    """The confirmed snapshot was superseded; never import unseen results."""


def _empty() -> dict[str, Any]:
    return {'version': 1, 'schema': 2, 'total_runs': 0, 'rounds': [], 'methods': {}, 'recent': [],
            'cycle_round': 0, 'cycle_id': uuid4().hex, 'last_result': None,
            'reviews': {}, 'imported_current': {}, 'imported_runs': 0, 'review_runs': 0,
            'last_import': None, 'reset_at': None}


def _method_row(method_id: str, label: str) -> dict[str, Any]:
    return {'method_id': method_id, 'label': label, **dict.fromkeys(COUNTERS, 0),
            'best_match': 0, 'first_rounds': {}, 'formula_versions': []}


def _validate(payload: Any) -> dict[str, Any]:
    if payload is None:
        return _empty()
    if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload.get('version') != 1 or payload.get('schema', 2) != 2:
        raise ValueError('invalid validation ledger')
    if type(payload.get('total_runs')) is not int or payload['total_runs'] < 0:
        raise ValueError('invalid validation count')
    result = {**_empty(), **deepcopy(payload)}
    if (not isinstance(result['rounds'], list) or any(type(n) is not int or n < 1 for n in result['rounds'])
            or not isinstance(result['recent'], list) or len(result['recent']) > MAX_RECENT
            or type(result['cycle_round']) is not int or result['cycle_round'] < 0
            or not isinstance(result['cycle_id'], str) or not result['cycle_id']):
        raise ValueError('invalid validation cycle')
    for key in ('imported_runs', 'review_runs'):
        if type(result[key]) is not int or result[key] < 0:
            raise ValueError('invalid import count')
    if result['imported_runs'] > result['total_runs']:
        raise ValueError('invalid import cursor')
    for group in ('methods', 'reviews', 'imported_current'):
        if not isinstance(result[group], dict):
            raise ValueError('invalid method collection')
        for method_id, raw in result[group].items():
            if not isinstance(method_id, str) or not isinstance(raw, dict):
                raise ValueError('invalid method row')
            row = {**_method_row(method_id, method_id), **raw}
            if any(type(row[c]) is not int or row[c] < 0 for c in (*COUNTERS, 'best_match')):
                raise ValueError('invalid score counter')
            if (row['generated'] + row['unavailable'] != row['attempts'] or row['best_match'] > 6
                    or row['three_plus_hits'] != sum(row[f'match_{n}'] for n in POINTS)
                    or row['points'] != sum(row[f'match_{n}'] * POINTS[n] for n in POINTS)
                    or row['three_plus_hits'] > row['generated'] or not isinstance(row['label'], str)):
                raise ValueError('inconsistent score counters')
            if (not isinstance(row['first_rounds'], dict)
                    or any(not str(n).isdigit() or type(k) is not int or not 0 <= k <= 6
                           for n, k in row['first_rounds'].items())
                    or not isinstance(row['formula_versions'], list)
                    or any(not isinstance(v, str) for v in row['formula_versions'])):
                raise ValueError('invalid first-round evidence')
            result[group][method_id] = row
    for method_id, row in result['methods'].items():
        if 'hit_history' not in row:
            row['hit_history'] = migrate_hits(result, method_id)
        row['hit_history'] = validate_hits(row['hit_history'], result['total_runs'], row['three_plus_hits'])
    # v1 had no cycle anchor or unique-round evidence; preserve its aggregate,
    # but never invent independent trials from its rolling recent-50 history.
    return result


def rotate(payload: dict, published_round: int) -> dict:
    updated = deepcopy(payload)
    if published_round <= updated['cycle_round']:
        return updated
    if updated['cycle_round'] == 0:
        updated['cycle_round'] = published_round
        return updated
    for key in ('total_runs', 'imported_runs'):
        updated[key] = 0
    updated.update(rounds=[], methods={}, recent=[], imported_current={}, last_result=None,
                   cycle_round=published_round, cycle_id=uuid4().hex, reset_at=datetime.now(UTC).isoformat())
    return updated


def published_round(coordinator) -> int:
    latest = max((d.round for d in getattr(coordinator, 'history', ())), default=0)
    # A single provisional publisher or a conflicting result cannot erase data.
    fast = getattr(coordinator, '_fast_result', None) or {}
    if fast.get('status') == 'cross_checked' and fast.get('draw'):
        from .models import LottoDraw
        try:
            draw = LottoDraw.from_storage(fast['draw'])
            if draw.round == fast.get('round'):
                latest = max(latest, draw.round)
        except (ValueError, TypeError, KeyError):
            pass
    return latest


def apply_result(payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Append one completed target-round test, including all losing outcomes."""
    updated = deepcopy(payload)
    target = result.get('target_round')
    rows = result.get('results')
    if type(target) is not int or target < 1 or not isinstance(rows, list):
        raise ValueError('invalid validation result')
    for method_id, old in updated['methods'].items():
        if 'hit_history' not in old:
            old['hit_history'] = migrate_hits(updated, method_id)
    updated['total_runs'] += 1
    updated['rounds'] = sorted(set(updated.get('rounds', [])) | {target})
    run_methods = []
    seen = set()
    for raw in rows:
        if not isinstance(raw, dict) or not isinstance(raw.get('method_id'), str):
            raise ValueError('invalid method')
        key = raw['method_id']
        if key in seen:
            raise ValueError('duplicate method')
        seen.add(key)
        label = str(raw.get('sensor_name') or key)[:180]
        row = updated['methods'].setdefault(key, _method_row(key, label))
        row['label'] = label
        row.setdefault('hit_history', [])
        row['attempts'] += 1
        row.setdefault('first_rounds', {})
        versions = row.setdefault('formula_versions', [])
        version = str(raw.get('formula_version') or 'legacy')[:80]
        if version not in versions:
            versions.append(version)
        match = None
        if raw.get('generation_status') == 'generated':
            match = raw.get('main_match_count', 0)
            if type(match) is not int or not 0 <= match <= 6:
                raise ValueError('invalid match count')
            row['generated'] += 1
            row['best_match'] = max(row['best_match'], match)
            row['first_rounds'].setdefault(str(target), match)
            if match >= 3:
                row['three_plus_hits'] += 1
                row[f'match_{match}'] += 1
                row['points'] += POINTS[match]
                events = row.setdefault('hit_history', [])
                events.append(hit_event(result, raw, updated['total_runs']))
                row['hit_history'] = events[-MAX_HIT_HISTORY:]
        else:
            row['unavailable'] += 1
        run_methods.append({'method_id': key, 'match': match, 'points': POINTS.get(match, 0)})
    updated['recent'].append({'run': updated['total_runs'], 'round': target,
                              'generated_at': str(result.get('generated_at', ''))[:80], 'methods': run_methods})
    updated['recent'] = updated['recent'][-MAX_RECENT:]
    # Only one complete result is retained. No recursive scoreboards or profiles.
    updated['last_result'] = {k: deepcopy(v) for k, v in result.items() if not k.startswith('validation_scoreboard')}
    return updated


def wilson(hits: int, count: int) -> list[float] | None:
    """99% Wilson interval, descriptive only; first test per distinct round."""
    if not count:
        return None
    z = 2.5758293035489004
    p = hits / count
    d = 1 + z*z/count
    c = (p + z*z/(2*count)) / d
    h = z * sqrt(p*(1-p)/count + z*z/(4*count*count)) / d
    return [round(max(0, c-h)*100, 3), round(min(1, c+h)*100, 3)]


def revision(payload: dict) -> str:
    raw = [payload.get('cycle_id'), payload.get('cycle_round'), payload['total_runs'], payload['methods']]
    return sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def summary(payload: dict[str, Any]) -> dict[str, Any]:
    methods = []
    for raw in payload.get('methods', {}).values():
        row = deepcopy(raw)
        generated, hits = row.get('generated', 0), row.get('three_plus_hits', 0)
        events = row.setdefault('hit_history', [])
        row['hit_history_omitted'] = max(0, hits - len(events))
        row['hit_history_limit'] = MAX_HIT_HISTORY
        row['hit_rate'] = round(hits*100/generated, 1) if generated else 0.0
        row['points_per_100'] = round(row['points']*100/generated, 2) if generated else 0.0
        first = row.pop('first_rounds', {})
        row['unique_rounds'] = len(first)
        row['first_hits'] = sum(n >= 3 for n in first.values())
        row['first_hit_rate'] = round(row['first_hits']*100/len(first), 2) if first else None
        row['interval_99'] = wilson(row['first_hits'], len(first)) if len(row.get('formula_versions', [])) <= 1 else None
        row['sample_notice'] = ('공식 버전 혼합 · 구간 비교 제외' if len(row.get('formula_versions', [])) > 1
                                else '표본 부족' if len(first) < 100 else '탐색 결과 · 실전 재확인 필요')
        row['baseline_ratio'] = round(hits/generated/BASELINE, 2) if generated else None
        methods.append(row)
    methods.sort(key=lambda r: (-r['points'], -r['three_plus_hits'], -r['best_match'], r['label']))
    coverage = {tuple(sorted(r.get('first_rounds', {}))) for r in payload.get('methods', {}).values()}
    return {'total_runs': payload.get('total_runs', 0), 'unique_rounds': len(payload.get('rounds', [])),
            'point_policy': '3개=1점 · 4개=3점 · 5개=10점 · 6개=50점', 'threshold': 3,
            'methods': methods, 'recent': deepcopy(payload.get('recent', [])),
            'cycle_round': payload.get('cycle_round', 0), 'cycle_id': payload.get('cycle_id'),
            'revision': revision(payload), 'reset_notice': RESET_NOTICE, 'reset_at': payload.get('reset_at'),
            'unimported_runs': payload['total_runs'] - payload.get('imported_runs', 0),
            'baseline_hit_rate': round(BASELINE*100, 5), 'comparable_rounds': len(coverage) <= 1,
            'review_runs': payload.get('review_runs', 0), 'last_import': deepcopy(payload.get('last_import'))}


def apply_import(payload: dict, expected_revision: str) -> dict:
    if expected_revision != revision(payload):
        raise ScoreConflict('검증 결과가 바뀌었거나 초기화되었습니다. 최신 내용을 확인한 후 다시 반영하세요.')
    updated = deepcopy(payload)
    delta_runs = updated['total_runs'] - updated.get('imported_runs', 0)
    if delta_runs <= 0:
        return updated
    for key, current in updated['methods'].items():
        previous = updated['imported_current'].get(key, {})
        row = updated['reviews'].setdefault(key, _method_row(key, current['label']))
        for field in COUNTERS:
            delta = current[field] - previous.get(field, 0)
            if delta < 0:
                raise ScoreConflict('리뷰 반영 기준이 일치하지 않습니다.')
            row[field] += delta
        row['label'] = current['label']
        row['best_match'] = max(row['best_match'], current['best_match'])
        row['formula_versions'] = sorted(set(row['formula_versions']) | set(current.get('formula_versions', [])))
        # Cross-cycle repeat draws remain single evidence points, not independent trials.
        for round_no, match in current.get('first_rounds', {}).items():
            row['first_rounds'].setdefault(round_no, match)
    updated['imported_current'] = deepcopy(updated['methods'])
    updated['imported_runs'] = updated['total_runs']
    updated['review_runs'] += delta_runs
    updated['last_import'] = {'at': datetime.now(UTC).isoformat(), 'cycle_round': updated['cycle_round'],
                              'runs': updated['total_runs'], 'added_runs': delta_runs, 'source': 'historical_validation'}
    return updated


def _state(hass, entry_id):
    return hass.data.setdefault(CACHE_KEY, {}).setdefault(entry_id, {'lock': asyncio.Lock(), 'payload': None})


def _store(hass, entry_id):
    try:
        from homeassistant.helpers.storage import Store
    except ModuleNotFoundError as err:
        if not (err.name or '').startswith('homeassistant'):
            raise
        return None  # Pure-policy tests only; never used by a running HA installation.
    return Store(hass, STORE_VERSION, f'{DOMAIN}.validation_scores.{entry_id}')


async def _save(store, state, payload):
    if store is not None:
        await store.async_save(payload)
    state['payload'] = payload  # Publish only after a successful atomic save.


async def async_access(hass, entry_id, current_round=0, *, result=None, expected_cycle=None,
                       import_revision=None, cycle_reader=None):
    state = _state(hass, entry_id)
    async with state['lock']:
        store = _store(hass, entry_id)
        if state['payload'] is None:
            state['payload'] = _validate(await store.async_load() if store else None)
        payload = state['payload']
        latest = max(current_round, cycle_reader() if cycle_reader else 0)
        updated = rotate(payload, latest)
        if updated != payload:
            await _save(store, state, updated)
            payload = updated
        if expected_cycle is not None and payload['cycle_id'] != expected_cycle:
            raise ScoreConflict('새 당첨회차가 확인되어 이전 검증 결과를 초기화했습니다.')
        if result is not None:
            updated = apply_result(payload, result)
        elif import_revision is not None:
            updated = apply_import(payload, import_revision)
        else:
            updated = payload
        if updated != payload:
            await _save(store, state, updated)
        # Publication may advance while storage was awaiting disk I/O.
        if cycle_reader and cycle_reader() > updated['cycle_round']:
            updated = rotate(updated, cycle_reader())
            await _save(store, state, updated)
            if result is not None:
                raise ScoreConflict('새 당첨회차가 확인되었습니다. 최신 검증 상태를 다시 확인하세요.')
        return deepcopy(updated)


async def async_record(hass, entry_id, result, *, current_round=0, expected_cycle=None, cycle_reader=None):
    try:
        payload = await async_access(hass, entry_id, current_round, result=result,
                                     expected_cycle=expected_cycle, cycle_reader=cycle_reader)
    except ScoreConflict:
        raise
    except Exception as err:
        # Store may raise HA-specific serialization/read errors. Do not erase or
        # fabricate counters, and allow a later access to retry the I/O.
        import logging
        logging.getLogger(__name__).warning('과거 검증 점수 저장 실패 (%s)', type(err).__name__)
        cached = _state(hass, entry_id)['payload']
        return {**summary(cached or _empty()), 'storage_error': True}
    return summary(payload)


def cached_reviews(hass, entry_id):
    payload = _state(hass, entry_id)['payload']
    return {key: {**{k: deepcopy(v) for k, v in row.items() if k != 'first_rounds'},
                  'unique_rounds': len(row.get('first_rounds', {})), 'source': 'historical_validation'}
            for key, row in (payload.get('reviews', {}) if payload else {}).items()}
