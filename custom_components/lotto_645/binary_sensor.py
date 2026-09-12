"""One binary result entity with every ticket/method's detailed prize outcome."""
from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity
from .entity import Lotto645Entity
from .result_details import winning_attributes

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LottoWinningDetailSensor(entry.runtime_data)])


class LottoWinningDetailSensor(Lotto645Entity, BinarySensorEntity):
    _lotto_group = 'results'
    _attr_has_entity_name = False
    _attr_icon = 'mdi:ticket-confirmation-outline'
    _unrecorded_attributes = frozenset({'results', 'winners', 'losers'})

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f'{coordinator.entry.entry_id}_winning_detail'

    @property
    def name(self):
        round_no = self.coordinator.result_round
        return f'{round_no}회 당첨 상세' if round_no else '당첨 상세'

    @property
    def available(self):
        return self.coordinator.data is not None

    @property
    def is_on(self):
        report = self.coordinator.winning_summary
        if (not report or report.get('status') != 'evaluated'
                or not report.get('checked_game_count')):
            return None  # unavailable/unknown is NOT a losing ticket
        return report['winning_game_count'] > 0

    @property
    def extra_state_attributes(self):
        return winning_attributes(self.coordinator)
