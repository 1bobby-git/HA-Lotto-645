"""Admin-only, read-only research previews. No purchase/review/AI mutations."""
from __future__ import annotations

from functools import partial

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .research_formulas import covering_wheel, fairness_diagnostic

KEY = 'lotto_645_research_commands'


def _integer(value):
    if type(value) is not int or not 1 <= value <= 45:
        raise vol.Invalid('1~45 정수가 필요합니다')
    return value


@websocket_api.websocket_command({
    'type': 'lotto_645/covering_wheel', vol.Required('entry_id'): str,
    vol.Required('candidate_numbers'): vol.All([_integer], vol.Length(min=8, max=8)),
})
@websocket_api.require_admin
@websocket_api.async_response
async def wheel_preview(hass, connection, msg):
    from .ticket_panel import _coordinator

    try:
        owner = _coordinator(hass, msg)
        history = tuple(owner.history)
        if not history:
            raise ValueError('공식 이력을 먼저 불러오세요')
        blocked = {tuple(draw.numbers) for draw in history}
        if owner.data:
            blocked.update(tuple(row.numbers) for row in owner.data.analysis.recommendations)
        result = await hass.async_add_executor_job(partial(
            covering_wheel, tuple(msg['candidate_numbers']), excluded_combinations=blocked,
        ))
        if _coordinator(hass, msg) is not owner:
            raise HomeAssistantError('통합이 변경되었습니다. 다시 생성하세요')
        result.update({'based_on_round': history[-1].round, 'target_round': history[-1].round + 1})
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg['id'], 'research_unavailable', str(err))
    else:
        connection.send_result(msg['id'], result)


@websocket_api.websocket_command({
    'type': 'lotto_645/research_diagnostics', vol.Required('entry_id'): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def diagnostics(hass, connection, msg):
    from .ticket_panel import _coordinator

    try:
        owner = _coordinator(hass, msg)
        history = tuple(owner.history)
        result = await hass.async_add_executor_job(fairness_diagnostic, tuple(d.numbers for d in history))
        if _coordinator(hass, msg) is not owner:
            raise HomeAssistantError('통합이 변경되었습니다. 다시 확인하세요')
        result['history_cutoff_round'] = history[-1].round if history else None
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg['id'], 'research_unavailable', str(err))
    else:
        connection.send_result(msg['id'], result)


@callback
def async_register_research_commands(hass):
    """Register once per HA instance; resolve the entry on EVERY request."""
    if hass.data.get(KEY):
        return
    websocket_api.async_register_command(hass, wheel_preview)
    websocket_api.async_register_command(hass, diagnostics)
    hass.data[KEY] = True
