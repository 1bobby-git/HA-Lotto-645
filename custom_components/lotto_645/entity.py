"""Base entity for Lotto 6/45 Analysis."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import Lotto645Coordinator


class Lotto645Entity(CoordinatorEntity[Lotto645Coordinator]):
    """Base coordinator entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        group = getattr(self, "_lotto_group", "recommendations")
        if group == "results":
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{coordinator.entry.entry_id}_results")},
                name="로또 추첨·당첨 결과", manufacturer="HA-Lotto-645",
                model="추첨 결과 · 구매번호 · 당첨 상세", sw_version=VERSION,
                via_device=(DOMAIN, coordinator.entry.entry_id),
                configuration_url="homeassistant://lotto-645",
            )
            return
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=NAME,
            manufacturer="HA-Lotto-645",
            model="Selectable Lotto 6/45 analysis + HA AI Task",
            sw_version=VERSION,
            configuration_url="homeassistant://lotto-645",
        )
