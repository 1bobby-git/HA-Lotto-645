"""Sensors for Lotto 6/45 Analysis."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AI_METHOD_ID,
    DISCLAIMER,
    FIRST_PRIZE_ODDS,
    PUBLIC_FORMULA_NOTICE,
    SOURCE_NAME,
    SOURCE_RESULT_URL,
)
from .coordinator import Lotto645Coordinator
from .entity import Lotto645Entity
from .methods import METHOD_MYUNGRI_HETU, METHODS_BY_ID, method_catalog

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
        LottoDrawNumbersSensor(coordinator),
        LottoWinningStatusSensor(coordinator),
    ]
    if METHOD_MYUNGRI_HETU in coordinator.configured_method_ids:
        entities.append(LottoSajuProfileSensor(coordinator))
    entities.extend(
        LottoGameSensor(coordinator, method_id)
        for method_id in coordinator.selected_method_ids
    )
    if coordinator.ai_enabled:
        entities.append(LottoAiRecommendationSensor(coordinator))
    async_add_entities(entities)


class LottoRecommendationsSensor(Lotto645Entity, SensorEntity):
    """Summary sensor for all selected games."""

    _unrecorded_attributes = frozenset({"games", "analysis_summary"})
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
            "saju_profile_status": self.coordinator.saju_profile_status,
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

    _unrecorded_attributes = frozenset({"methods"})
    _attr_name = "추천 방식 안내"
    _attr_icon = "mdi:book-open-variant"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_method_guide"

    @property
    def available(self) -> bool:
        """The static method catalog does not depend on lottery network data."""
        return True

    @property
    def native_value(self) -> str:
        """Show a human-readable count instead of the ambiguous bare number 16."""
        return f"{len(METHODS_BY_ID)}개 추천 방식"

    @property
    def extra_state_attributes(self) -> dict:
        catalog = method_catalog()
        return {
            "method_count": len(METHODS_BY_ID),
            "selected_method_ids": list(self.coordinator.selected_method_ids),
            "selected_method_names": [
                METHODS_BY_ID[method_id].label
                for method_id in self.coordinator.selected_method_ids
            ],
            "methods": catalog,
            "how_to_view": (
                "이 엔티티의 상세 속성에서 methods 목록을 확인하거나, 각 추천번호 엔티티의 "
                "method_description 속성에서 해당 방식의 설명을 확인하세요. Home Assistant에서 "
                "속성이 접혀 보이면 개발자 도구 > 상태에서 '추천 방식 안내' 엔티티를 선택하면 전체 목록을 볼 수 있습니다."
            ),
            "usage": "통합 구성에서 여러 방식을 동시에 선택할 수 있으며, 각 방식은 6개 번호 1게임과 핵심 근거를 생성합니다.",
            "refresh_behavior": "즉시 새로고침은 선택된 비AI 추천을 고득점 후보군 안에서 다시 선택합니다.",
            "public_formula_notice": PUBLIC_FORMULA_NOTICE,
            "disclaimer": DISCLAIMER,
        }


class LottoSajuProfileSensor(Lotto645Entity, SensorEntity):
    """Show whether personal Saju is configured and expose derived natal context."""

    _unrecorded_attributes = frozenset({"*"})
    _attr_name = "명리 사주 프로필"
    _attr_icon = "mdi:yin-yang"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_saju_profile"

    @property
    def available(self) -> bool:
        """Profile configuration remains inspectable even if draw data is offline."""
        return True

    @property
    def native_value(self) -> str:
        return "준비됨" if self.coordinator.saju_profile_ready else "설정 필요"

    @property
    def extra_state_attributes(self) -> dict:
        base = {
            "status": self.coordinator.saju_profile_status,
            "required_before_use": True,
            "required_fields": ["양력/음력", "생년월일", "출생시간", "성별", "출생지", "시간대"],
            "where_to_enter": "설정 > 기기 및 서비스 > Lotto 6/45 Analysis > 구성 > 명리 사주정보 입력·수정",
            "privacy": "입력값은 Home Assistant 구성에 로컬 저장되며 로또 미러와 HA AI 추천 프롬프트에 원본 생년월일·출생시간·출생지를 보내지 않습니다.",
        }
        data = self.coordinator.data
        if data is None:
            base["message"] = "구성 > 명리 사주정보 입력·수정에서 프로필을 저장하세요."
            return base
        recommendation = data.analysis.recommendation_by_method(METHOD_MYUNGRI_HETU)
        if recommendation is None:
            base["message"] = "통합 구성 > 명리 사주정보 입력·수정을 완료하면 명리 권장 추천이 활성화됩니다."
            return base
        details = recommendation.details
        for key in (
            "structural_analysis", "favorable_analysis", "luck_layers", "calendar_rules",
            "shensha", "rule_version", "rule_sources", "calculation_warnings",
            "four_pillars", "pillar_details", "day_master",
            "day_master_element", "day_master_strength", "support_ratio",
            "five_element_balance", "ten_god_element_roles", "favorable_elements",
            "avoid_elements", "current_daewoon", "target_draw_date",
            "target_draw_time", "target_draw_four_pillars", "target_interactions",
            "traditional_notice", "privacy_notice",
        ):
            if key in details:
                base[key] = details[key]
        return base


class LottoGameSensor(Lotto645Entity, SensorEntity):
    """Recommendation produced by one selected method."""

    # Keep current explanations accessible, but do not duplicate a large natal
    # profile and luck timeline in Recorder on every recommendation refresh.
    _unrecorded_attributes = frozenset({
        "pillar_details", "current_daewoon", "target_interactions", "structural_analysis",
        "favorable_analysis", "luck_layers", "number_score_trace", "rule_sources",
        "calculation_warnings", "calendar_rules", "shensha", "target_draw_four_pillars",
    })
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
        method = METHODS_BY_ID[self.method_id]
        return {
            **recommendation.as_attributes(),
            "method_category": method.category,
            "method_description": method.description,
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


class LottoDrawNumbersSensor(Lotto645Entity, SensorEntity):
    """Show the six main numbers of the latest completed official draw."""

    _attr_name = "추첨번호"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_draw_numbers"

    @property
    def native_value(self) -> str:
        draw = self.coordinator.data.latest_draw
        return ", ".join(str(number) for number in draw.numbers)

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


class LottoWinningStatusSensor(Lotto645Entity, SensorEntity):
    """Summarize how the saved recommendations performed after a draw."""

    _unrecorded_attributes = frozenset({"results", "winners", "losers"})
    _attr_name = "당첨 여부"
    _attr_icon = "mdi:ticket-percent-outline"

    def __init__(self, coordinator: Lotto645Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_winning_status"

    @property
    def native_value(self) -> str:
        evaluation = self.coordinator.last_draw_evaluation
        if not evaluation:
            return "판정 대기"
        winning_count = int(evaluation.get("winning_game_count", 0))
        if winning_count:
            return f"{winning_count}개 당첨 · 최고 {evaluation.get('highest_prize', '당첨')}"
        return "전체 미당첨"

    def _decorate_result(self, result: dict) -> dict:
        method_id = str(result.get("method_id", ""))
        if method_id == AI_METHOD_ID:
            unique_id = f"{self.coordinator.entry.entry_id}_ai_recommendation"
        else:
            unique_id = f"{self.coordinator.entry.entry_id}_method_{method_id}"
        return {**result, "recommendation_sensor_unique_id": unique_id}

    @property
    def extra_state_attributes(self) -> dict:
        evaluation = self.coordinator.last_draw_evaluation
        if not evaluation:
            return {
                "status": "waiting",
                "message": (
                    "현재 추천 대상 회차의 추첨번호가 갱신되면 저장된 모든 추천 센서를 "
                    "자동으로 대조해 1~5등 또는 미당첨을 판정합니다."
                ),
                "prize_rules": "1등=6개, 2등=5개+보너스, 3등=5개, 4등=4개, 5등=3개",
            }
        results = [self._decorate_result(item) for item in evaluation.get("results", [])]
        winners = [item for item in results if item.get("status") == "당첨"]
        losers = [item for item in results if item.get("status") == "미당첨"]
        return {
            "status": "evaluated",
            "round": evaluation.get("round"),
            "draw_date": evaluation.get("draw_date"),
            "winning_numbers": evaluation.get("winning_numbers"),
            "bonus_number": evaluation.get("bonus_number"),
            "evaluated_at": evaluation.get("evaluated_at"),
            "prediction_based_on_round": evaluation.get("prediction_based_on_round"),
            "prediction_generation_sequence": evaluation.get("prediction_generation_sequence"),
            "prediction_generated_at": evaluation.get("prediction_generated_at"),
            "checked_game_count": evaluation.get("checked_game_count", 0),
            "winning_game_count": evaluation.get("winning_game_count", 0),
            "losing_game_count": evaluation.get("losing_game_count", 0),
            "highest_prize": evaluation.get("highest_prize"),
            "highest_prize_sensor": evaluation.get("highest_prize_sensor"),
            "results": results,
            "winners": winners,
            "losers": losers,
            "prize_rules": "1등=6개, 2등=5개+보너스, 3등=5개, 4등=4개, 5등=3개",
            "note": "실제 entity_id는 사용자가 이름을 변경할 수 있으므로 센서명과 unique_id를 함께 제공합니다.",
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
