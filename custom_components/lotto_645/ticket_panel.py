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
from .const import AI_METHOD_ID
from .methods import METHODS_BY_ID, RETIRED_METHOD_LABELS
from .purchased_tickets import PurchaseInputError, parse_round, parse_games
from .ticket_qr import parse_ticket_qr

KEY = DOMAIN + '_panel'
PATH = 'lotto-645'
PANEL_TAG = 'lotto-ticket-panel-v2-0-0'
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
    rows = []
    for method_id in ids:
        summary = coordinator.review_for_method(method_id) if hasattr(coordinator, 'review_for_method') else {}
        label = METHODS_BY_ID[method_id].label if method_id in METHODS_BY_ID else 'Home Assistant AI 추천' if method_id == AI_METHOD_ID else RETIRED_METHOD_LABELS.get(method_id, method_id)
        rows.append({'method_id': method_id, 'label': label, 'display_name': review_name(label, summary), **summary})
    return rows


def _view(coordinator: Any, round_no: int | None = None, ticket_id: str | None = None) -> dict:
    draw = coordinator.result_draw
    book = coordinator.purchase_book
    round_no = round_no or book.selected_round or (coordinator.data.analysis.target_round if coordinator.data else None)
    record = book.ticket_record(round_no,ticket_id)
    metadata = coordinator.result_metadata
    return {**panel_metadata(coordinator.result_round, metadata.get('status', 'waiting')),
            'reviews': _review_rows(coordinator),
            'review_round': coordinator.review_for_round(coordinator.result_round) if hasattr(coordinator, 'review_for_round') else {},
            'review_storage_error': getattr(coordinator, 'review_storage_error', False),
            'review_save_pending': getattr(coordinator, '_review_save_error', False),
            'round': round_no, 'revision': record.get('saved_at', ''),
            'ticket_id':record.get('ticket_id'),
            'tickets':[{'ticket_id':r['ticket_id'],'saved_at':r['saved_at'],'game_count':len(r['games'])} for r in book.tickets.values() if r['round']==round_no],
            'service_status':getattr(getattr(coordinator,'service',None),'status','unknown'),
            'values': book.form_values(round_no,record.get('ticket_id')) if round_no else {},
            'stored_rounds': sorted(map(int, book.records), reverse=True),
            'purchased': book.report(coordinator.result_history, round_no,record.get('ticket_id')),
            'draw': draw.to_storage() if draw and metadata['status'] != 'conflict' else None,
            'result_round': coordinator.result_round,
            'result_verification': metadata, 'winning': coordinator.winning_summary,
            'storage_error': coordinator.purchase_storage_error,
            'entry_id': coordinator.entry.entry_id,
            'recommendation_target': coordinator.data.analysis.target_round if coordinator.data else None,
            'recommendations': ([row.as_attributes() for row in coordinator.data.analysis.recommendations]
                + ([coordinator.data.ai_recommendation.as_attributes()] if coordinator.data.ai_recommendation else []))
                if coordinator.data else [],
            'recommendation_generated_at': coordinator.data.generated_at.isoformat() if coordinator.data else None,
            'generation_sequence': getattr(coordinator, 'local_generation_sequence', 0),
            'generation_matches':[{'ticket_id':t['ticket_id'],'formula_id':r.method_id,'generation_id':r.details.get('generation_id')} for t in book.tickets.values() if t['round']==round_no for r in (coordinator.data.analysis.recommendations if coordinator.data and coordinator.data.analysis.target_round==round_no else []) if any(tuple(g['numbers'])==r.numbers for g in t['games'])]}


@websocket_api.websocket_command({'type': 'lotto_645/purchases_get', vol.Required('entry_id'): str,
                                 vol.Optional('round'): vol.All(int, vol.Range(min=1, max=999999)), vol.Optional('ticket_id'):vol.All(str,vol.Length(max=80))})
@websocket_api.require_admin
@websocket_api.async_response
async def purchases_get(hass, connection, msg):
    try:
        result = _view(_coordinator(hass, msg), msg.get('round'),msg.get('ticket_id'))
    except (ValueError, HomeAssistantError):
        connection.send_error(msg['id'], 'unavailable', '로또 통합 또는 회차를 확인하세요')
    else:
        connection.send_result(msg['id'], result)


@websocket_api.websocket_command({'type':'lotto_645/purchases_export',vol.Required('entry_id'):str})
@websocket_api.require_admin
@websocket_api.async_response
async def purchases_export(hass,connection,msg):
    try:
        coordinator=_coordinator(hass,msg)
        connection.send_result(msg['id'],coordinator.purchase_book.to_storage())
    except HomeAssistantError:
        connection.send_error(msg['id'],'unavailable','복권 기록을 사용할 수 없습니다.')


