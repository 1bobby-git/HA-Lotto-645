"""Data coordinator for Lotto 6/45 Analysis."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.ai_task import async_generate_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .methods import METHODS_BY_ID
from .ai_formula import (AI_BASE_FORMULA, explanation_prompt,
                         validate_explanation, validate_backend_ticket)
from .service_runtime import ServiceRuntime
from .lab_client import LabServiceError
from .const import CONF_PERSONAL_CONSENT
FORMULA_VERSION = "server"
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
from .methods import DEFAULT_METHOD_IDS, METHOD_MYUNGRI_HETU, METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE, normalize_method_ids
from .models import AnalysisResult, Lotto645Data, LottoDraw, Recommendation
from .myungri import extract_saju_profile, has_complete_saju_profile
from .fast_result_state import FastResultState, evaluate_saved
from .review import ReviewBook
from .review_state import ReviewState
from .published_results import draw_cutoff
from .purchased_tickets import PurchaseBook, combined_result, parse_games

_LOGGER = logging.getLogger(__name__)


class AiRecommendationError(HomeAssistantError):
    """Raised when an AI Task result cannot be accepted safely."""


class Lotto645Coordinator(ReviewState, FastResultState, DataUpdateCoordinator[Lotto645Data]):
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
        self.service = ServiceRuntime(self)
        self._history_storage_error = False
        self._consensus_save_task: asyncio.Task | None = None
        self._consensus_dirty = False
        self._local_generation_nonce = 0
        self._local_generated_at: datetime | None = None
        self._suppress_ai_generation_once = False
        self._saju_profile_valid = False
        self._regeneration_exclusions: tuple[tuple[int, ...], ...] = ()
        self._prediction_snapshot: dict[str, Any] | None = None
        self._draw_evaluation: dict[str, Any] | None = None
        self._manual_result_refresh_requested = False
        self._manual_lock = asyncio.Lock()
        self.review_book = ReviewBook()
        self.review_storage_error = False
        self._review_dirty = False
        self._review_save_error = False
        self._review_save_lock = asyncio.Lock()
        self._review_store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.reviews.{entry.entry_id}")
        self.purchase_book = PurchaseBook()
        self.purchase_storage_error = False
        self._purchase_lock = asyncio.Lock()
        self._purchase_store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.purchases.{entry.entry_id}"
        )

    @callback
    def async_update_listeners(self) -> None:
        """Publish persisted server results; never calculate aggregates in HA."""
        super().async_update_listeners()
        self.hass.bus.async_fire(DOMAIN + '_updated', {'entry_id': self.entry.entry_id})

    async def _async_save_consensus(self) -> None:
        """Coalesce source publications, including updates during a disk write."""
        while self._consensus_dirty:
            self._consensus_dirty = False
            try:
                await self._save_storage()
            except (OSError, HomeAssistantError):
                self._needs_storage_save = True
                _LOGGER.warning("합의 추천 저장 실패: 다음 데이터 갱신에서 재시도합니다")
                break

    async def async_flush_consensus(self) -> None:
        """Finish the pending snapshot write before options reload/unload."""
        task = getattr(self, "_consensus_save_task", None)
        if task is not None:
            await asyncio.shield(task)

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
        return "ready" if self.saju_profile_ready else ("remote_consent_required" if not self.entry.options.get(CONF_PERSONAL_CONSENT) else "profile_required")

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

    def _purchase_formula_links(
        self, round_no: int, values: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        """Capture exact current-generation provenance when a ticket is saved."""
        if self.data is None or self.data.analysis.target_round != round_no:
            return {}
        games = parse_games(values)
        recommendations = list(self.data.analysis.recommendations)
        if self.data.ai_recommendation is not None:
            recommendations.append(self.data.ai_recommendation)
        result: dict[str, list[dict[str, Any]]] = {}
        for game in games:
            numbers = tuple(game["numbers"])
            links = []
            for recommendation in recommendations:
                if recommendation.numbers != numbers:
                    continue
                generated = recommendation.details.get("generated_at")
                if not generated:
                    when = (
                        self.data.ai_generated_at
                        if recommendation.source in ("ai", "ai_task")
                        else self._local_generated_at
                    )
                    generated = when.isoformat() if when else None
                if not generated:
                    # Without a real generation timestamp we can show a current
                    # coincidence but must not claim durable formula provenance.
                    continue
                link = {
                    "formula_id": recommendation.method_id,
                    "formula_label": recommendation.label,
                    "source": recommendation.source,
                    "generated_at": str(generated),
                    "based_on_round": self.data.analysis.based_on_round,
                    "target_round": round_no,
                    "generation_sequence": self._local_generation_nonce,
                }
                for key in ("formula_version", "core_version", "generation_id"):
                    value = recommendation.details.get(key)
                    if value is not None:
                        link[key] = value
                links.append(link)
            if links:
                result[game["slot"]] = links
        return result

    async def async_save_purchase_record(
        self, round_no: int, values: dict[str, Any], *, clear: bool = False,
        expected_revision: str | None = None, ticket_id: str | None = None, new_ticket: bool = False
    ) -> None:
        """Save all five lines atomically without network, AI or regeneration."""
        if self.purchase_storage_error:
            raise HomeAssistantError("purchase_storage_unavailable")
        async with self._purchase_lock:
            if expected_revision is not None:
                current = "" if new_ticket else self.purchase_book.ticket_record(round_no,ticket_id).get("saved_at", "")
                if current != expected_revision:
                    raise HomeAssistantError("purchase_revision_conflict")
            formula_links = {} if clear else self._purchase_formula_links(round_no, values)
            updated = self.purchase_book.updated(
                round_no, values, clear=clear, ticket_id=ticket_id, new_ticket=new_ticket,
                formula_links_by_slot=formula_links,
            )
            await self._purchase_store.async_save(updated.to_storage())
            # Do not replace the in-memory copy before a successful durable write.
            self.purchase_book = updated
        self.async_update_listeners()

    async def _async_setup(self) -> None:
        """Load HA cache first, then the release-bundled last-known-good seed."""
        try:
            self.review_book = ReviewBook.from_storage(await self._review_store.async_load())
        except (ValueError, TypeError, KeyError, HomeAssistantError, OSError):
            self.review_storage_error = True
            _LOGGER.error("리뷰 저장소 오류: 원본을 보존하고 덮어쓰지 않습니다")
        try:
            self.purchase_book = PurchaseBook.from_storage(await self._purchase_store.async_load())
        except (ValueError, TypeError, KeyError, HomeAssistantError, OSError):
            # Keep the bad file untouched and block writes; recommendations still work.
            self.purchase_storage_error = True
            _LOGGER.error("구매번호 저장소를 읽지 못했습니다. 원본 파일을 보존하며 덮어쓰지 않습니다")
        if not self.purchase_storage_error and not self.review_storage_error:
            migrated = self.purchase_book.with_review_formula_links(self.review_book.rounds)
            if migrated.to_storage() != self.purchase_book.to_storage():
                try:
                    await self._purchase_store.async_save(migrated.to_storage())
                except (OSError, HomeAssistantError):
                    _LOGGER.warning(
                        "기존 구매번호의 공식 연결 이관을 저장하지 못해 원본 구매기록을 유지합니다"
                    )
                else:
                    self.purchase_book = migrated
        self._saju_profile_valid = bool(self.entry.options.get(CONF_PERSONAL_CONSENT)) and await self.hass.async_add_executor_job(
            has_complete_saju_profile, self.saju_profile
        )
        await self.service.prepare()
        try:
            payload = await self._store.async_load()
        except (ValueError, OSError, HomeAssistantError):
            payload = None
            self._history_storage_error = True
            _LOGGER.error("기존 저장소 오류: 원본을 덮어쓰지 않습니다")
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
        self._sync_reviews()
        if not self.review_storage_error:
            async with self._review_save_lock:
                while self._review_dirty:
                    payload = self.review_book.to_storage()
                    try:
                        await self._review_store.async_save(payload)
                    except (OSError, HomeAssistantError):
                        self._review_save_error = True
                        _LOGGER.warning("리뷰 저장 실패: 기존 저장본을 유지하고 다음 갱신에 재시도합니다")
                        break
                    self._review_save_error = False
                    # A snapshot may have changed while the write yielded.
                    self._review_dirty = payload != self.review_book.to_storage()
        if self._history_storage_error:
            return
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
            result = {
                "index": item.index,
                "method_id": item.method_id,
                "label": item.label,
                "method": item.method,
                "numbers": list(item.numbers),
                "reason": "",
                "score": None,
                "details": {k:v for k,v in item.details.items() if k in ("formula_version","core_version","generation_id","generated_at")},
                "source": item.source,
            }
            if item.method_id in (METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE):
                # A reactive aggregate can be newer than the source batch. Never
                # attribute it to an earlier, potentially pre-draw timestamp.
                result["generated_at"] = item.details.get("consensus_updated_at")
            return result

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
        if hasattr(self, "review_book") and not self.review_storage_error:
            if self.review_book.record_snapshot(snapshot):
                self._review_dirty = True
                # New snapshots may not have a result yet, but must be durable.
                self._needs_storage_save = True
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
        self._sync_reviews()
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
            self._local_generated_at = None
            self._needs_storage_save = True

        if changed or self._needs_storage_save or self._review_dirty:
            await self._save_storage()

        try:
            analysis = await self.service.analysis()
        except (LabServiceError, ValueError, OSError) as exc:
            self.service.status = exc.code if isinstance(exc,LabServiceError) else "storage_error"
            analysis = self.service.legacy_analysis()

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
                ai_generated_at = datetime.fromisoformat(ai_recommendation.details["generated_at"])
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
        return vol.Schema({
            vol.Required("formula_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[AI_BASE_FORMULA])),
            vol.Required("reason"): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)),
            vol.Optional("basis"): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)),
        })

    def _ai_prompt(self, analysis: AnalysisResult, attempt: int, numbers=()) -> str:
        return explanation_prompt(numbers, analysis.target_round, analysis.based_on_round, attempt)

    def _parse_ai_result(self, data: Any, analysis: AnalysisResult,
                         numbers=(), entity_id: str | None = None) -> Recommendation:
        try:
            reason, basis = validate_explanation(data)
            numbers = validate_backend_ticket(numbers, analysis, self.history)
        except (ValueError, TypeError) as err:
            raise AiRecommendationError(str(err)) from err
        values = set(numbers)
        details = {
            "target_round": analysis.target_round, "based_on_round": analysis.based_on_round,
            "base_formula_id": AI_BASE_FORMULA, "formula_version": FORMULA_VERSION,
            "rng": "system_csprng", "number_source": "backend_formula_engine",
            "ai_role": "explanation_only", "history_used_for_weighting": False,
            "history_cutoff_round": analysis.based_on_round,
            "uniformity": "uniform_over_allowed_combinations",
            "exclusions": "past_winning_combinations_and_duplicate_tickets",
            "basis": basis, "provider": entity_id or self.configured_ai_entity_id or "HA preferred data AI Task",
            "exact_past_first_prize_match": False,
            "max_numbers_matching_any_past_first_prize": max(
                (len(values & set(draw.numbers)) for draw in self.history), default=0),
            "latest_draw_overlap": len(values & set(self.history[-1].numbers)),
            "first_prize_odds": FIRST_PRIZE_ODDS, "disclaimer": DISCLAIMER,
        }
        return Recommendation(
            index=len(analysis.recommendations) + 1, method_id=AI_METHOD_ID,
            label="Home Assistant AI 추천", method="HA AI 설명 · CCSS 추첨 공식",
            numbers=numbers, reason=reason, score=None, details=details, source="ai_task",
        )

    async def _async_create_ai_recommendation(
        self, analysis: AnalysisResult, entity_id: str | None
    ) -> Recommendation:
        # Freeze a CSPRNG ticket before invoking the language model. Retries can
        # only change explanation, never use the LLM as a random-number source.
        try:
            base_result = await self.service.ai_ticket(analysis.target_round)
            numbers = base_result.games[0].numbers
        except LabServiceError as exc:
            raise AiRecommendationError(exc.code) from exc
        # Preserve a valid backend ticket even if the optional language model fails.
        backend = self._parse_ai_result({"formula_id":AI_BASE_FORMULA,
            "reason":"비공개 Core에서 생성했습니다. AI 설명은 아직 없습니다.","basis":"서버 CCSS"},
            analysis,numbers,entity_id)
        backend.details.update(core_version=base_result.core_version,
            formula_version=base_result.games[0].formula_version,
            generation_id=base_result.generation_id,generated_at=base_result.generated_at)
        self._cached_ai_recommendation = backend
        self._cached_ai_generated_at = datetime.fromisoformat(base_result.generated_at)
        self._needs_storage_save = True
        await self._save_storage()
        last_error: Exception | None = None
        for attempt in range(1, AI_MAX_ATTEMPTS + 1):
            try:
                result = await async_generate_data(
                    self.hass,
                    task_name=f"로또 6/45 {analysis.target_round}회 추천",
                    entity_id=entity_id,
                    instructions=self._ai_prompt(analysis, attempt, numbers),
                    structure=self._ai_structure(),
                )
                parsed = self._parse_ai_result(result.data, analysis, numbers, entity_id)
                parsed.details.update(backend.details)
                return parsed
            except (AiRecommendationError, HomeAssistantError, KeyError) as err:
                last_error = err
                _LOGGER.debug(
                    "AI 추천 검증 실패 (%s/%s): %s",
                    attempt,
                    AI_MAX_ATTEMPTS,
                    err,
                )
        return replace(backend,reason="번호 생성 완료. AI 설명을 가져오지 못했습니다.")

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
            # The AI awaited external I/O; local regeneration/round advancement
            # may have happened meanwhile. Never publish against stale state.
            if self.data is None or recommendation.details["target_round"] != self.data.analysis.target_round:
                raise AiRecommendationError("AI 설명 중 기준 회차가 바뀌었습니다")
            try:
                validate_backend_ticket(recommendation.numbers, self.data.analysis, self.history)
            except ValueError as err:
                raise AiRecommendationError(str(err)) from err
        except (AiRecommendationError, HomeAssistantError, KeyError) as err:
            self.data = replace(self.data, ai_status="error", ai_error=str(err))
            self.async_update_listeners()
            raise AiRecommendationError(str(err)) from err
        generated_at = datetime.fromisoformat(recommendation.details["generated_at"])
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
