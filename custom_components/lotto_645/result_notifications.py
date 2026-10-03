"""Entry-scoped, durable announcement alerts containing only public result data."""
from __future__ import annotations

from datetime import UTC, datetime
import logging

from .published_results import current_draw_round

_LOGGER = logging.getLogger(__name__)
LABELS = {'provisional': '언론 임시 결과 · 공식 확인 전',
          'cross_checked': '언론 교차 확인 · 공식 확인 전',
          'official_history': '공식 이력 확인', 'official_confirmed': '공식 확인',
          'official_corrected': '공식 정정 확인'}


def announcement(draw, metadata: dict, now: datetime, previous: dict | None = None) -> dict | None:
    """Never infer announcement completion from the clock or missing results."""
    status = metadata.get('status')
    target = current_draw_round(now)
    if status == 'conflict':
        if not previous or previous.get('round') != target:
            return None
        return {'round': target, 'key': f'{target}:conflict', 'signature': 'conflict',
                'status': status, 'title': f'로또 {target}회 결과 확인 보류',
                'message': '출처의 당첨번호가 서로 다릅니다. 이전 임시 결과의 당첨 판정을 보류하고 재확인 중입니다.'}
    if draw is None or draw.round != target or status not in LABELS:
        return None
    signature = ','.join(map(str, draw.numbers)) + f'+{draw.bonus}'
    corrected = previous and previous.get('signature') not in (None, signature, 'conflict')
    return {'round': target, 'key': f'{target}:{signature}', 'signature': signature,
            'status': status, 'title': f'로또 {target}회 당첨번호' + (' 정정' if corrected else ' 발표 확인'),
            'message': f"{', '.join(map(str, draw.numbers))} · 보너스 {draw.bonus}\n{LABELS[status]}"}


async def async_publish_result_notification(coordinator) -> None:
    """Upsert one HA card per entry/round; only emit after durable deduplication."""
    from homeassistant.components import persistent_notification
    from homeassistant.helpers.storage import Store
    from .const import DOMAIN

    if not hasattr(coordinator, '_result_notification_store'):
        coordinator._result_notification_store = Store(
            coordinator.hass, 1, f'{DOMAIN}.announcements.{coordinator.entry.entry_id}')
    store = coordinator._result_notification_store
    if not hasattr(coordinator, '_result_notification_ledger'):
        saved = await store.async_load()
        saved = saved if isinstance(saved, dict) else {}
        coordinator._result_notification_first = not saved.get('initialized', False)
        rows = saved.get('rounds', {})
        coordinator._result_notification_ledger = {k: v for k, v in rows.items()
            if str(k).isdigit() and isinstance(v, dict)} if isinstance(rows, dict) else {}
    ledger = coordinator._result_notification_ledger
    now = datetime.now(UTC)
    previous = ledger.get(str(current_draw_round(now)))
    if not isinstance(previous, dict):
        previous = None
    payload = announcement(coordinator.result_draw, coordinator.result_metadata, now, previous)
    first = coordinator._result_notification_first
    if payload is None:
        if first:
            await store.async_save({'initialized': True, 'rounds': ledger})
            coordinator._result_notification_first = False
        return
    coordinator._last_result_notification = payload
    if previous and all(previous.get(k) == payload.get(k) for k in ('key', 'status')):
        return
    if first and payload['status'].startswith('official'):
        baseline = {**ledger, str(payload['round']): payload}
        await store.async_save({'initialized': True, 'rounds': baseline})
        coordinator._result_notification_ledger = baseline
        coordinator._result_notification_first = False
        return
    notification_id = f'{DOMAIN}_{coordinator.entry.entry_id}_draw_{payload["round"]}'
    # Same ID replaces the existing HA card even after a save failure/restart.
    persistent_notification.async_create(coordinator.hass, payload['message'],
                                         title=payload['title'], notification_id=notification_id)
    updated = {**ledger, str(payload['round']): payload}
    updated = dict(sorted(updated.items(), key=lambda item: int(item[0]))[-8:])
    await store.async_save({'initialized': True, 'rounds': updated})
    coordinator._result_notification_first = False
    coordinator._result_notification_ledger = updated
    coordinator.hass.bus.async_fire(DOMAIN + '_updated', {
        'entry_id': coordinator.entry.entry_id, 'announcement': payload})


def schedule_result_notification(coordinator) -> None:
    """Coalesce rapid publisher corrections without delaying result listeners."""
    if getattr(coordinator, "_result_notification_stopping", False):
        return
    coordinator._result_notification_dirty = True
    task = getattr(coordinator, '_result_notification_task', None)
    if task is not None and not task.done():
        return

    async def run():
        while coordinator._result_notification_dirty:
            coordinator._result_notification_dirty = False
            try:
                await async_publish_result_notification(coordinator)
            except Exception:  # Alert failure must not hide the actual draw result.
                _LOGGER.warning('당첨번호 알림을 저장/전달하지 못했습니다. 다음 갱신에 재시도합니다')
                break
    coordinator._result_notification_task = coordinator.hass.async_create_task(run())


def cancel_result_notifications(coordinator) -> None:
    coordinator._result_notification_stopping = True
    task = getattr(coordinator, '_result_notification_task', None)
    if task is not None and not task.done():
        task.cancel()
