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
    """Set up local-regeneration and optional AI buttons."""
    coordinator: Lotto645Coordinator = entry.runtime_data
    entities: list[ButtonEntity] = [LottoRefreshButton(coordinator), LottoResultCheckButton(coordinator), LottoFinalizationButton(coordinator)]
    if coordinator.ai_enabled:
        entities.append(LottoAiRecommendationButton(coordinator))
    async_add_entities(entities)


class LottoRefreshButton(Lotto645Entity, ButtonEntity):
    """Refresh history and regenerate all non-AI recommendations."""

    _attr_name = "즉시 새로고침 · 번호 재생성"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_and_regenerate()


class LottoAiRecommendationButton(Lotto645Entity, ButtonEntity):
    """Generate a new recommendation through the configured HA AI Task."""

    _attr_name = "AI 추천 생성"
    _attr_icon = "mdi:creation"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_generate_ai"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.ai_status != "generating"

    async def async_press(self) -> None:
        await self.coordinator.async_generate_ai_recommendation()


class LottoResultCheckButton(Lotto645Entity, ButtonEntity):
    """Action button lives in Controls on the result device, not primary sensors."""
    _lotto_group = "results"
    _attr_name = "추첨 결과 지금 확인"
    _attr_icon = "mdi:cloud-sync-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_check_result"

    async def async_press(self):
        await self.coordinator.async_poll_published_results(force=True)


class LottoFinalizationButton(Lotto645Entity, ButtonEntity):
    """Explicit user/automation action; never triggered by coordinator refresh."""
    _attr_name = "최종 번호 산출"
    _attr_icon = "mdi:selection-multiple"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_finalize"

    @property
    def available(self):
        summary=getattr(self.coordinator.service,'final_summary',{})
        return super().available and summary.get('input_state')=='ready' and summary.get('default_execution_ready',False) and summary.get('connection_status')!='unavailable' and summary.get('job_status') not in ('queued','running')

    async def async_press(self):
        from homeassistant.exceptions import HomeAssistantError
        from .lab_client import LabServiceError
        try:await self.coordinator.service.finalization_state('start')
        except (LabServiceError,ValueError,OSError) as error:
            raise HomeAssistantError('최종 산출 준비 상태와 출력 게임 수를 패널에서 확인하세요.') from error
