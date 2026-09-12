"""Shared prize detail attributes; exact official matches only determine wins."""
from __future__ import annotations
from homeassistant.helpers import entity_registry as er
from .const import AI_METHOD_ID, DOMAIN


def decorate_result(coordinator, result: dict) -> dict:
    method_id = str(result.get('method_id', ''))
    if result.get('source') == 'purchased':
        unique_id = f'{coordinator.entry.entry_id}_purchased_tickets'
    elif method_id == AI_METHOD_ID:
        unique_id = f'{coordinator.entry.entry_id}_ai_recommendation'
    else:
        unique_id = f'{coordinator.entry.entry_id}_method_{method_id}'
    registry = er.async_get(coordinator.hass)
    return {**result, 'recommendation_sensor_unique_id': unique_id,
            'entity_id': registry.async_get_entity_id('sensor', DOMAIN, unique_id)}


def winning_attributes(coordinator) -> dict:
    evaluation = coordinator.winning_summary
    if not evaluation:
        return {'status': 'waiting', 'results': [], 'winners': [], 'losers': [],
                'message': '추첨번호 확인 후 같은 회차의 저장번호를 비교합니다.'}
    results = [decorate_result(coordinator, row) for row in evaluation.get('results', [])]
    review = coordinator.review_for_round(evaluation.get('round')) if hasattr(coordinator, 'review_for_round') else {}
    by_method = {r['method_id']: r for r in review.get('methods', [])}
    for row in results:
        if row.get('source') != 'purchased' and row.get('method_id') in by_method:
            r = by_method[row['method_id']]
            row['review'] = {k: r[k] for k in ('review_score', 'stars', 'exact_match_count',
                                             'near_match_count', 'near_pairs', 'rank_this_round')}
    return {**evaluation, 'results': results,
            'winners': [r for r in results if r.get('prize_rank') is not None],
            'losers': [r for r in results if r.get('prize_rank') is None],
            'prize_rules': '1등=6개, 2등=5개+보너스, 3등=5개, 4등=4개, 5등=3개',
            'review_notice': '±1 유사번호와 별점은 리뷰 전용이며 당첨 등수에 포함되지 않습니다.',
            'note': '추천번호와 실제 구매번호는 구분됩니다. 지급·소유권 확인이 아닙니다.'}