@websocket_api.websocket_command({'type': 'lotto_645/qr_preview', vol.Required('entry_id'): str,
                                 vol.Required('qr'): vol.All(str, vol.Length(min=1, max=2048))})
@websocket_api.require_admin
@websocket_api.async_response
async def qr_preview(hass, connection, msg):
    try:
        coordinator = _coordinator(hass, msg)
        preview = parse_ticket_qr(msg['qr'])
        # Do not retain/log raw QR, receipt identifier, or an image.
        preview['revision'] = ''
        preview['will_replace'] = False
        preview['duplicate_candidate'] = any(r['round']==preview['round'] and {tuple(g['numbers']) for g in r['games']} == {tuple(g['numbers']) for g in parse_games(preview['values'])} for r in coordinator.purchase_book.tickets.values())
    except (PurchaseInputError, ValueError, HomeAssistantError):
        connection.send_error(msg['id'], 'invalid_ticket_qr', '지원하는 로또 6/45 QR 주소가 아닙니다. A~E 번호를 직접 입력할 수 있습니다.')
    else:
        connection.send_result(msg['id'], preview)


@websocket_api.websocket_command({'type': 'lotto_645/purchases_save', vol.Required('entry_id'): str,
                                 vol.Required('round'): vol.All(int, vol.Range(min=1, max=999999)),
                                 vol.Required('revision'): vol.All(str, vol.Length(max=100)),
                                 vol.Required('values'): {vol.Optional(f'game_{s}'): vol.All(str, vol.Length(max=150)) for s in 'abcde'},
                                 vol.Optional('clear', default=False): bool,
                                 vol.Optional('ticket_id'):vol.All(str,vol.Length(max=80)),
                                 vol.Optional('new_ticket',default=False):bool})
@websocket_api.require_admin
@websocket_api.async_response
async def purchases_save(hass, connection, msg):
    try:
        coordinator = _coordinator(hass, msg)
        await coordinator.async_save_purchase_record(parse_round(msg['round']), msg['values'],
                                                      clear=msg['clear'], expected_revision=msg['revision'],
                                                      ticket_id=msg.get('ticket_id'),new_ticket=msg['new_ticket'])
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


@websocket_api.websocket_command({'type': 'lotto_645/subscribe', vol.Required('entry_id'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def subscribe_updates(hass, connection, msg):
    """Entry-scoped invalidations survive coordinator reloads. No private payload."""
    entry = hass.config_entries.async_get_entry(msg['entry_id'])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg['id'], 'unavailable', '로또 통합을 확인하세요')
        return
    from homeassistant.core import callback
    @callback
    def changed(event):
        if event.data.get('entry_id') == msg['entry_id']:
            connection.send_event(msg['id'], {'entry_id': msg['entry_id']})
    connection.subscriptions[msg['id']] = hass.bus.async_listen(DOMAIN + '_updated', changed)
    connection.send_result(msg['id'])


def _publish_panel(hass: HomeAssistant, shared: dict) -> None:
    """Replace our panel atomically; never remove the route during a reload."""
    existing = hass.data.get(frontend.DATA_PANELS, {}).get(PATH)
    if existing is not None:
        config = getattr(existing, 'config', None) or {}
        if config.get('_panel_custom', {}).get('name') not in {'lotto-ticket-panel', PANEL_TAG}:
            raise HomeAssistantError('로또 페이지 경로를 다른 패널이 사용 중입니다')
    frontend.async_register_built_in_panel(
        hass, component_name='custom', frontend_url_path=PATH,
        sidebar_title='로또 복권', sidebar_icon='mdi:ticket-confirmation',
        require_admin=True, update=existing is not None,
        config={'entries': dict(shared['entries']), 'version': VERSION,
                'brand_logo_url': f'/lotto_645_brand/logo.png?v={VERSION}' if shared.get('source_logo_verified') else None,
                '_panel_custom': {'name': PANEL_TAG, 'embed_iframe': False,
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
            for handler in (purchases_get, purchases_export, qr_preview, purchases_save, result_check, subscribe_updates):
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
    if shared['entries']:
        _publish_panel(hass, shared)
    else:
        existing = hass.data.get(frontend.DATA_PANELS, {}).get(PATH)
        if existing and (getattr(existing, 'config', None) or {}).get('_panel_custom', {}).get('name') in {'lotto-ticket-panel', PANEL_TAG}:
            frontend.async_remove_panel(hass, PATH)
