"""Exercise live source pushes through real Home Assistant coordinator classes."""
from dataclasses import replace
from datetime import UTC, datetime
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


async def verify_consensus(hass):
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
    from custom_components.lotto_645.coordinator import Lotto645Coordinator
    from custom_components.lotto_645.methods import METHOD_SELECTED_MEDIAN as MID
    from custom_components.lotto_645.models import AnalysisResult, Lotto645Data, LottoDraw, Recommendation
    from custom_components.lotto_645.sensor import LottoGameSensor
    from custom_components.lotto_645.config_flow import Lotto645OptionsFlow
    from homeassistant.data_entry_flow import FlowResultType

    a, b, c = 'uniform_fisher_yates', 'uniform_floyd', 'bayesian_shrinkage'
    obj = object.__new__(Lotto645Coordinator)
    # This isolated fixture is not created inside a config-entry setup context.
    # Explicit None avoids the deprecated ContextVar fallback in real HA.
    DataUpdateCoordinator.__init__(
        obj, hass, logging.getLogger(__name__), name='consensus-smoke', config_entry=None,
    )
    obj.entry = SimpleNamespace(entry_id='consensus-smoke', options={'selected_methods': [a,b,MID]})
    obj._saju_profile_valid = False
    obj._consensus_save_task = None
    obj._consensus_dirty = False
    obj._set_prediction_snapshot = Mock()
    obj._save_storage = AsyncMock()
    obj.async_request_refresh = AsyncMock(side_effect=AssertionError('Derived updates must not fetch/regenerate'))
    obj._local_generation_nonce = 0
    obj._local_generated_at = None
    obj.review_for_method = lambda key: {}
    obj.history = [LottoDraw(1241, '2026-09-12', (5,10,15,20,25,30), 40)]
    def rec(key, values, index):
        return Recommendation(index, key, key, 'local', values, '', None, {})
    sources = (rec(a, (2,10,18,26,34,42), 1), rec(b, (4,12,20,28,36,44), 2))
    data = Lotto645Data(obj.history[-1], AnalysisResult(1242,1241,sources,{}), 1, datetime.now(UTC),'test')
    sensor = LottoGameSensor(obj, MID)
    seen = []
    remove = obj.async_add_listener(lambda: seen.append((sensor.native_value, sensor.extra_state_attributes)))
    try:
        obj.async_set_updated_data(data)
        assert seen[-1][0] == '3, 11, 19, 27, 35, 43'
        assert sensor.available
        await obj.async_flush_consensus()
        # Same-source notification is a no-op for the derived value/timestamp.
        stamp = seen[-1][1]['consensus_updated_at']
        calls = obj._save_storage.await_count
        obj.async_update_listeners()
        await obj.async_flush_consensus()
        assert seen[-1][1]['consensus_updated_at'] == stamp
        assert obj._save_storage.await_count == calls
        # A push, not the refresh button, changes the source and aggregate.
        updated = replace(sources[1], numbers=(8,16,24,32,40,45))
        obj.async_set_updated_data(replace(obj.data, analysis=replace(obj.data.analysis,
            recommendations=(sources[0], updated, obj.data.analysis.recommendations[-1]))))
        assert seen[-1][0] != '3, 11, 19, 27, 35, 43'
        assert seen[-1][1]['consensus_source_numbers'][b] == list(updated.numbers)
        # Changing selected source membership updates even at the same nonce.
        third = rec(c, (7,15,23,31,39,45), 3)
        obj.entry.options['selected_methods'] = [a,b,c,MID]
        obj.async_set_updated_data(replace(obj.data, analysis=replace(obj.data.analysis,
            recommendations=(*obj.data.analysis.recommendations, third))))
        assert seen[-1][1]['consensus_source_count'] == 3
        obj.entry.options['selected_methods'] = [a,c,MID]
        obj.async_update_listeners()
        assert seen[-1][1]['consensus_source_method_ids'] == [a,c]
        obj.entry.options['selected_methods'] = [a,MID]
        obj.async_update_listeners()
        assert not sensor.available
        assert seen[-1][1]['consensus_status'] == 'waiting_for_sources'
        obj.entry.options['selected_methods'] = [a,b,MID]
        obj.async_update_listeners()
        assert sensor.available
        obj.async_request_refresh.assert_not_called()
        await obj.async_flush_consensus()
        assert obj._save_storage.await_count > calls
        # Real OptionsFlow: uniform/Bayesian inputs count, AI does not.
        flow = Lotto645OptionsFlow(SimpleNamespace(options={}))
        flow.hass = hass; flow.handler = 'consensus-smoke'; flow.flow_id = 'consensus-smoke'
        result = await flow.async_step_recommendations({'selected_methods':[a,b,MID]})
        assert result['type'] == FlowResultType.CREATE_ENTRY, result
        result = await flow.async_step_recommendations({'selected_methods':[a,MID]})
        assert result['errors']['base'] == 'consensus_sources_required', result
        result = await flow.async_step_recommendations({'selected_methods':[a,c,MID]})
        assert result['type'] == FlowResultType.CREATE_ENTRY, result
    finally:
        remove()
        await obj.async_flush_consensus()
    print('PASS: live consensus source push, selection add/remove, no-op, unavailable/recovery, no refresh/AI, real HA sensor and options')
