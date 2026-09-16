"""Admin-only portfolio previews; bounded executor work, no persistent mutations."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from functools import partial
import threading

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .constraints import ConstraintError, RULES_KEY
from .portfolio import generate_portfolio

KEY = 'lotto_645_portfolio_commands'
JOBS_KEY = 'lotto_645_portfolio_jobs'


def _integer(value):
    if type(value) is not int:
        raise vol.Invalid('정수가 필요합니다')
    return value


@websocket_api.websocket_command({
    'type': 'lotto_645/portfolio_coverage', vol.Required('entry_id'): str,
    vol.Required('candidate_numbers'): vol.All([vol.All(_integer, vol.Range(min=1, max=45))], vol.Length(min=6, max=45)),
    vol.Required('ticket_count'): vol.All(_integer, vol.Range(min=1, max=5)),
    vol.Optional('mode', default='balanced'): vol.In(('balanced', 'coverage', 'wheel9')),
    vol.Optional('max_overlap', default=6): vol.All(_integer, vol.Range(min=0, max=6)),
    vol.Optional('apply_rules', default=True): bool,
})
@websocket_api.require_admin
@websocket_api.async_response
async def portfolio_preview(hass, connection, msg):
    """Resolve entry every time; an unfinished job cannot be duplicated."""
    from .ticket_panel import _coordinator

    cancel = threading.Event()
    try:
        owner = _coordinator(hass, msg)
        history = tuple(owner.history)
        if not history:
            raise ConstraintError('history_unavailable', '공식 이력을 먼저 불러오세요')
        jobs = hass.data.setdefault(JOBS_KEY, {})
        entry_id = msg['entry_id']
        if entry_id in jobs and not jobs[entry_id].done():
            raise ConstraintError('generation_busy', '이 통합의 조합 설계가 진행 중입니다')
        rules = deepcopy(owner.entry.options.get(RULES_KEY)) if msg.get('apply_rules', True) else None
        blocked = {tuple(row.numbers) for row in history}
        if owner.data:
            blocked.update(tuple(row.numbers) for row in owner.data.analysis.recommendations)

        def checkpoint(_done, _total):
            if cancel.is_set():
                raise ConstraintError('generation_cancelled', '조합 설계를 중단했습니다')

        worker = hass.async_add_executor_job(partial(
            generate_portfolio, tuple(msg['candidate_numbers']), msg['ticket_count'],
            mode=msg.get('mode', 'balanced'), max_overlap=msg.get('max_overlap', 6),
            rules=rules, previous=history[-1].numbers, blocked=blocked, checkpoint=checkpoint,
        ))
        jobs[entry_id] = worker

        def finished(future):
            if jobs.get(entry_id) is future:
                jobs.pop(entry_id, None)
            if not future.cancelled():
                future.exception()  # Retrieve even when a timed-out caller stopped waiting.

        worker.add_done_callback(finished)
        result = await asyncio.wait_for(asyncio.shield(worker), timeout=20)
        if _coordinator(hass, msg) is not owner or tuple(owner.history) != history:
            raise ConstraintError('stale_context', '통합 또는 추첨 이력이 바뀌었습니다. 다시 생성하세요')
        result.update(based_on_round=history[-1].round, target_round=history[-1].round + 1,
                      saved_rules_applied=msg.get('apply_rules', True))
    except TimeoutError:
        cancel.set()
        connection.send_error(msg['id'], 'search_limit', '계산 시간 한도를 초과했습니다. 조건을 완화하거나 결과를 저장하지 않았습니다')
    except asyncio.CancelledError:
        cancel.set()
        raise
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg['id'], getattr(err, 'code', 'portfolio_unavailable'), str(err))
    else:
        connection.send_result(msg['id'], result)


@callback
def async_register_portfolio_commands(hass):
    if hass.data.get(KEY):
        return
    websocket_api.async_register_command(hass, portfolio_preview)
    hass.data[KEY] = True
