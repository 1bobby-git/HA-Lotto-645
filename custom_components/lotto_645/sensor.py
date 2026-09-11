"""Sensors for Lotto 6/45 Analysis."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISCLAIMER, FIRST_PRIZE_ODDS, SOURCE_NAME, SOURCE_RESULT_URL
from .coordinator import Lotto645Coordinator
from .entity import Lotto645Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lotto sensors."""
    coordinator: Lotto645Coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        LottoRecommendationsSensor(coordinator),
        LottoLatestDrawSensor(coordinator),
    ]
    entities.extend(LottoGameSensor(coordinator, index) for index in range(5))
    async_add_entities(entities)


class LottoRecommendationsSensor(Lotto645Entity, SensorEntity):
    """Summary sensor for all five games."""

    _attr_name = "추천 요약"
    _attr_icon = "mdi:ticket-confirmation-outline"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_recommendations"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.analysis.target_round

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        analysis = data.analysis
        return {
            "target_round": analysis.target_round,
            "based_on_round": analysis.based_on_round,
            "history_draws": data.history_count,
            "generated_at": data.generated_at.isoformat(),
            "source_status": data.source_status,
            "data_source": SOURCE_NAME,
            "source_url": SOURCE_RESULT_URL,
            "games": [rec.as_attributes() for rec in analysis.recommendations],
            "analysis_summary": analysis.summary,
            "first_prize_odds": FIRST_PRIZE_ODDS,
            "disclaimer": DISCLAIMER,
        }


class LottoGameSensor(Lotto645Entity, SensorEntity):
    """One of the five recommended games."""

    _attr_icon = "mdi:numeric"

    def __init__(self, coordinator: Lotto645Coordinator, index: int) -> None:
        super().__init__(coordinator)
        self.index = index
        self._attr_name = f"추천 게임 {index + 1}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_game_{index + 1}"

    @property
    def native_value(self) -> str:
        recommendation = self.coordinator.data.analysis.recommendations[self.index]
        return ", ".join(str(number) for number in recommendation.numbers)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        recommendation = data.analysis.recommendations[self.index]
        return {
            **recommendation.as_attributes(),
            "target_round": data.analysis.target_round,
            "based_on_round": data.analysis.based_on_round,
            "history_draws": data.history_count,
            "first_prize_odds": FIRST_PRIZE_ODDS,
            "disclaimer": DISCLAIMER,
        }


class LottoLatestDrawSensor(Lotto645Entity, SensorEntity):
    """Latest official draw sensor."""

    _attr_name = "최신 당첨 결과"
    _attr_icon = "mdi:trophy-outline"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_latest_draw"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.latest_draw.round

    @property
    def extra_state_attributes(self) -> dict:
        draw = self.coordinator.data.latest_draw
        return {
            "round": draw.round,
            "draw_date": draw.draw_date,
            "winning_numbers": list(draw.numbers),
            "bonus_number": draw.bonus,
            "first_prize_winners": draw.first_prize_winners,
            "first_prize_amount": draw.first_prize_amount,
            "source_status": self.coordinator.data.source_status,
            "data_source": SOURCE_NAME,
            "source_url": SOURCE_RESULT_URL,
        }
