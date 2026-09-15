"""Observe published draws without polling the network or regenerating numbers."""
from __future__ import annotations

import logging

from .historical_validation_scores import async_access, published_round

_LOGGER = logging.getLogger(__name__)


async def async_setup_validation(hass, coordinator):
    entry = coordinator.entry
    pending = None
    observed = 0

    async def synchronize():
        nonlocal observed
        try:
            payload = await async_access(hass, entry.entry_id, published_round(coordinator), cycle_reader=lambda: published_round(coordinator))
            observed = payload['cycle_round']
            states = hass.data.get('lotto_645_panel', {}).get('validation_states', {})
            state = states.get(entry.entry_id)
            if state and state.get('cycle_id') != payload['cycle_id']:
                # Do not cancel a thread. Let its lease drain; the runtime rejects
                # its stale result. Keep the running state until it has finished.
                if state.get('status') != 'running':
                    states.pop(entry.entry_id, None)
                hass.data.get('lotto_645_last_historical_validation', {}).pop(entry.entry_id, None)
        except Exception as err:
            _LOGGER.warning('과거 검증 초기화/복원 재시도 필요 (%s)', type(err).__name__)

    def changed():
        nonlocal pending
        if published_round(coordinator) > observed and (pending is None or pending.done()):
            pending = hass.async_create_task(synchronize(), 'lotto-validation-cycle')

    await synchronize()
    entry.async_on_unload(coordinator.async_add_listener(changed))
