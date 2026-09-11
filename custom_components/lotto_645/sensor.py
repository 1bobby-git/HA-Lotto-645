"""Sensors for Lotto 6/45 Analysis."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DISCLAIMER,
    FIRST_PRIZE_ODDS,
    PUBLIC_FORMULA_NOTICE,
    SOURCE_NAME,
    SOURCE_RESULT_URL,
)
from .coordinator import Lotto645Coordinator
from .entity import Lotto645Entity
from .methods import METHODS_BY_ID, method_catalog

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
        LottoMethodGuideSensor(coordinator),
        LottoLatestDrawSensor(coordinator),
    ]
    entities.extend(
        LottoGameSensor(coordinator, method_id)
        for method_id in coordinator.selected_method_ids
    )
    if coordinator.ai_enabled:
        entities.append(LottoAiRecommendationSensor(coordinator))
    async_add_entities(entities)


class LottoRecommendationsSensor(Lotto645Entity, SensorEntity):
    """Summary sensor for all selected games."""

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
        games = [item.as_attributes() for item in analysis.recommendations]
        if data.ai_recommendation is not None:
            games.append(data.ai_recommendation.as_attributes())
        return {
            "target_round": analysis.target_round,
            "based_on_round": analysis.based_on_round,
            "history_draws": data.history_count,
            "generated_at": data.generated_at.isoformat(),
            "local_generation_sequence": self.coordinator.local_generation_sequence,
            "local_generated_at": (
                self.coordinator.local_generated_at.isoformat()
                if self.coordinator.local_generated_at
                else None
            ),
            "refresh_behavior": "즉시 새로고침 시 AI를 제외한 선택된 로컬 추천번호를 새 후보로 재생성",
            "source_status": data.source_status,
            "data_source": SOURCE_NAME,
            "source_url": SOURCE_RESULT_URL,
            "selected_method_ids": list(self.coordinator.selected_method_ids),
            "selected_method_count": len(self.coordinator.selected_method_ids),
            "games": games,
            "analysis_summary": analysis.summary,
            "ai_enabled": self.coordinator.ai_enabled,
            "ai_status": data.ai_status,
            "ai_error": data.ai_error,
            "ai_generated_at": (
                data.ai_generated_at.isoformat() if data.ai_generated_at else None
            ),
            "first_prize_odds": FIRST_PRIZE_ODDS,
            "public_formula_notice": PUBLIC_FORMULA_NOTICE,
            "disclaimer": DISCLAIMER,
        }


class LottoMethodGuideSensor(Lotto645Entity, SensorEntity):
    """Expose detailed explanations for every selectable recommendation method."""

    _attr_name = "추천 방식 안내"
    _attr_icon = "mdi:book-open-variant"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_method_guide"

    @property
    def native_value(self) -> int:
        return len(METHODS_BY_ID)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "method_count": len(METHODS_BY_ID),
            "selected_method_ids": list(self.coordinator.selected_method_ids),
            "methods": method_catalog(),
            "usage": "통합 구성에서 여러 방식을 동시에 선택할 수 있으며, 각 방식은 6개 번호 1게임과 핵심 근거를 생성합니다.",
            "refresh_behavior": "즉시 새로고침은 선택된 비AI 추천을 고득점 후보군 안에서 다시 선택합니다.",
            "public_formula_notice": PUBLIC_FORMULA_NOTICE,
            "disclaimer": DISCLAIMER,
        }


class LottoGameSensor(Lotto645Entity, SensorEntity):
    """Recommendation produced by one selected method."""

    _attr_icon = "mdi:numeric"

    def __init__(self, coordinator: Lotto645Coordinator, method_id: str) -> None:
        super().__init__(coordinator)
        self.method_id = method_id
        method = METHODS_BY_ID[method_id]
        self._attr_name = method.label
        self._attr_unique_id = f"{coordinator.entry.entry_id}_method_{method_id}"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.analysis.recommendation_by_method(self.method_id)
            is not None
        )

    @property
    def native_value(self) -> str | None:
        recommendation = self.coordinator.data.analysis.recommendation_by_method(
            self.method_id
        )
        if recommendation is None:
            return None
        return ", ".join(str(number) for number in recommendation.numbers)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        recommendation = data.analysis.recommendation_by_method(self.method_id)
        if recommendation is None:
            return {}
        return {
            **recommendation.as_attributes(),
            "target_round": data.analysis.target_round,
            "based_on_round": data.analysis.based_on_round,
            "history_draws": data.history_count,
            "local_generation_sequence": self.coordinator.local_generation_sequence,
            "first_prize_odds": FIRST_PRIZE_ODDS,
            "public_formula_notice": PUBLIC_FORMULA_NOTICE,
            "disclaimer": DISCLAIMER,
        }


class LottoAiRecommendationSensor(Lotto645Entity, SensorEntity):
    """Validated recommendation generated by the preferred HA AI Task."""

    _attr_name = "Home Assistant AI 추천"
    _attr_icon = "mdi:creation-outline"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_ai_recommendation"

    @property
    def native_value(self) -> str:
        data = self.coordinator.data
        if data.ai_recommendation is not None:
            return ", ".join(
                str(number) for number in data.ai_recommendation.numbers
            )
        return data.ai_status

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        attributes = {
            "status": data.ai_status,
            "error": data.ai_error,
            "generated_at": (
                data.ai_generated_at.isoformat() if data.ai_generated_at else None
            ),
            "configured_ai_task_entity": (
                self.coordinator.configured_ai_entity_id
                or "HA preferred data AI Task"
            ),
            "auto_generate": self.coordinator.ai_auto_generate,
            "manual_local_refresh_does_not_regenerate_ai": True,
            "target_round": data.analysis.target_round,
            "based_on_round": data.analysis.based_on_round,
            "first_prize_odds": FIRST_PRIZE_ODDS,
            "disclaimer": DISCLAIMER,
        }
        if data.ai_recommendation is not None:
            attributes.update(data.ai_recommendation.as_attributes())
        return attributes


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
