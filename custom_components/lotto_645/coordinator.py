"""Data coordinator for Lotto 6/45 Analysis."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.ai_task import async_generate_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .analysis import build_analysis
from .api import LottoApiClient, LottoApiError
from .const import (
    AI_MAX_ATTEMPTS,
    AI_METHOD_ID,
    CONF_AI_AUTO_GENERATE,
    CONF_AI_TASK_ENTITY_ID,
    CONF_ENABLE_AI,
    CONF_SELECTED_METHODS,
    DEFAULT_AI_AUTO_GENERATE,
    DEFAULT_ENABLE_AI,
    DISCLAIMER,
    DOMAIN,
    FIRST_PRIZE_ODDS,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)
from .methods import DEFAULT_METHOD_IDS, normalize_method_ids
from .models import AnalysisResult, Lotto645Data, LottoDraw, Recommendation

_LOGGER = logging.getLogger(__name__)


class AiRecommendationError(HomeAssistantError):
    """Raised when an AI Task result cannot be accepted safely."""


class Lotto645Coordinator(DataUpdateCoordinator[Lotto645Data]):
    """Coordinate remote draw updates, local analysis, and optional AI Tasks."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.entry = entry
        self.client = LottoApiClient(async_get_clientsession(hass))
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
        )
        self.history: list[LottoDraw] = []
        self._cached_ai_recommendation: Recommendation | None = None
        self._cached_ai_generated_at: datetime | None = None

    @property
    def selected_method_ids(self) -> tuple[str, ...]:
        """Return configured local recommendation methods."""
        return normalize_method_ids(
            self.entry.options.get(CONF_SELECTED_METHODS, DEFAULT_METHOD_IDS)
        )

    @property
    def ai_enabled(self) -> bool:
        return bool(
            self.entry.options.get(CONF_ENABLE_AI, DEFAULT_ENABLE_AI)
        )

    @property
    def ai_auto_generate(self) -> bool:
        return bool(
            self.entry.options.get(
                CONF_AI_AUTO_GENERATE, DEFAULT_AI_AUTO_GENERATE
            )
        )

    @property
    def configured_ai_entity_id(self) -> str | None:
        value = self.entry.options.get(CONF_AI_TASK_ENTITY_ID)
        return str(value) if value else None

    async def _async_setup(self) -> None:
        """Load cached history and a valid cached AI result once."""
        payload = await self._store.async_load()
        if not payload:
            return
        try:
            draws = [
                LottoDraw.from_storage(item)
                for item in payload.get("draws", [])
            ]
            draws.sort(key=lambda draw: draw.round)
            if draws and draws[0].round == 1:
                contiguous = [draw.round for draw in draws] == list(
                    range(1, draws[-1].round + 1)
                )
                if contiguous:
                    self.history = draws
            if not self.history:
                _LOGGER.warning(
                    "로또 캐시가 연속된 전체 회차가 아니어서 다시 동기화합니다"
                )
                return

            ai_payload = payload.get("ai_recommendation")
            if isinstance(ai_payload, dict):
                recommendation = Recommendation.from_storage(ai_payload)
                if recommendation.details.get("target_round") == (
                    self.history[-1].round + 1
                ):
                    self._cached_ai_recommendation = recommendation
                    generated = payload.get("ai_generated_at")
                    if generated:
                        self._cached_ai_generated_at = datetime.fromisoformat(
                            str(generated)
                        )
        except (KeyError, TypeError, ValueError) as err:
            self.history = []
            self._cached_ai_recommendation = None
            self._cached_ai_generated_at = None
            _LOGGER.warning(
                "로또 캐시를 읽지 못해 다시 동기화합니다: %s", err
            )

    async def _save_storage(self) -> None:
        await self._store.async_save(
            {
                "latest_round": self.history[-1].round if self.history else 0,
                "draws": [draw.to_storage() for draw in self.history],
                "ai_recommendation": (
                    self._cached_ai_recommendation.to_storage()
                    if self._cached_ai_recommendation
                    else None
                ),
                "ai_generated_at": (
                    self._cached_ai_generated_at.isoformat()
                    if self._cached_ai_generated_at
                    else None
                ),
            }
        )

    async def _async_update_data(self) -> Lotto645Data:
        """Fetch new draws and rebuild selected recommendations when required."""
        source_status = "live"
        changed = False
        try:
            latest_round = await self.client.async_latest_round()
            if not self.history:
                self.history = await self.client.async_fetch_full_history(
                    latest_round
                )
                changed = True
            else:
                cached_latest = self.history[-1].round
                if latest_round > cached_latest:
                    new_draws = await self.client.async_fetch_range(
                        cached_latest + 1, latest_round
                    )
                    by_round = {draw.round: draw for draw in self.history}
                    by_round.update({draw.round: draw for draw in new_draws})
                    self.history = [
                        by_round[index] for index in range(1, latest_round + 1)
                    ]
                    changed = True
                    self._cached_ai_recommendation = None
                    self._cached_ai_generated_at = None
                elif latest_round < cached_latest:
                    source_status = "cache_ahead_of_source"
        except LottoApiError as err:
            if not self.history:
                kwargs: dict[str, Any] = {}
                if err.retry_after is not None:
                    kwargs["retry_after"] = err.retry_after
                raise UpdateFailed(str(err), **kwargs) from err
            source_status = "cached_fallback"
            _LOGGER.debug(
                "동행복권 통신 실패, 마지막 정상 캐시를 유지합니다: %s", err
            )

        if not self.history:
            raise UpdateFailed("분석할 로또 회차 데이터가 없습니다")

        if self.data is not None and not changed:
            configured = tuple(
                self.data.analysis.summary.get("selected_method_ids", [])
            )
            if configured == self.selected_method_ids:
                if self.data.source_status == source_status:
                    return self.data
                return replace(self.data, source_status=source_status)

        try:
            analysis = await self.hass.async_add_executor_job(
                build_analysis, self.history, self.selected_method_ids
            )
        except ValueError as err:
            raise UpdateFailed(f"로또 분석 실패: {err}") from err

        ai_recommendation = (
            self._cached_ai_recommendation if self.ai_enabled else None
        )
        ai_generated_at = (
            self._cached_ai_generated_at if self.ai_enabled else None
        )
        ai_status = (
            "ready"
            if ai_recommendation is not None
            else ("idle" if self.ai_enabled else "disabled")
        )
        ai_error: str | None = None

        if (
            self.ai_enabled
            and self.ai_auto_generate
            and ai_recommendation is None
        ):
            try:
                ai_recommendation = await self._async_create_ai_recommendation(
                    analysis, self.configured_ai_entity_id
                )
                ai_generated_at = datetime.now(UTC)
                self._cached_ai_recommendation = ai_recommendation
                self._cached_ai_generated_at = ai_generated_at
                ai_status = "ready"
            except (AiRecommendationError, HomeAssistantError, KeyError) as err:
                ai_status = "error"
                ai_error = str(err)
                _LOGGER.warning("AI 로또 추천 자동 생성 실패: %s", err)

        if changed or ai_recommendation is not None:
            await self._save_storage()

        return Lotto645Data(
            latest_draw=self.history[-1],
            analysis=analysis,
            history_count=len(self.history),
            generated_at=datetime.now(UTC),
            source_status=source_status,
            ai_recommendation=ai_recommendation,
            ai_status=ai_status,
            ai_error=ai_error,
            ai_generated_at=ai_generated_at,
        )

    def _ai_structure(self) -> vol.Schema:
        number_selector = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=45,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        return vol.Schema(
            {
                vol.Required(f"number_{index}"): number_selector
                for index in range(1, 7)
            }
            | {
                vol.Required("reason"): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
                vol.Optional("basis"): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
            }
        )

    def _ai_prompt(self, analysis: AnalysisResult, attempt: int) -> str:
        local_games = "\n".join(
            f"- {item.label}: {', '.join(map(str, item.numbers))} / {item.reason}"
            for item in analysis.recommendations
        )
        summary = analysis.summary
        retry_text = (
            "이전 결과가 중복 번호, 범위 오류 또는 과거 1등 완전일치로 거절되었습니다. "
            "반드시 다른 유효 조합을 만드세요."
            if attempt > 1
            else ""
        )
        return f"""당신은 로또 6/45 통계 해석 보조 엔진입니다.
아래 데이터만 참고해 {analysis.target_round}회용 번호 6개와 핵심 근거를 생성하세요.
추첨은 독립 무작위이며 당첨을 보장하거나 확률을 높인다고 표현하면 안 됩니다.

필수 규칙:
1. 1~45의 서로 다른 정수 정확히 6개
2. 과거 1회~{analysis.based_on_round}회 1등 조합과 완전히 동일하지 않게 선택
3. 제공된 로컬 추천과 완전히 같은 조합은 피하고 통계적 관점을 달리할 것
4. 근거는 실제 제공 통계에 연결해 180자 이내 한국어로 작성
5. number_1~number_6 필드에는 번호를 하나씩 넣을 것
{retry_text}

분석 기준 회차: {analysis.based_on_round}
위상 변화 상위: {summary.get('top_phase_change')}
다음 회차 전이 상위: {summary.get('top_transition')}
번호쌍 그래프 상위: {summary.get('top_graph_strength')}
로컬 추천:
{local_games}

참고: 모든 6개 조합의 1등 확률은 {FIRST_PRIZE_ODDS}로 동일합니다.
"""

    def _parse_ai_result(
        self, data: Any, analysis: AnalysisResult
    ) -> Recommendation:
        if not isinstance(data, dict):
            raise AiRecommendationError("AI Task가 구조화된 객체를 반환하지 않았습니다")
        try:
            numbers = tuple(
                sorted(int(data[f"number_{index}"]) for index in range(1, 7))
            )
        except (KeyError, TypeError, ValueError) as err:
            raise AiRecommendationError(
                "AI Task 추천 번호를 해석할 수 없습니다"
            ) from err

        if len(numbers) != 6 or len(set(numbers)) != 6:
            raise AiRecommendationError("AI Task가 중복 없는 번호 6개를 반환하지 않았습니다")
        if any(number < 1 or number > 45 for number in numbers):
            raise AiRecommendationError("AI Task 번호 범위가 1~45를 벗어났습니다")

        past_combos = {tuple(draw.numbers) for draw in self.history}
        if numbers in past_combos:
            raise AiRecommendationError("AI Task 조합이 과거 1등 조합과 완전히 같습니다")
        if any(numbers == item.numbers for item in analysis.recommendations):
            raise AiRecommendationError("AI Task 조합이 로컬 추천과 완전히 같습니다")

        reason = str(data.get("reason", "")).strip()
        if not reason:
            raise AiRecommendationError("AI Task가 추천 근거를 반환하지 않았습니다")
        reason = reason[:300]
        values = set(numbers)
        max_overlap = max(
            (len(values & set(draw.numbers)) for draw in self.history),
            default=0,
        )
        details = {
            "target_round": analysis.target_round,
            "based_on_round": analysis.based_on_round,
            "basis": str(data.get("basis", "")).strip()[:500],
            "provider": self.configured_ai_entity_id or "HA preferred data AI Task",
            "exact_past_first_prize_match": False,
            "max_numbers_matching_any_past_first_prize": max_overlap,
            "latest_draw_overlap": len(
                values & set(self.history[-1].numbers)
            ),
            "first_prize_odds": FIRST_PRIZE_ODDS,
            "disclaimer": DISCLAIMER,
        }
        return Recommendation(
            index=len(analysis.recommendations) + 1,
            method_id=AI_METHOD_ID,
            label="Home Assistant AI 추천",
            method="HA AI Task",
            numbers=numbers,  # type: ignore[arg-type]
            reason=reason,
            score=None,
            details=details,
            source="ai_task",
        )

    async def _async_create_ai_recommendation(
        self,
        analysis: AnalysisResult,
        entity_id: str | None,
    ) -> Recommendation:
        last_error: Exception | None = None
        for attempt in range(1, AI_MAX_ATTEMPTS + 1):
            try:
                result = await async_generate_data(
                    self.hass,
                    task_name=f"로또 6/45 {analysis.target_round}회 추천",
                    entity_id=entity_id,
                    instructions=self._ai_prompt(analysis, attempt),
                    structure=self._ai_structure(),
                )
                return self._parse_ai_result(result.data, analysis)
            except (AiRecommendationError, HomeAssistantError, KeyError) as err:
                last_error = err
                _LOGGER.debug(
                    "AI 추천 검증 실패 (%s/%s): %s",
                    attempt,
                    AI_MAX_ATTEMPTS,
                    err,
                )
        raise AiRecommendationError(
            f"유효한 AI 추천을 생성하지 못했습니다: {last_error}"
        ) from last_error

    async def async_generate_ai_recommendation(
        self, entity_id: str | None = None
    ) -> Recommendation:
        """Generate, validate, cache, and publish an AI recommendation."""
        if not self.ai_enabled:
            raise AiRecommendationError(
                "통합 옵션에서 Home Assistant AI 추천을 먼저 활성화하세요"
            )
        if self.data is None:
            raise AiRecommendationError("로또 분석 데이터가 아직 준비되지 않았습니다")

        self.data = replace(self.data, ai_status="generating", ai_error=None)
        self.async_update_listeners()
        try:
            recommendation = await self._async_create_ai_recommendation(
                self.data.analysis,
                entity_id or self.configured_ai_entity_id,
            )
        except (AiRecommendationError, HomeAssistantError, KeyError) as err:
            self.data = replace(
                self.data,
                ai_status="error",
                ai_error=str(err),
            )
            self.async_update_listeners()
            raise AiRecommendationError(str(err)) from err

        generated_at = datetime.now(UTC)
        self._cached_ai_recommendation = recommendation
        self._cached_ai_generated_at = generated_at
        self.data = replace(
            self.data,
            ai_recommendation=recommendation,
            ai_status="ready",
            ai_error=None,
            ai_generated_at=generated_at,
        )
        await self._save_storage()
        self.async_update_listeners()
        return recommendation
