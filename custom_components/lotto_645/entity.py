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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=NAME,
            manufacturer="HA-Lotto-645",
            model="Lotto 6/45 deterministic analysis",
            sw_version=VERSION,
        )
