"""Reactive, deterministic consensus of the actual selected six-number tickets.

Inputs are the same immutable records published by LottoGameSensor, not hidden
feature scores. No RNG, network, source regeneration or recursive self-vote.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import replace
from hashlib import sha256
from itertools import product
import json
from math import ceil, floor
from statistics import median

from .const import DISCLAIMER, FIRST_PRIZE_ODDS
from .methods import METHOD_SELECTED_MEDIAN, METHODS_BY_ID, consensus_source_ids
from .models import AnalysisResult, LottoDraw, Recommendation

CONSENSUS_VERSION = 2
TOLERANCE = 1
MIN_SOURCES = 2


def valid_ticket(value: object) -> tuple[int, ...] | None:
    """Reject unavailable/malformed source records instead of coercing values."""
    if (not isinstance(value, (tuple, list)) or len(value) != 6
            or any(type(n) is not int or not 1 <= n <= 45 for n in value)
            or len(set(value)) != 6):
        return None
    return tuple(sorted(value))


def select_near_medians(
    tickets: Sequence[tuple[int, ...]], forbidden: Iterable[tuple[int, ...]] = (),
) -> tuple[tuple[int, ...] | None, tuple[float, ...]]:
    """Search at most 3**6 candidates; never silently relax the +/-1 rule."""
    centers = tuple(float(median(column)) for column in zip(*tickets, strict=True))
    choices = [range(max(1, ceil(c - TOLERANCE)), min(45, floor(c + TOLERANCE)) + 1)
               for c in centers]
    blocked = set(forbidden)
    votes = Counter(number for ticket in tickets for number in ticket)
    candidates = (combo for combo in product(*choices)
                  if all(a < b for a, b in zip(combo, combo[1:])) and combo not in blocked)
    # Exact integers/halves: no floating-point rounding ambiguity or random ties.
    best = min(candidates, key=lambda combo: (
        sum(abs(n - c) for n, c in zip(combo, centers)),
        -sum(votes[n] for n in combo), combo,
    ), default=None)
    return best, centers


def refresh_consensus(
    analysis: AnalysisResult,
    selected_ids: Sequence[str],
    history: Iterable[LottoDraw],
    *, updated_at: str | None = None, excluded_combinations: Iterable[tuple[int, ...]] = (),
) -> AnalysisResult:
    """Derive from current selected local outputs and atomically replace only it.

    Same numbers/selection/history yield the same result, independent of the
    refresh nonce, source timestamps, score changes or notification count.
    """
    others = tuple(r for r in analysis.recommendations if r.method_id != METHOD_SELECTED_MEDIAN)
    summary = dict(analysis.summary)
    if METHOD_SELECTED_MEDIAN not in selected_ids:
        summary.pop('selected_median_consensus', None)
        if others == analysis.recommendations and summary == analysis.summary:
            return analysis
        return replace(analysis, recommendations=others, summary=summary)

    requested = consensus_source_ids(selected_ids)
    by_id = {r.method_id: r for r in others}
    sources: dict[str, tuple[int, ...]] = {}
    for key in requested:
        row = by_id.get(key)
        if row is None or row.source != 'local':
            continue
        # Missing fields are the legacy local record format, not a stale round.
        if (row.details.get('target_round', analysis.target_round) != analysis.target_round
                or row.details.get('based_on_round', analysis.based_on_round) != analysis.based_on_round):
            continue
        ticket = valid_ticket(row.numbers)
        if ticket is not None:
            sources[key] = ticket
    past = {tuple(d.numbers) for d in history if d.round <= analysis.based_on_round}
    extra_blocked = set(excluded_combinations)
    signature = sha256(json.dumps({
        'version': CONSENSUS_VERSION, 'target': analysis.target_round,
        'based_on': analysis.based_on_round, 'selected': sorted(requested),
        'sources': sorted(sources.items()), 'past': sorted(past | extra_blocked),
    }, separators=(',', ':')).encode()).hexdigest()
    previous = analysis.recommendation_by_method(METHOD_SELECTED_MEDIAN)
    old_meta = analysis.summary.get('selected_median_consensus', {})
    old_stamp = old_meta.get('updated_at') if old_meta.get('input_signature') == signature else None
    stamp = old_stamp or updated_at
    meta = {
        'formula_version': CONSENSUS_VERSION,
        'source_method_ids': list(sources),
        'source_method_labels': [METHODS_BY_ID[key].label for key in sources],
        'source_count': len(sources), 'requested_source_count': len(requested),
        'missing_source_method_ids': [key for key in requested if key not in sources],
        'source_numbers': {key: list(ticket) for key, ticket in sources.items()},
        'input_signature': signature, 'updated_at': stamp,
        'tolerance': TOLERANCE, 'status': 'waiting_for_sources',
        'rule': '선택한 다른 로컬 공식의 실제 추천번호를 정렬해 순번별 중앙값 ±1에서 구성; AI·자기 자신 제외',
        'update_trigger': 'selected_source_numbers_or_selection_changed',
    }
    recommendation = None
    if len(sources) >= MIN_SOURCES:
        # Current source duplicates and past winning tickets are hard exclusions.
        # Live consensus keeps identical inputs stable. An isolated historical
        # rerun may explicitly exclude its prior simulation, never live records.
        combo, centers = select_near_medians(tuple(sources.values()), past | set(sources.values()) | extra_blocked)
        meta['position_medians'] = list(centers)
        meta['status'] = 'ready' if combo else 'no_candidate_within_tolerance'
        if combo:
            votes = Counter(n for ticket in sources.values() for n in ticket)
            method = METHODS_BY_ID[METHOD_SELECTED_MEDIAN]
            details = {
                'formula_id': METHOD_SELECTED_MEDIAN, 'formula_version': CONSENSUS_VERSION,
                'method_description': method.description, 'method_category': method.category,
                'target_round': analysis.target_round, 'based_on_round': analysis.based_on_round,
                'consensus_source_method_ids': list(sources),
                'consensus_source_methods': meta['source_method_labels'],
                'consensus_source_count': len(sources),
                'consensus_source_numbers': meta['source_numbers'],
                'consensus_missing_source_method_ids': meta['missing_source_method_ids'],
                'consensus_position_medians': list(centers),
                'consensus_position_deviations': [n - c for n, c in zip(combo, centers)],
                'consensus_tolerance': TOLERANCE, 'consensus_rule': meta['rule'],
                'consensus_input_signature': signature, 'consensus_updated_at': stamp,
                'consensus_number_support_votes': {str(n): votes[n] for n in combo},
                'refresh_behavior': '선택한 원본 공식의 추천번호 또는 선택 목록이 바뀌면 자동 재계산; 같은 입력이면 유지',
                'number_source': 'selected_local_recommendation_numbers',
                'rng': 'not_used', 'score_meaning': '실제 추천번호의 파생 중앙값; 내부 점수나 당첨 확률이 아님',
                'uniformity': 'nonuniform_personalization', 'predictive_evidence': 'not_established',
                'number_sum': sum(combo), 'odd_count': sum(n % 2 for n in combo),
                'exact_past_first_prize_match': False,
                'first_prize_odds': FIRST_PRIZE_ODDS, 'disclaimer': DISCLAIMER,
            }
            recommendation = Recommendation(
                max((r.index for r in others), default=0) + 1,
                METHOD_SELECTED_MEDIAN, method.label, method.category, combo,
                f"선택한 다른 {len(sources)}개 공식의 실제 추천번호를 순번별 중앙값 ±1로 집계합니다. 원본 번호·선택 변경 시 자동 갱신됩니다.",
                None, details,
            )
            if recommendation == previous:
                recommendation = previous
    summary['selected_median_consensus'] = meta
    rows = others + ((recommendation,) if recommendation else ())
    if rows == analysis.recommendations and summary == analysis.summary:
        return analysis
    return replace(analysis, recommendations=rows, summary=summary)
