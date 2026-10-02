"""Button platform for Lotto 6/45 Analysis."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components import persistent_notification

from .const import DOMAIN
from .coordinator import Lotto645Coordinator
from .entity import Lotto645Entity
from .game_entities import (
    active_button_unique_ids,
    game_entity_name,
    register_button_unique_id,
)
from .methods import METHODS_BY_ID

PARALLEL_UPDATES = 0


def _active_button_unique_ids(coordinator: Lotto645Coordinator) -> set[str]:
    """Registration buttons that should exist for the current selection."""
    return active_button_unique_ids(
        coordinator.entry.entry_id,
        list(coordinator.selected_method_ids),
        {method_id: coordinator.game_count(method_id) for method_id in coordinator.selected_method_ids},
    )


def _prune_stale_purchase_buttons(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: Lotto645Coordinator
) -> None:
    """Delete registration buttons of deselected formulas/games from the registry.

    Options changes reload the entry. Old buttons would otherwise linger as
    unavailable entities, so only this integration's button identities that are
    no longer configured are removed.
    """
    registry = er.async_get(hass)
    active = _active_button_unique_ids(coordinator)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registry_entry.domain != "button" or registry_entry.platform != DOMAIN:
            continue
        unique_id = registry_entry.unique_id
        if not (unique_id.startswith(f"{entry.entry_id}_method_") and unique_id.endswith("_register")
                or unique_id.endswith("_register_all")):
            continue
        if unique_id not in active:
            registry.async_remove(registry_entry.entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up local-regeneration and optional AI buttons."""
    coordinator: Lotto645Coordinator = entry.runtime_data
    _prune_stale_purchase_buttons(hass, entry, coordinator)
    entities: list[ButtonEntity] = [LottoRefreshButton(coordinator), LottoResultCheckButton(coordinator), LottoFinalizationButton(coordinator)]
    if coordinator.ai_enabled:
        entities.append(LottoAiRecommendationButton(coordinator))
    for method_id in coordinator.selected_method_ids:
        label = METHODS_BY_ID[method_id].label
        for game_no in range(1, coordinator.game_count(method_id) + 1):
            entities.append(LottoGamePurchaseButton(coordinator, method_id, game_no, label))
        entities.append(LottoFormulaPurchaseButton(coordinator, method_id, label))
    async_add_entities(entities)


class LottoGamePurchaseButton(Lotto645Entity, ButtonEntity):
    """Register one generated game as a purchased line of the same round."""

    _attr_icon = "mdi:ticket-plus"

    def __init__(self, coordinator: Lotto645Coordinator, method_id: str, game_no: int, label: str) -> None:
        super().__init__(coordinator)
        self.method_id = method_id
        self.game_no = game_no
        self._attr_name = f"{game_entity_name(game_no, label)} 복권 등록"
        self._attr_unique_id = register_button_unique_id(
            coordinator.entry.entry_id, method_id, game_no
        )

    @property
    def _own_recommendation(self):
        """This button stays unavailable until its game really exists."""
        if self.coordinator.data is None:
            return None
        for recommendation in self.coordinator.data.analysis.recommendations_by_method(self.method_id):
            if recommendation.formula_game == self.game_no:
                return recommendation
        return None

    @property
    def available(self) -> bool:
        return super().available and self._own_recommendation is not None

    async def async_press(self) -> None:
        result = await self.coordinator.async_register_generated_purchase(self.method_id, self.game_no)
        _notify(self.coordinator, self._attr_name, result)


class LottoFormulaPurchaseButton(Lotto645Entity, ButtonEntity):
    """Register every generated game of one formula as purchased lines."""

    _attr_icon = "mdi:ticket-confirmation"

    def __init__(self, coordinator: Lotto645Coordinator, method_id: str, label: str) -> None:
        super().__init__(coordinator)
        self.method_id = method_id
        self._attr_name = f"{label} 전체 복권 등록"
        self._attr_unique_id = register_button_unique_id(coordinator.entry.entry_id, method_id)

    @property
    def available(self) -> bool:
        return (
            super().available
            and bool(self.coordinator.data.analysis.recommendations_by_method(self.method_id))
        )

    async def async_press(self) -> None:
        result = await self.coordinator.async_register_generated_purchase(self.method_id)
        _notify(self.coordinator, self._attr_name, result)


def _notify(coordinator: Lotto645Coordinator, name: str, result: dict) -> None:
    """Report which slots were filled; registration is not a silent side effect."""
    rows = result.get("registered") or []
    skipped = result.get("skipped") or []
    if rows:
        slots = ", ".join(f"{row['slot']}번" for row in rows)
        text = f"{name}: {result['round']}회 복권 {slots} 줄에 등록했습니다."
        if result.get("created_tickets"):
            text += f" (새 복권 {result['created_tickets']}장)"
    elif skipped:
        text = f"{name}: 이미 등록된 번호라 건너뛰었습니다."
    else:
        text = f"{name}: 등록할 번호가 없습니다."
    if skipped and rows:
        text += f" {len(skipped)}개 게임은 이미 등록되어 건너뛰었습니다."
    persistent_notification.async_create(
        coordinator.hass, text, "복권 등록", notification_id="lotto_645_purchase_register"
    )


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
