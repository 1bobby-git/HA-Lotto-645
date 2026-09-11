"""Button platform for Lotto 6/45 Analysis."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import Lotto645Coordinator
from .entity import Lotto645Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up refresh and optional AI buttons."""
    coordinator: Lotto645Coordinator = entry.runtime_data
    entities: list[ButtonEntity] = [LottoRefreshButton(coordinator)]
    if coordinator.ai_enabled:
        entities.append(LottoAiRecommendationButton(coordinator))
    async_add_entities(entities)


class LottoRefreshButton(Lotto645Entity, ButtonEntity):
    """Request an immediate official-result refresh."""

    _attr_name = "즉시 새로고침"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class LottoAiRecommendationButton(Lotto645Entity, ButtonEntity):
    """Generate a new recommendation through the configured HA AI Task."""

    _attr_name = "AI 추천 생성"
    _attr_icon = "mdi:creation"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_generate_ai"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.ai_status != "generating"
        )

    async def async_press(self) -> None:
        await self.coordinator.async_generate_ai_recommendation()
