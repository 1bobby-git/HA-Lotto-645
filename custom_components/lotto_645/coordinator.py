"""Data coordinator for Lotto 6/45 Analysis."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import asyncio
import math
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
    CONF_ALLOW_OFFICIAL_FALLBACK,
    CONF_ENABLE_AI,
    CONF_SELECTED_METHODS,
    DEFAULT_AI_AUTO_GENERATE,
    DEFAULT_ALLOW_OFFICIAL_FALLBACK,
    DEFAULT_ENABLE_AI,
    DISCLAIMER,
    DOMAIN,
    FIRST_PRIZE_ODDS,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)
from .history import LottoHistoryError, load_bundled_history
from .methods import DEFAULT_METHOD_IDS, METHOD_MYUNGRI_HETU, normalize_method_ids
from .models import AnalysisResult, Lotto645Data, LottoDraw, Recommendation
from .myungri import extract_saju_profile, has_complete_saju_profile
from .fast_result_state import FastResultState, evaluate_saved
from .published_results import draw_cutoff
from .purchased_tickets import PurchaseBook, combined_result

_LOGGER = logging.getLogger(__name__)


class AiRecommendationError(HomeAssistantError):
    """Raised when an AI Task result cannot be accepted safely."""


class Lotto645Coordinator(FastResultState, DataUpdateCoordinator[Lotto645Data]):
    """Coordinate safe history updates, local regeneration, Saju and optional AI Tasks."""

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
        self._startup_source = "none"
        self._needs_storage_save = False
        self._cached_ai_recommendation: Recommendation | None = None
        self._cached_ai_generated_at: datetime | None = None
        self._local_generation_nonce = 0
        self._local_generated_at: datetime | None = None
        self._suppress_ai_generation_once = False
        self._saju_profile_valid = False
        self._regeneration_exclusions: tuple[tuple[int, ...], ...] = ()
        self._prediction_snapshot: dict[str, Any] | None = None
        self._draw_evaluation: dict[str, Any] | None = None
        self._manual_result_refresh_requested = False
        self._manual_lock = asyncio.Lock()
        self.purchase_book = PurchaseBook()
        self.purchase_storage_error = False
        self._purchase_lock = asyncio.Lock()
        self._purchase_store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.purchases.{entry.entry_id}"
        )

    @property
    def configured_method_ids(self) -> tuple[str, ...]:
        """Return methods selected in options, including Saju if it awaits a profile."""
        return normalize_method_ids(
            self.entry.options.get(CONF_SELECTED_METHODS, DEFAULT_METHOD_IDS)
        )

    @property
    def saju_profile(self) -> dict[str, Any]:
        """Return the local personal Saju profile extracted from config options."""
        return extract_saju_profile(dict(self.entry.options))

    @property
    def saju_profile_ready(self) -> bool:
        return self._saju_profile_valid

    @property
    def saju_profile_status(self) -> str:
        if METHOD_MYUNGRI_HETU not in self.configured_method_ids:
            return "not_selected"
        return "ready" if self.saju_profile_ready else "profile_required"

    @property
    def selected_method_ids(self) -> tuple[str, ...]:
        """Return active methods; personal Saju is blocked until its profile exists."""
        configured = self.configured_method_ids
        if self.saju_profile_ready:
            return configured
        return tuple(
            method_id for method_id in configured if method_id != METHOD_MYUNGRI_HETU
        )

    @property
    def ai_enabled(self) -> bool:
        return bool(self.entry.options.get(CONF_ENABLE_AI, DEFAULT_ENABLE_AI))

    @property
    def ai_auto_generate(self) -> bool:
        return bool(
            self.entry.options.get(CONF_AI_AUTO_GENERATE, DEFAULT_AI_AUTO_GENERATE)
        )

    @property
    def configured_ai_entity_id(self) -> str | None:
        value = self.entry.options.get(CONF_AI_TASK_ENTITY_ID)
        return str(value) if value else None

    @property
    def allow_official_fallback(self) -> bool:
        """Direct Donghaeng requests are opt-in and never used for full history."""
        return bool(
            self.entry.options.get(
                CONF_ALLOW_OFFICIAL_FALLBACK,
                DEFAULT_ALLOW_OFFICIAL_FALLBACK,
            )
        )

    @property
    def local_generation_sequence(self) -> int:
        return self._local_generation_nonce

    @property
    def local_generated_at(self) -> datetime | None:
        return self._local_generated_at

    @property
    def last_draw_evaluation(self) -> dict[str, Any] | None:
        """Return the latest persisted recommendation-vs-draw evaluation."""
        return self._draw_evaluation

    async def async_save_purchase_record(
        self, round_no: int, values: dict[str, Any], *, clear: bool = False,
        expected_revision: str | None = None
    ) -> None:
        """Save all five lines atomically without network, AI or regeneration."""
        if self.purchase_storage_error:
            raise HomeAssistantError("purchase_storage_unavailable")
        async with self._purchase_lock:
            if expected_revision is not None:
                current = self.purchase_book.records.get(str(round_no), {}).get("saved_at", "")
                if current != expected_revision:
                    raise HomeAssistantError("purchase_revision_conflict")
            updated = self.purchase_book.updated(round_no, values, clear=clear)
            await self._purchase_store.async_save(updated.to_storage())
            # Do not replace the in-memory copy before a successful durable write.
            self.purchase_book = updated
        self.async_update_listeners()

    async def _async_setup(self) -> None:
        """Load HA cache first, then the release-bundled last-known-good seed."""
        try:
            self.purchase_book = PurchaseBook.from_storage(await self._purchase_store.async_load())
        except (ValueError, TypeError, KeyError, HomeAssistantError, OSError):
            # Keep the bad file untouched and block writes; recommendations still work.
            self.purchase_storage_error = True
            _LOGGER.error("구매번호 저장소를 읽지 못했습니다. 원본 파일을 보존하며 덮어쓰지 않습니다")
        self._saju_profile_valid = await self.hass.async_add_executor_job(
            has_complete_saju_profile, self.saju_profile
        )
        payload = await self._store.async_load()
        if payload:
            try:
                self._restore_fast_state(payload)
            except (ValueError, TypeError, KeyError):
                # A damaged provisional overlay must not discard valid history.
                self._fast_result = None
                self._frozen_result_snapshot = None
            try:
                prediction_snapshot = payload.get("prediction_snapshot")
                if isinstance(prediction_snapshot, dict):
                    self._prediction_snapshot = prediction_snapshot
                draw_evaluation = payload.get("draw_evaluation")
                if isinstance(draw_evaluation, dict):
                    self._draw_evaluation = draw_evaluation
                draws = [
                    LottoDraw.from_storage(item) for item in payload.get("draws", [])
                ]
                draws.sort(key=lambda draw: draw.round)
                if draws and [draw.round for draw in draws] == list(
                    range(1, draws[-1].round + 1)
                ):
                    self.history = draws
                    self._startup_source = "storage_cache"
                self._local_generation_nonce = max(
                    0, int(payload.get("local_generation_sequence", 0))
                )
                excluded = payload.get("local_excluded_combinations", [])
                self._regeneration_exclusions = tuple(
                    tuple(sorted(item)) for item in excluded
                    if isinstance(item, list) and len(item) == 6 and len(set(item)) == 6
                    and all(type(n) is int and 1 <= n <= 45 for n in item)
                )
                local_generated = payload.get("local_generated_at")
                if local_generated:
                    self._local_generated_at = datetime.fromisoformat(str(local_generated))
                ai_payload = payload.get("ai_recommendation")
                if self.history and isinstance(ai_payload, dict):
                    recommendation = Recommendation.from_storage(ai_payload)
                    if recommendation.details.get("target_round") == self.history[-1].round + 1:
                        self._cached_ai_recommendation = recommendation
                        generated = payload.get("ai_generated_at")
                        if generated:
                            self._cached_ai_generated_at = datetime.fromisoformat(str(generated))
            except (KeyError, TypeError, ValueError) as err:
                self.history = []
                self._cached_ai_recommendation = None
                self._cached_ai_generated_at = None
                self._local_generation_nonce = 0
                self._local_generated_at = None
                self._prediction_snapshot = None
                self._draw_evaluation = None
                _LOGGER.warning("로또 로컬 캐시를 읽지 못했습니다: %s", err)

        if self.history:
            return
        try:
            draws, _metadata = await self.hass.async_add_executor_job(load_bundled_history)
        except LottoHistoryError as err:
            _LOGGER.error("번들 로또 이력을 읽지 못했습니다: %s", err)
            return
        self.history = draws
        self._startup_source = "bundled_seed"
        self._needs_storage_save = True

    async def _save_storage(self) -> None:
        await self._store.async_save(
            {
                "fast_result": getattr(self, "_fast_result", None),
                "frozen_result_snapshot": getattr(self, "_frozen_result_snapshot", None),
                "latest_round": self.history[-1].round if self.history else 0,
                "draws": [draw.to_storage() for draw in self.history],
                "local_generation_sequence": self._local_generation_nonce,
                "local_excluded_combinations": [list(item) for item in self._regeneration_exclusions],
                "local_generated_at": (
                    self._local_generated_at.isoformat()
                    if self._local_generated_at
                    else None
                ),
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
                "prediction_snapshot": self._prediction_snapshot,
                "draw_evaluation": self._draw_evaluation,
            }
        )
        self._needs_storage_save = False

    def _build_prediction_snapshot(
        self,
        analysis: AnalysisResult,
        ai_recommendation: Recommendation | None,
        ai_generated_at: datetime | None,
    ) -> dict[str, Any]:
        def minimal_item(item: Recommendation) -> dict[str, Any]:
            # The result checker only needs identity + six numbers.  Do not copy
            # large analysis details or derived Saju context into the persistent
            # prediction snapshot.
            return {
                "index": item.index,
                "method_id": item.method_id,
                "label": item.label,
                "method": item.method,
                "numbers": list(item.numbers),
                "reason": "",
                "score": None,
                "details": {},
                "source": item.source,
            }

        recommendations = [minimal_item(item) for item in analysis.recommendations]
        if ai_recommendation is not None:
            recommendations.append(minimal_item(ai_recommendation))
        return {
            "target_round": analysis.target_round,
            "based_on_round": analysis.based_on_round,
            "local_generation_sequence": self._local_generation_nonce,
            "local_generated_at": (
                self._local_generated_at.isoformat() if self._local_generated_at else None
            ),
            "ai_generated_at": ai_generated_at.isoformat() if ai_generated_at else None,
            "recommendations": recommendations,
        }

    def _set_prediction_snapshot(
        self,
        analysis: AnalysisResult,
        ai_recommendation: Recommendation | None,
        ai_generated_at: datetime | None,
    ) -> None:
        # Do not replace the result's pre-publication snapshot with numbers
        # generated after that draw was reported while official history lags.
        state = getattr(self, "_fast_result", None) or {}
        if analysis.target_round <= state.get("round", 0):
            return
        snapshot = self._build_prediction_snapshot(
            analysis, ai_recommendation, ai_generated_at
        )
        if (self._prediction_snapshot
                and self._prediction_snapshot.get("target_round") == analysis.target_round
                and datetime.now(UTC) >= draw_cutoff(analysis.target_round)):
            return
        if snapshot != self._prediction_snapshot:
            self._prediction_snapshot = snapshot
            self._needs_storage_save = True

    def _evaluate_prediction_snapshot(self) -> None:
        snapshot = self._prediction_snapshot
        if not isinstance(snapshot, dict):
            return
        try:
            target_round = int(snapshot.get("target_round", 0))
        except (TypeError, ValueError):
            return
        if target_round <= 0:
            return
        draw = next((item for item in self.history if item.round == target_round), None)
        if draw is None:
            return
        if (self._draw_evaluation and self._draw_evaluation.get("round") == target_round
                and self._draw_evaluation.get("winning_numbers") == list(draw.numbers)
                and self._draw_evaluation.get("bonus_number") == draw.bonus
                and self._draw_evaluation.get("snapshot_policy") == "pre_draw_v1"):
            return
        # Apply the same timestamp policy to official-first and fast-overlay
        # results. Older cached evaluations are recomputed once with this policy.
        self._draw_evaluation = evaluate_saved(snapshot, draw)
        self._needs_storage_save = True
        _LOGGER.info(
            "%s회 추천 결과 판정 완료: %s게임 중 %s게임 당첨, 최고 %s",
            target_round,
            self._draw_evaluation.get("checked_game_count", 0),
            self._draw_evaluation.get("winning_game_count", 0),
            self._draw_evaluation.get("highest_prize", "미당첨"),
        )

    @staticmethod
    def _history_changed(left: list[LottoDraw], right: list[LottoDraw]) -> bool:
        if len(left) != len(right):
            return True
        return any(
            a.to_storage() != b.to_storage()
            for a, b in zip(left, right, strict=True)
        )

    async def _async_update_data(self) -> Lotto645Data:
        """Refresh data and atomically evaluate a newly completed draw."""
        manual_result_refresh = self._manual_result_refresh_requested
        self._manual_result_refresh_requested = False
        # async_refresh_and_regenerate() captures the exact pre-refresh ticket
        # snapshot before advancing the generation nonce.  Do not overwrite that
        # snapshot at the start of the user-triggered result check.
        if self.data is not None and not manual_result_refresh:
            self._set_prediction_snapshot(
                self.data.analysis,
                self.data.ai_recommendation,
                self.data.ai_generated_at,
            )
        elif self._prediction_snapshot is None and self.history:
            # Upgrade compatibility: v1.7 and older did not persist recommendation
            # snapshots.  Reconstruct the currently displayed target round from
            # the cached pre-draw history before accepting a newer mirror round.
            try:
                profile = self.saju_profile if self.saju_profile_ready else None
                cached_analysis = await self.hass.async_add_executor_job(
                    build_analysis,
                    self.history,
                    self.selected_method_ids,
                    self._local_generation_nonce,
                    profile,
                    self._regeneration_exclusions,
                )
            except ValueError as err:
                _LOGGER.debug("기존 추천 스냅샷 재구성 생략: %s", err)
            else:
                self._set_prediction_snapshot(
                    cached_analysis,
                    self._cached_ai_recommendation,
                    self._cached_ai_generated_at,
                )
        changed = False
        source_status = self._startup_source or "cache"
        old_latest_round = self.history[-1].round if self.history else 0
        mirror_ok = False
        mirror_error: LottoApiError | None = None
        suppress_ai_generation = self._suppress_ai_generation_once
        self._suppress_ai_generation_once = False

        try:
            mirror_history, mirror_meta = await self.client.async_fetch_shared_mirror(
                force=manual_result_refresh
            )
            mirror_ok = True
            if mirror_history is None:
                source_status = "shared_mirror_not_modified"
            else:
                mirror_latest = mirror_history[-1].round
                cached_latest = self.history[-1].round if self.history else 0
                if not self.history or mirror_latest >= cached_latest:
                    changed = self._history_changed(self.history, mirror_history)
                    self.history = mirror_history
                    source_status = "shared_mirror"
                    _LOGGER.debug(
                        "공유 로또 미러 동기화: %s회, updated_at=%s",
                        mirror_latest,
                        mirror_meta.get("updated_at"),
                    )
                else:
                    source_status = "cache_ahead_of_mirror"
        except LottoApiError as err:
            mirror_error = err
            source_status = (
                "bundled_seed_fallback"
                if self._startup_source == "bundled_seed"
                else "cached_fallback"
            )
            _LOGGER.debug("공유 로또 미러 사용 불가, 로컬 이력 유지: %s", err)

        if (
            manual_result_refresh
            and not mirror_ok
            and self.allow_official_fallback
            and self.history
        ):
            self.client.begin_update_cycle()
            try:
                official_latest = await self.client.async_latest_round_official()
                cached_latest = self.history[-1].round
                if official_latest > cached_latest:
                    new_draws = await self.client.async_fetch_recent_range_official(
                        cached_latest + 1, official_latest
                    )
                    self.history.extend(new_draws)
                    changed = True
                    source_status = "official_incremental_fallback"
                elif official_latest == cached_latest:
                    source_status = "official_verified_cache"
                else:
                    source_status = "cache_ahead_of_official"
            except LottoApiError as err:
                _LOGGER.warning(
                    "선택적 동행복권 직접 증분 확인을 중단했습니다: %s", err
                )
                source_status = "cached_fallback_official_unavailable"

        if not self.history:
            kwargs: dict[str, Any] = {}
            if mirror_error and mirror_error.retry_after is not None:
                kwargs["retry_after"] = mirror_error.retry_after
            raise UpdateFailed(
                "로또 이력 미러와 번들 캐시를 모두 사용할 수 없습니다",
                **kwargs,
            )

        if self.history[-1].round != old_latest_round:
            # Evaluate the pre-draw snapshot before next-round recommendations replace it.
            # Applies to scheduled, normal coordinator and manual refresh paths.
            self._evaluate_prediction_snapshot()
            self._cached_ai_recommendation = None
            self._cached_ai_generated_at = None
            self._local_generation_nonce = 0
            self._regeneration_exclusions = ()
            self._local_generated_at = datetime.now(UTC)
            self._needs_storage_save = True

        if changed or self._needs_storage_save:
            await self._save_storage()

        if self.data is not None and not changed:
            configured = tuple(
                self.data.analysis.summary.get("selected_method_ids", [])
            )
            generated_sequence = int(
                self.data.analysis.summary.get("generation_sequence", 0)
            )
            if (
                configured == self.selected_method_ids
                and generated_sequence == self._local_generation_nonce
            ):
                if self.data.source_status == source_status:
                    return self.data
                return replace(self.data, source_status=source_status)

        try:
            profile = self.saju_profile if self.saju_profile_ready else None
            analysis = await self.hass.async_add_executor_job(
                build_analysis,
                self.history,
                self.selected_method_ids,
                self._local_generation_nonce,
                profile,
                self._regeneration_exclusions,
            )
        except ValueError as err:
            raise UpdateFailed(f"로또 분석 실패: {err}") from err

        if self._local_generated_at is None:
            self._local_generated_at = datetime.now(UTC)
            self._needs_storage_save = True

        ai_recommendation = self._cached_ai_recommendation if self.ai_enabled else None
        ai_generated_at = self._cached_ai_generated_at if self.ai_enabled else None
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
            and not suppress_ai_generation
        ):
            try:
                ai_recommendation = await self._async_create_ai_recommendation(
                    analysis, self.configured_ai_entity_id
                )
                ai_generated_at = datetime.now(UTC)
                self._cached_ai_recommendation = ai_recommendation
                self._cached_ai_generated_at = ai_generated_at
                ai_status = "ready"
                self._needs_storage_save = True
            except (AiRecommendationError, HomeAssistantError, KeyError) as err:
                ai_status = "error"
                ai_error = str(err)
                _LOGGER.warning("AI 로또 추천 자동 생성 실패: %s", err)

        self._set_prediction_snapshot(analysis, ai_recommendation, ai_generated_at)
        if self._needs_storage_save:
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

    async def async_refresh_and_regenerate(self) -> None:
        """User-triggered refresh, optional new-draw evaluation, and local regeneration."""
        async with self._manual_lock:
            if self.data is not None:
                # Freeze exactly what the user saw before this refresh.  If a new
                # draw is obtained by this request, this snapshot is what gets
                # evaluated before next-round recommendations replace it.
                self._set_prediction_snapshot(
                    self.data.analysis,
                    self.data.ai_recommendation,
                    self.data.ai_generated_at,
                )
            self._manual_result_refresh_requested = True
            previous = tuple(item.numbers for item in self.data.analysis.recommendations) if self.data else ()
            if self.data and self.data.ai_recommendation:
                previous += (self.data.ai_recommendation.numbers,)
            self._regeneration_exclusions = previous
            self._local_generation_nonce += 1
            self._local_generated_at = datetime.now(UTC)
            self._needs_storage_save = True
            self._suppress_ai_generation_once = True
            await self.async_request_refresh()

    async def async_check_draw_result(self) -> None:
        """Force a mirror recheck without regenerating current recommendation numbers."""
        async with self._manual_lock:
            if self.data is not None:
                self._set_prediction_snapshot(
                    self.data.analysis,
                    self.data.ai_recommendation,
                    self.data.ai_generated_at,
                )
            self._manual_result_refresh_requested = True
            self._suppress_ai_generation_once = True
            await self.async_request_refresh()

    def _ai_structure(self) -> vol.Schema:
        number_selector = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=45, step=1, mode=selector.NumberSelectorMode.BOX
            )
        )
        return vol.Schema(
            {vol.Required(f"number_{index}"): number_selector for index in range(1, 7)}
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
        # Only derived local recommendation text is shared with the configured AI
        # Task. Raw birth date/time/place/timezone values never enter this prompt.
        local_games = "\n".join(
            f"- {item.label}: {', '.join(map(str, item.numbers))} / {item.reason}"
            for item in analysis.recommendations
            if item.method_id != METHOD_MYUNGRI_HETU
        )
        summary = analysis.summary
        retry_text = (
            "이전 결과가 중복 번호, 범위 오류 또는 과거 1등 완전일치로 거절되었습니다. 반드시 다른 유효 조합을 만드세요."
            if attempt > 1
            else ""
        )
        return f"""당신은 로또 6/45 통계 해석 보조 엔진입니다.
