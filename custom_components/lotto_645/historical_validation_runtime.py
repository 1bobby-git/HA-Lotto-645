"""Single-flight historical validation, isolated from pre-draw recommendations."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from functools import partial

from .historical_validation import HistoricalValidationError, run_historical_validation
from .historical_validation_scores import (
    ScoreConflict, async_access, async_record as async_record_validation_score, published_round,
)

KEY = 'lotto_645_historical_validation_workers'
TIMEOUT_SECONDS = 180
LAST_KEY = 'lotto_645_last_historical_validation'


async def async_validate_history(hass, coordinator, target_round, method_ids):
    """Generate from the prefix, then append only to the current validation cycle."""
    workers = hass.data.setdefault(KEY, {})
    key = coordinator.entry.entry_id
    if key in workers and not workers[key].done():
        raise HistoricalValidationError('validation_busy', '이 통합에서 과거 회차를 검증 중입니다. 완료 후 다시 실행하세요.')
    live_lock = getattr(coordinator, '_manual_lock', None)
    if live_lock is not None and live_lock.locked():
        raise HistoricalValidationError('generation_busy', '현재 추천번호를 생성 중입니다. 완료 후 과거 검증을 실행하세요.')
    try:
        cycle = await async_access(hass, key, published_round(coordinator))
    except Exception as err:
        raise HistoricalValidationError('score_storage_error', '검증 저장소를 읽지 못했습니다. 기존 기록을 보존합니다.') from err
    # Recheck after awaiting the store; another requester may have claimed it.
    if key in workers and not workers[key].done():
        raise HistoricalValidationError('validation_busy', '이미 과거 회차를 검증 중입니다.')
    history = tuple(coordinator.history)
    profile = deepcopy(coordinator.saju_profile) if coordinator.saju_profile_ready else None
    previous = hass.data.get(LAST_KEY, {}).get(key)
    blocked = previous[2] if previous and previous[0] is coordinator and previous[1] == target_round else ()
    worker = hass.async_add_executor_job(partial(
        run_historical_validation, history, target_round, tuple(method_ids), profile, previous_tickets=blocked,
    ))
    workers[key] = worker

    def finished(future):
        if not future.cancelled() and future.exception() is None:
            result = future.result()
            if (result.get('mode') == 'historical_validation'
                    and published_round(coordinator) == cycle['cycle_round']
                    and getattr(coordinator.entry, 'runtime_data', coordinator) is coordinator):
                hass.data.setdefault(LAST_KEY, {})[key] = (coordinator, target_round, tuple(
                    tuple(row['recommended_numbers']) for row in result['results']
                    if row.get('generation_status') == 'generated'
                ))
        if workers.get(key) is future:
            workers.pop(key, None)

    worker.add_done_callback(finished)
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            result = await asyncio.shield(worker)
    except TimeoutError as err:
        raise HistoricalValidationError('validation_timeout', '검증 제한시간을 초과했습니다. 실행 중인 작업이 정리된 후 공식을 줄여 다시 시도하세요.') from err
    if getattr(coordinator.entry, 'runtime_data', coordinator) is not coordinator:
        raise HistoricalValidationError('validation_reloaded', '통합이 다시 로드되어 이전 작업을 기록하지 않았습니다.')
    try:
        scoreboard = await async_record_validation_score(
            hass, key, result, current_round=published_round(coordinator),
            expected_cycle=cycle['cycle_id'], cycle_reader=lambda: published_round(coordinator),
        )
    except ScoreConflict as err:
        hass.data.get(LAST_KEY, {}).pop(key, None)
        raise HistoricalValidationError('validation_cycle_expired', str(err)) from err
    return {**result, 'validation_cycle': scoreboard.get('cycle_id'), 'validation_scoreboard': scoreboard,
            'validation_scoreboard_persisted': not scoreboard.get('storage_error', False)}
