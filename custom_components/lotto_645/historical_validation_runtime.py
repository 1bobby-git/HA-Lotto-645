"""Single-flight executor for ephemeral historical validation, no stores/listeners."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from functools import partial

from .historical_validation import HistoricalValidationError, run_historical_validation

KEY = 'lotto_645_historical_validation_workers'
TIMEOUT_SECONDS = 180
LAST_KEY = 'lotto_645_last_historical_validation'


async def async_validate_history(hass, coordinator, target_round, method_ids):
    """Do not call the live coordinator's build/refresh/review/save methods.

    Keep the busy lease until the executor really finishes, even if the caller
    is cancelled or times out. Otherwise retries could create unbounded workers.
    """
    workers = hass.data.setdefault(KEY, {})
    key = coordinator.entry.entry_id
    if key in workers and not workers[key].done():
        raise HistoricalValidationError('validation_busy', '이 통합에서 과거 회차를 검증 중입니다. 완료 후 다시 실행하세요.')
    live_lock = getattr(coordinator, '_manual_lock', None)
    if live_lock is not None and live_lock.locked():
        raise HistoricalValidationError('generation_busy', '현재 추천번호를 생성 중입니다. 완료 후 과거 검증을 실행하세요.')
    history = tuple(coordinator.history)  # LottoDraw records are frozen.
    profile = deepcopy(coordinator.saju_profile) if coordinator.saju_profile_ready else None
    # One bounded prior batch per entry, held only in memory. A reload or target
    # change discards it. This is not a live recommendation/review cache.
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
            return await asyncio.shield(worker)
    except TimeoutError as err:
        raise HistoricalValidationError('validation_timeout', '검증 제한시간을 초과했습니다. 실행 중인 작업이 정리된 후 공식을 줄여 다시 시도하세요.') from err
