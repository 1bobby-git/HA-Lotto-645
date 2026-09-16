"""Project stored reviews onto the current selection without editing the ledger."""
from __future__ import annotations

from math import isfinite
from .const import AI_METHOD_ID


def review_method_ids(coordinator) -> tuple[str, ...]:
    """Configuration, not saved history or the full catalog, owns visibility."""
    ids = [key for key in coordinator.configured_method_ids
           if isinstance(key, str) and key != AI_METHOD_ID]
    if coordinator.ai_enabled:
        ids.append(AI_METHOD_ID)
    return tuple(dict.fromkeys(ids))


def selected_round_review(report: dict, method_ids: tuple[str, ...]) -> dict:
    """Return a detached view; hidden methods remain in the persisted record."""
    by_id = {row['method_id']: row for row in report.get('methods', [])
             if isinstance(row, dict) and isinstance(row.get('method_id'), str)}
    methods = [dict(by_id[key]) for key in method_ids if key in by_id]
    view = {**report, 'methods': methods, 'peer_count': len(methods)}
    if report.get('status') in ('confirmed', 'provisional'):
        scores = [row['review_score'] for row in methods
                  if type(row.get('review_score')) in (int, float)
                  and isfinite(row['review_score'])]
        for row in methods:
            score = row.get('review_score')
            if type(score) in (int, float) and isfinite(score):
                row['rank_this_round'] = 1 + sum(value > score for value in scores)
    return view
