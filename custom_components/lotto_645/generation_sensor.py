"""One diagnostic progress entity, not seventeen repeated recommendation writes."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .entity import Lotto645Entity


class LottoGenerationProgressSensor(Lotto645Entity, SensorEntity):
    _attr_name = "번호 재생성 진행상황"
    _attr_icon = "mdi:progress-clock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unrecorded_attributes = frozenset({"*"})

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_generation_progress"

    @property
    def available(self) -> bool:
        return True  # An analysis error must remain visible, not 'unavailable'.

    @property
    def native_value(self) -> str:
        return self.coordinator.generation.view["message"]

    @property
    def extra_state_attributes(self) -> dict:
        return self.coordinator.generation.view

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def changed() -> None:
            self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(
            self.hass, self.coordinator.generation.signal, changed,
        ))