아래 데이터만 참고해 {analysis.target_round}회용 번호 6개와 핵심 근거를 생성하세요.
추첨은 독립 무작위이며 당첨을 보장하거나 확률을 높인다고 표현하면 안 됩니다.
개인 사주 원본 생년월일·출생시간·출생지는 제공되지 않으며 추정해서도 안 됩니다.

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
삼중 동반출현 상위: {summary.get('top_triplet_strength')}
로컬 추천:
{local_games}

참고: 모든 6개 조합의 1등 확률은 {FIRST_PRIZE_ODDS}로 동일합니다.
"""

    def _parse_ai_result(self, data: Any, analysis: AnalysisResult) -> Recommendation:
        if not isinstance(data, dict):
            raise AiRecommendationError("AI Task가 구조화된 객체를 반환하지 않았습니다")
        try:
            raw = [data[f"number_{index}"] for index in range(1, 7)]
            if any(isinstance(n, bool) or not isinstance(n, (int, float))
                   or not math.isfinite(n) or int(n) != n for n in raw):
                raise ValueError("non-integral AI number")
            numbers = tuple(sorted(int(n) for n in raw))
        except (KeyError, TypeError, ValueError, OverflowError) as err:
            raise AiRecommendationError("AI Task는 1~45 정수 6개를 반환해야 합니다") from err
        if len(numbers) != 6 or len(set(numbers)) != 6:
            raise AiRecommendationError("AI Task가 중복 없는 번호 6개를 반환하지 않았습니다")
        if any(number < 1 or number > 45 for number in numbers):
            raise AiRecommendationError("AI Task 번호 범위가 1~45를 벗어났습니다")
        past_combos = {tuple(draw.numbers) for draw in self.history}
        if numbers in past_combos:
            raise AiRecommendationError("AI Task 조합이 과거 1등 조합과 완전히 같습니다")
        if any(numbers == item.numbers for item in analysis.recommendations):
            raise AiRecommendationError("AI Task 조합이 로컬 추천과 완전히 같습니다")
        reason = data.get("reason", "")
        reason = reason.strip() if isinstance(reason, str) else ""
        if not reason:
            raise AiRecommendationError("AI Task가 추천 근거를 반환하지 않았습니다")
        values = set(numbers)
        max_overlap = max(
            (len(values & set(draw.numbers)) for draw in self.history), default=0
        )
        details = {
            "target_round": analysis.target_round,
            "based_on_round": analysis.based_on_round,
            "basis": str(data.get("basis", "")).strip()[:500],
            "provider": self.configured_ai_entity_id or "HA preferred data AI Task",
            "exact_past_first_prize_match": False,
            "max_numbers_matching_any_past_first_prize": max_overlap,
            "latest_draw_overlap": len(values & set(self.history[-1].numbers)),
            "first_prize_odds": FIRST_PRIZE_ODDS,
            "disclaimer": DISCLAIMER,
        }
        return Recommendation(
            index=len(analysis.recommendations) + 1,
            method_id=AI_METHOD_ID,
            label="Home Assistant AI 추천",
            method="HA AI Task",
            numbers=numbers,  # type: ignore[arg-type]
            reason=reason[:300],
            score=None,
            details=details,
            source="ai_task",
        )

    async def _async_create_ai_recommendation(
        self, analysis: AnalysisResult, entity_id: str | None
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
            self.data = replace(self.data, ai_status="error", ai_error=str(err))
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
        self._set_prediction_snapshot(self.data.analysis, recommendation, generated_at)
        await self._save_storage()
        self.async_update_listeners()
        return recommendation
