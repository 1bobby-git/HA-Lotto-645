"""Data coordinator for Lotto 6/45 Analysis."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .analysis import build_analysis
from .api import LottoApiClient, LottoApiError
from .const import DOMAIN, STORAGE_KEY_PREFIX, STORAGE_VERSION, UPDATE_INTERVAL
from .models import Lotto645Data, LottoDraw

_LOGGER = logging.getLogger(__name__)


class Lotto645Coordinator(DataUpdateCoordinator[Lotto645Data]):
    """Coordinate remote draw updates and local deterministic analysis."""

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

    async def _async_setup(self) -> None:
        """Load cached history once."""
        payload = await self._store.async_load()
        if not payload:
            return
        try:
            draws = [LottoDraw.from_storage(item) for item in payload.get("draws", [])]
            draws.sort(key=lambda draw: draw.round)
            if draws and draws[0].round == 1:
                contiguous = [draw.round for draw in draws] == list(
                    range(1, draws[-1].round + 1)
                )
                if contiguous:
                    self.history = draws
                    return
            _LOGGER.warning("로또 캐시가 연속된 전체 회차가 아니어서 다시 동기화합니다")
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.warning("로또 캐시를 읽지 못해 다시 동기화합니다: %s", err)

    async def _save_history(self) -> None:
        await self._store.async_save(
            {
                "latest_round": self.history[-1].round if self.history else 0,
                "draws": [draw.to_storage() for draw in self.history],
            }
        )

    async def _async_update_data(self) -> Lotto645Data:
        """Fetch new draws and rebuild recommendations only when needed."""
        source_status = "live"
        changed = False
        try:
            latest_round = await self.client.async_latest_round()
            if not self.history:
                self.history = await self.client.async_fetch_full_history(latest_round)
                changed = True
            else:
                cached_latest = self.history[-1].round
                if latest_round > cached_latest:
                    new_draws = await self.client.async_fetch_range(
                        cached_latest + 1, latest_round
                    )
                    by_round = {draw.round: draw for draw in self.history}
                    by_round.update({draw.round: draw for draw in new_draws})
                    self.history = [by_round[index] for index in range(1, latest_round + 1)]
                    changed = True
                elif latest_round < cached_latest:
                    source_status = "cache_ahead_of_source"
        except LottoApiError as err:
            if not self.history:
                kwargs: dict[str, Any] = {}
                if err.retry_after is not None:
                    kwargs["retry_after"] = err.retry_after
                raise UpdateFailed(str(err), **kwargs) from err
            source_status = "cached_fallback"
            _LOGGER.debug("동행복권 통신 실패, 마지막 정상 캐시를 유지합니다: %s", err)

        if changed:
            await self._save_history()

        if not self.history:
            raise UpdateFailed("분석할 로또 회차 데이터가 없습니다")

        if self.data is not None and not changed:
            if self.data.source_status == source_status:
                return self.data
            return Lotto645Data(
                latest_draw=self.data.latest_draw,
                analysis=self.data.analysis,
                history_count=self.data.history_count,
                generated_at=self.data.generated_at,
                source_status=source_status,
            )

        try:
            analysis = await self.hass.async_add_executor_job(build_analysis, self.history)
        except ValueError as err:
            raise UpdateFailed(f"로또 분석 실패: {err}") from err

        return Lotto645Data(
            latest_draw=self.history[-1],
            analysis=analysis,
            history_count=len(self.history),
            generated_at=datetime.now(UTC),
            source_status=source_status,
        )
