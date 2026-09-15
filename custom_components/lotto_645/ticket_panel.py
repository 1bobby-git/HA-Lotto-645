"""Admin-authenticated purchase panel. QR image decoding stays in the browser."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, VERSION
from .panel_metadata import panel_metadata
from .historical_validation import MIN_TARGET_ROUND, HistoricalValidationError
from .historical_validation_runtime import async_validate_history
from .historical_validation_scores import (
    ScoreConflict, async_access, cached_reviews, published_round, summary as score_summary,
)
from .const import AI_METHOD_ID
from .methods import METHODS_BY_ID, RETIRED_METHOD_LABELS
from .purchased_tickets import PurchaseInputError, parse_round
from .ticket_qr import parse_ticket_qr

KEY = DOMAIN + '_panel'
PATH = 'lotto-645'
WWW = Path(__file__).parent / 'www'
# The user-supplied PNG and locally verified pixel-identical lossless encodings.
# Never display the old quantized replacement as the supplied original.
SOURCE_LOGO_HASHES = {
    '88f442d0d73cb9c4b378059297dfa1b8d3f334fb5e2dc9599404e5eee042ed3d',
    'e97a01c60eddd57689a2073d0d9ff0f8c2f8b7a98a8d3aabf5e7d974317ebe5e',
    '48c9f12ab0b98cb721269844f505e0d703b2f8cfb1e4b889abe3abb92238fb80',
    '743d91bc687b5af2b4d3b9652a6b3cb1d2ee808abc4599cbc87abbe5c609b73f',
}


def _source_logo_available() -> bool:
    try:
        return hashlib.sha256((WWW.parent / 'brand' / 'logo.png').read_bytes()).hexdigest() in SOURCE_LOGO_HASHES
    except OSError:
        return False


def _coordinator(hass: HomeAssistant, message: dict) -> Any:
    entry = hass.config_entries.async_get_entry(message['entry_id'])
    if entry is None or entry.domain != DOMAIN or not getattr(entry, 'runtime_data', None):
        raise HomeAssistantError('통합을 사용할 수 없습니다')
    if getattr(entry, 'state', ConfigEntryState.LOADED) is not ConfigEntryState.LOADED:
        raise HomeAssistantError('로또 통합을 다시 불러오는 중입니다. 잠시 후 다시 확인하세요')
    return entry.runtime_data


def _review_rows(coordinator) -> list[dict]:
    from .const import AI_METHOD_ID
    from .methods import METHODS_BY_ID, RETIRED_METHOD_LABELS
    from .review import review_name
    ids = list(getattr(coordinator, 'configured_method_ids', ()))
    ids.extend(key for key in getattr(coordinator, '_review_summaries', {}) if key not in ids)
    if getattr(coordinator, 'ai_enabled', False) and AI_METHOD_ID not in ids:
        ids.append(AI_METHOD_ID)
    imported = cached_reviews(coordinator.hass, coordinator.entry.entry_id) if hasattr(coordinator, 'hass') else {}
    ids.extend(key for key in imported if key not in ids)
    rows = []
    for method_id in ids:
        summary = coordinator.review_for_method(method_id) if hasattr(coordinator, 'review_for_method') else {}
        label = METHODS_BY_ID[method_id].label if method_id in METHODS_BY_ID else 'Home Assistant AI 추천' if method_id == AI_METHOD_ID else RETIRED_METHOD_LABELS.get(method_id, method_id)
        rows.append({'method_id': method_id, 'label': label, 'display_name': review_name(label, summary), **summary,
                     'historical_review': imported.get(method_id)})
    return rows


def _view(coordinator: Any, round_no: int | None = None) -> dict:
    draw = coordinator.result_draw
    book = coordinator.purchase_book
    round_no = round_no or book.selected_round or (coordinator.data.analysis.target_round if coordinator.data else None)
    record = book.records.get(str(round_no), {})
    metadata = coordinator.result_metadata
    return {**panel_metadata(coordinator.result_round, metadata.get('status', 'waiting')),
            'historical_validation': {
                'min_round': MIN_TARGET_ROUND,
                'max_round': coordinator.history[-1].round if getattr(coordinator, 'history', None) else 0,
                'default_method_ids': list(getattr(coordinator, 'selected_method_ids', ()))
                    + ([AI_METHOD_ID] if getattr(coordinator, 'ai_enabled', False) else []),
                'saju_profile_ready': getattr(coordinator, 'saju_profile_ready', False),
            },
            'reviews': _review_rows(coordinator),
            'review_round': coordinator.review_for_round(coordinator.result_round) if hasattr(coordinator, 'review_for_round') else {},
            'review_storage_error': getattr(coordinator, 'review_storage_error', False),
            'review_save_pending': getattr(coordinator, '_review_save_error', False),
            'round': round_no, 'revision': record.get('saved_at', ''),
            'values': book.form_values(round_no) if round_no else {},
            'stored_rounds': sorted(map(int, book.records), reverse=True),
            'purchased': book.report(coordinator.result_history, round_no),
            'draw': draw.to_storage() if draw and metadata['status'] != 'conflict' else None,
            'result_round': coordinator.result_round,
            'result_verification': metadata, 'winning': coordinator.winning_summary,
            'storage_error': coordinator.purchase_storage_error,
            'recommendation_target': coordinator.data.analysis.target_round if coordinator.data else None}


@websocket_api.websocket_command({'type': 'lotto_645/purchases_get', vol.Required('entry_id'): str,
                                 vol.Optional('round'): vol.All(int, vol.Range(min=1, max=999999))})
@websocket_api.require_admin
@websocket_api.async_response
async def purchases_get(hass, connection, msg):
    try:
        result = _view(_coordinator(hass, msg), msg.get('round'))
    except (ValueError, HomeAssistantError):
        connection.send_error(msg['id'], 'unavailable', '로또 통합 또는 회차를 확인하세요')
    else:
        connection.send_result(msg['id'], result)


@websocket_api.websocket_command({'type': 'lotto_645/qr_preview', vol.Required('entry_id'): str,
                                 vol.Required('qr'): vol.All(str, vol.Length(min=1, max=2048))})
@websocket_api.require_admin
@websocket_api.async_response
async def qr_preview(hass, connection, msg):
    try:
        coordinator = _coordinator(hass, msg)
        preview = parse_ticket_qr(msg['qr'])
        # Do not retain/log raw QR, receipt identifier, or an image.
        preview['revision'] = coordinator.purchase_book.records.get(str(preview['round']), {}).get('saved_at', '')
        preview['will_replace'] = bool(preview['revision'])
    except (PurchaseInputError, ValueError, HomeAssistantError):
        connection.send_error(msg['id'], 'invalid_ticket_qr', '지원하는 로또 6/45 QR 주소가 아닙니다. A~E 번호를 직접 입력할 수 있습니다.')
    else:
        connection.send_result(msg['id'], preview)


@websocket_api.websocket_command({'type': 'lotto_645/purchases_save', vol.Required('entry_id'): str,
                                 vol.Required('round'): vol.All(int, vol.Range(min=1, max=999999)),
                                 vol.Required('revision'): vol.All(str, vol.Length(max=100)),
                                 vol.Required('values'): {vol.Optional(f'game_{s}'): vol.All(str, vol.Length(max=150)) for s in 'abcde'},
                                 vol.Optional('clear', default=False): bool})
@websocket_api.require_admin
@websocket_api.async_response
async def purchases_save(hass, connection, msg):
    try:
        coordinator = _coordinator(hass, msg)
        await coordinator.async_save_purchase_record(parse_round(msg['round']), msg['values'],
                                                      clear=msg['clear'], expected_revision=msg['revision'])
        result = _view(coordinator, msg['round'])
    except PurchaseInputError as err:
        connection.send_error(msg['id'], err.code, f'{err.field}: 1~45의 중복 없는 번호 6개를 입력하세요')
    except (HomeAssistantError, OSError) as err:
        code = 'purchase_revision_conflict' if str(err) == 'purchase_revision_conflict' else 'save_failed'
        text = '다른 화면에서 변경되었습니다. 해당 회차를 다시 불러온 후 저장하세요.' if code == 'purchase_revision_conflict' else '저장하지 못했습니다. 기존 번호는 유지됩니다.'
        connection.send_error(msg['id'], code, text)
    else:
        connection.send_result(msg['id'], result)


@websocket_api.websocket_command({'type': 'lotto_645/result_check', vol.Required('entry_id'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def result_check(hass, connection, msg):
    try:
        coordinator = _coordinator(hass, msg)
        await coordinator.async_poll_published_results(force=True)
        result = _view(coordinator)
    except (HomeAssistantError, ValueError, OSError):
        connection.send_error(msg['id'], 'check_failed', '아직 새 결과를 확인하지 못했습니다. 기존 저장번호는 유지됩니다.')
    else:
        connection.send_result(msg['id'], result)


def _strict_int(value):
    if type(value) is not int:
        raise vol.Invalid('integer required')
    return value


def _validation_states(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    shared = hass.data.setdefault(KEY, {'entries': {}, 'registered': False})
    return shared.setdefault('validation_states', {})


def _validation_snapshot(state):
    return {k: v for k, v in state.items() if k != 'task'} if state else {'status': 'idle'}


async def _validation_worker(hass, coordinator, entry_id, round_no, method_ids, state):
    try:
        result = await async_validate_history(hass, coordinator, round_no, method_ids)
        if _coordinator(hass, {'entry_id': entry_id}) is not coordinator:
            raise HomeAssistantError('Integration reloaded during validation')
    except HistoricalValidationError as err:
        state.update(status='error', error_code=err.code, error=str(err))
    except (HomeAssistantError, ValueError, OSError):
        state.update(status='error', error_code='validation_failed',
                     error='과거 검증을 완료하지 못했습니다. 실제 추천번호와 리뷰는 변경되지 않았습니다.')
    else:
        state.update(status='completed', result=result, error=None, error_code=None)
    finally:
        state['finished_at'] = datetime.now(UTC).isoformat()


@websocket_api.websocket_command({
    'type': 'lotto_645/historical_validate', vol.Required('entry_id'): str,
    vol.Required('round'): vol.All(_strict_int, vol.Range(min=MIN_TARGET_ROUND, max=999999)),
    vol.Required('method_ids'): vol.All([vol.In((*METHODS_BY_ID, AI_METHOD_ID))],
                                      vol.Length(min=1, max=len(METHODS_BY_ID) + 1)),
})
@websocket_api.require_admin
@websocket_api.async_response
async def historical_validate(hass, connection, msg):
    """HA owns async_validate_history(...); closing the page cannot cancel it."""
    try:
        coordinator = _coordinator(hass, msg)
        payload = await async_access(hass, msg['entry_id'], published_round(coordinator),
                                     cycle_reader=lambda: published_round(coordinator))
        states = _validation_states(hass)
        state = states.get(msg['entry_id'])
        requested_ids = list(msg['method_ids'])
        if state and state.get('status') == 'running':
            if state.get('round') != msg['round'] or state.get('method_ids') != requested_ids:
                connection.send_error(msg['id'], 'validation_busy', '다른 검증이 계산 중입니다. 완료 후 다시 실행하세요.')
                return
            task = state.get('task')
        else:
            state = {'status': 'running', 'run_id': (state or {}).get('run_id', 0) + 1,
                     'cycle_id': payload['cycle_id'], 'round': msg['round'], 'method_ids': requested_ids,
                     'started_at': datetime.now(UTC).isoformat(), 'result': None}
            states[msg['entry_id']] = state
            task = hass.async_create_task(
                _validation_worker(hass, coordinator, msg['entry_id'], msg['round'], requested_ids, state),
                f'{DOMAIN} historical validation {msg["entry_id"]}',
            )
            state['task'] = task
        if task is None:
            raise ValueError('missing task')
        await asyncio.shield(task)
        if state['status'] != 'completed':
            connection.send_error(msg['id'], state.get('error_code', 'validation_failed'), state.get('error', '검증 실패'))
            return
        latest = await async_access(hass, msg['entry_id'], published_round(coordinator),
                                     cycle_reader=lambda: published_round(coordinator))
        if latest['cycle_id'] != state['cycle_id']:
            raise ScoreConflict('새 당첨회차가 확인되어 이전 검증을 초기화했습니다.')
        connection.send_result(msg['id'], state['result'])
    except ScoreConflict as err:
        connection.send_error(msg['id'], 'validation_cycle_expired', str(err))
    except (HomeAssistantError, ValueError, OSError):
        connection.send_error(msg['id'], 'validation_failed', '검증 저장소 또는 통합 상태를 확인하세요. 기존 기록은 보존합니다.')


@websocket_api.websocket_command({
    'type': 'lotto_645/historical_validation_state', vol.Required('entry_id'): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def historical_validation_state(hass, connection, msg):
    """Restore the persisted cycle even after an HA restart; never generate."""
    try:
        coordinator = _coordinator(hass, msg)
        payload = await async_access(hass, msg['entry_id'], published_round(coordinator),
                                     cycle_reader=lambda: published_round(coordinator))
        state = _validation_states(hass).get(msg['entry_id'])
        if state and state.get('cycle_id') != payload['cycle_id']:
            state = None
        snapshot = _validation_snapshot(state)
        score = score_summary(payload)
        if snapshot['status'] in ('idle', 'completed') and payload.get('last_result'):
            result = {**payload['last_result'], 'validation_cycle': payload['cycle_id'],
                      'validation_scoreboard': score, 'validation_scoreboard_persisted': True}
            snapshot.update(status='completed', result=result, round=result['target_round'],
                            method_ids=result.get('method_ids', []))
        snapshot.update(validation_scoreboard=score)
        connection.send_result(msg['id'], snapshot)
    except (HomeAssistantError, ValueError, OSError):
        connection.send_error(msg['id'], 'score_storage_error', '검증 기록을 복원하지 못했습니다. 원본을 보존합니다.')


@websocket_api.websocket_command({
    'type': 'lotto_645/historical_validation_import', vol.Required('entry_id'): str,
    vol.Required('confirmed'): vol.All(bool, vol.In([True])),
    vol.Required('revision'): vol.All(str, vol.Length(min=64, max=64)),
})
@websocket_api.require_admin
@websocket_api.async_response
async def historical_validation_import(hass, connection, msg):
    """Import server-owned aggregates only after confirming this exact revision."""
    try:
        coordinator = _coordinator(hass, msg)
        if msg.get('confirmed') is not True:
            raise ScoreConflict('리뷰 반영 확인이 필요합니다.')
        payload = await async_access(
            hass, msg['entry_id'], published_round(coordinator), import_revision=msg['revision'],
            cycle_reader=lambda: published_round(coordinator),
        )
        connection.send_result(msg['id'], {**_view(coordinator), 'validation_scoreboard': score_summary(payload)})
    except ScoreConflict as err:
        connection.send_error(msg['id'], 'validation_revision_conflict', str(err))
    except (HomeAssistantError, ValueError, OSError):
        connection.send_error(msg['id'], 'score_storage_error', '리뷰에 저장하지 못했습니다. 다시 확인한 후 재시도하세요.')


def _publish_panel(hass: HomeAssistant, shared: dict) -> None:
    """Replace our panel atomically; never remove the route during a reload."""
    existing = hass.data.get(frontend.DATA_PANELS, {}).get(PATH)
    if existing is not None:
        config = getattr(existing, 'config', None) or {}
        if config.get('_panel_custom', {}).get('name') != 'lotto-ticket-panel':
            raise HomeAssistantError('로또 페이지 경로를 다른 패널이 사용 중입니다')
    frontend.async_register_built_in_panel(
        hass, component_name='custom', frontend_url_path=PATH,
        sidebar_title='로또 복권', sidebar_icon='mdi:ticket-confirmation',
        require_admin=True, update=existing is not None,
        config={'entries': dict(shared['entries']), 'version': VERSION,
                'brand_logo_url': f'/lotto_645_brand/logo.png?v={VERSION}' if shared.get('source_logo_verified') else None,
                '_panel_custom': {'name': 'lotto-ticket-panel', 'embed_iframe': False,
                                  'trust_external': False, 'handle_safe_area': True,
                                  'module_url': f'/lotto_645_static/lotto-panel-shell.js?v={VERSION}'}},
    )


async def async_register_ticket_panel(hass: HomeAssistant, entry) -> None:
    shared = hass.data.setdefault(KEY, {'entries': {}, 'registered': False})
    lock = shared.setdefault('lock', asyncio.Lock())
    async with lock:
        if getattr(entry, 'disabled_by', None) is not None:
            return
        # Register static resources once per HA process, even after all entries
        # are temporarily unloaded. Do not duplicate HTTP routes on reload.
        if not shared.get('static_registered', shared.get('registered', False)):
            await hass.http.async_register_static_paths([
                StaticPathConfig('/lotto_645_static', str(WWW), False)])
            shared['static_registered'] = True
        if not shared.get('brand_registered', False):
            await hass.http.async_register_static_paths([
                StaticPathConfig('/lotto_645_brand', str(Path(__file__).parent / 'brand'), False)])
            shared['brand_registered'] = True
        if not shared.get('commands_registered', shared.get('registered', False)):
            for handler in (purchases_get, qr_preview, purchases_save, result_check, historical_validate,
                            historical_validation_state, historical_validation_import):
                websocket_api.async_register_command(hass, handler)
            shared['commands_registered'] = True
        shared['source_logo_verified'] = await hass.async_add_executor_job(_source_logo_available)
        shared['registered'] = True
        shared['entries'][entry.entry_id] = entry.title
        _publish_panel(hass, shared)


def async_ensure_ticket_panel(hass: HomeAssistant) -> None:
    """Restore a missing registered route without polling any remote service."""
    shared = hass.data.get(KEY)
    if shared and shared.get('registered') and shared['entries'] and not frontend.async_panel_exists(hass, PATH):
        _publish_panel(hass, shared)


def async_remove_ticket_panel(hass: HomeAssistant, entry_id: str, *, permanent: bool = False) -> None:
    shared = hass.data.get(KEY)
    if not shared:
        return
    entry = hass.config_entries.async_get_entry(entry_id)
    if not permanent and entry is not None and getattr(entry, 'disabled_by', None) is None:
        # Options reload / setup retry: keep the link and let the page show
        # 'integration unavailable' instead of disappearing from the sidebar.
        return
    shared['entries'].pop(entry_id, None)
    shared.get('validation_states', {}).pop(entry_id, None)
    if shared['entries']:
        _publish_panel(hass, shared)
    else:
        existing = hass.data.get(frontend.DATA_PANELS, {}).get(PATH)
        if existing and (getattr(existing, 'config', None) or {}).get('_panel_custom', {}).get('name') == 'lotto-ticket-panel':
            frontend.async_remove_panel(hass, PATH)
