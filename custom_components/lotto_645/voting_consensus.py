"""Reactive family-normalized votes; the legacy positional median is unchanged."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from heapq import heappop, heappush
import json

VOTE_ID = 'selected_vote_consensus'
AGGREGATE_IDS = ('selected_median_consensus', VOTE_ID)


def family(method_id):
    from .sampling import UNIFORM_IDS
    if method_id in UNIFORM_IDS:
        return 'uniform'
    if method_id in ('weighted_frequency', 'hot_numbers', 'recency_decay', 'bayesian_shrinkage'):
        return 'frequency'
    return method_id


def select_vote(sources, blocked, signature):
    counts = Counter(family(key) for key in sources)
    votes = {n: sum((Fraction(1, counts[family(key)]) for key, row in sources.items() if n in row), Fraction())
             for n in range(1, 46)}
    order = sorted((n for n in votes if votes[n]), key=lambda n: (
        -votes[n], sha256(f'{signature}:{n}'.encode()).digest(), n))
    if len(order) < 6:
        return None, votes
    first = tuple(range(6))
    def item(indexes):
        return (-sum((votes[order[i]] for i in indexes), Fraction()), indexes)
    heap, seen = [item(first)], {first}
    # Enumerate descending score, at most one more candidate than forbidden tickets.
    for _ in range(len(blocked) + 1):
        if not heap:
            return None, votes
        _, indexes = heappop(heap)
        ticket = tuple(sorted(order[i] for i in indexes))
        if ticket not in blocked:
            return ticket, votes
        for j in range(6):
            if indexes[j] + 1 >= (indexes[j+1] if j < 5 else len(order)):
                continue
            following = (*indexes[:j], indexes[j]+1, *indexes[j+1:])
            if following not in seen:
                seen.add(following)
                heappush(heap, item(following))
    return None, votes


def refresh_vote(analysis, selected_ids, history, *, updated_at=None, excluded_combinations=()):
    from .consensus import valid_ticket
    from .const import DISCLAIMER, FIRST_PRIZE_ODDS
    from .methods import METHODS_BY_ID, consensus_source_ids
    from .models import Recommendation

    others = tuple(r for r in analysis.recommendations if r.method_id != VOTE_ID)
    summary = dict(analysis.summary)
    if VOTE_ID not in selected_ids:
        summary.pop(VOTE_ID, None)
        return analysis if others == analysis.recommendations and summary == analysis.summary else replace(analysis, recommendations=others, summary=summary)
    requested = consensus_source_ids(selected_ids)
    sources = {row.method_id: valid_ticket(row.numbers) for row in others
               if row.method_id in requested and row.source == 'local'
               and row.details.get('target_round', analysis.target_round) == analysis.target_round
               and row.details.get('based_on_round', analysis.based_on_round) == analysis.based_on_round
               and valid_ticket(row.numbers) is not None}
    blocked = {tuple(d.numbers) for d in history if d.round <= analysis.based_on_round}
    blocked.update(tuple(sorted(row)) for row in excluded_combinations)
    blocked.update(row.numbers for row in others)
    signature = sha256(json.dumps([1, analysis.target_round, sorted(requested), sorted(sources.items()), sorted(blocked)], separators=(',', ':')).encode()).hexdigest()
    old = summary.get(VOTE_ID, {})
    previous = analysis.recommendation_by_method(VOTE_ID)
    stamp = (old.get('updated_at') or updated_at) if old.get('input_signature') == signature else updated_at
    meta = {'input_signature': signature, 'updated_at': stamp, 'source_count': len(sources),
            'source_method_ids': list(sources), 'missing_source_method_ids': [k for k in requested if k not in sources],
            'family_count': len({family(k) for k in sources}), 'status': 'waiting_for_sources',
            'rule': '같은 계열의 공식 수로 표를 나눈 뒤 번호별 득표 합이 가장 큰 허용 조합 선택'}
    row = None
    if len(sources) >= 2:
        ticket, votes = select_vote(sources, blocked, signature)
        meta['status'] = 'ready' if ticket else 'no_allowed_combination'
        if ticket:
            method = METHODS_BY_ID[VOTE_ID]
            row = Recommendation(max((r.index for r in others), default=0)+1, VOTE_ID, method.label,
                method.category, ticket, method.description, None, {
                    'formula_id': VOTE_ID, 'formula_version': 1, 'target_round': analysis.target_round,
                    'based_on_round': analysis.based_on_round, 'consensus_source_count': len(sources),
                    'consensus_source_method_ids': list(sources),
                    'consensus_source_numbers': {k: list(v) for k, v in sources.items()},
                    'consensus_family_count': meta['family_count'],
                    'consensus_number_votes': {str(n): float(votes[n]) for n in ticket},
                    'consensus_input_signature': signature, 'consensus_updated_at': stamp,
                    'method_description': method.description, 'method_category': method.category,
                    'uniformity': 'nonuniform_family_vote', 'predictive_evidence': 'not_established',
                    'score_meaning': '계열 보정 득표이며 당첨 확률이 아닙니다',
                    'rng': 'not_used', 'tie_rule': 'sha256_of_source_signature_and_number',
                    'first_prize_odds': FIRST_PRIZE_ODDS, 'disclaimer': DISCLAIMER})
    if row is not None and row == previous:
        row = previous
    summary[VOTE_ID] = meta
    return replace(analysis, recommendations=others + ((row,) if row else ()), summary=summary)
