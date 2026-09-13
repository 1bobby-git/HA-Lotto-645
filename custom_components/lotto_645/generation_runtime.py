"""HA-side progress, single-flight user requests and thread-safe UI updates."""
from __future__ import annotations

import asyncio
from functools import partial
import logging
import threading
from time import monotonic

from homeassistant.components import persistent_notification
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import HomeAssistantError

from .analysis import build_analysis
from .const import DOMAIN, VERSION
from .generation import GenerationCancelled, GenerationProgress, progress_message
from .methods import METHODS_BY_ID

_LOGGER = logging.getLogger(__name__)


class GenerationController:
    """UI updates cannot mutate recommendations or become new review votes."""

    def __init__(self, coordinator) -> None:
        self.owner = coordinator
        self.hass = coordinator.hass
        self.progress = GenerationProgress()
        self.signal = f"{DOMAIN}_generation_{coordinator.entry.entry_id}"
        self.notification_id = self.signal
        self.store = Store(self.hass, 1, f"{DOMAIN}.timings.{VERSION}.{coordinator.entry.entry_id}")
        self.task: asyncio.Task | None = None
        self.worker: asyncio.Future | None = None
        self.save_task: asyncio.Task | None = None
        self.done = asyncio.Event()
        self.cancel = threading.Event()
        self.closed = False
        self.notify = False
        self.ticker: asyncio.Task | None = None
        self.last_notice = -100.0
        self.last_signal = -100.0

    async def load(self) -> None:
        try:
            self.progress.load(await self.store.async_load())
        except (OSError, ValueError, TypeError, HomeAssistantError):
            _LOGGER.warning("재생성 시간 기록을 읽지 못했습니다. 예상시간을 다시 측정합니다")

    @property
    def view(self) -> dict:
        result = self.progress.view()
        result["message"] = progress_message(result)
        return result

    def begin(self, *, manual: bool = False) -> None:
        if self.closed:
            raise GenerationCancelled()
        self.notify = self.notify or manual
        if self.progress.active:
            self.publish(force=True)
            return
        self.done.clear()
        self.cancel.clear()
        self.progress.begin({key: METHODS_BY_ID[key].label for key in self.owner.selected_method_ids})
        self.publish(force=True)
        self.ticker = self.hass.async_create_task(self._tick())

    async def _tick(self) -> None:
        while self.progress.active and not self.closed:
            await asyncio.sleep(1)
            self.publish()

    def publish(self, *, force: bool = False) -> None:
        if self.closed:
            return
        now = monotonic()
        if force or now - self.last_signal >= 1:
            async_dispatcher_send(self.hass, self.signal)
            self.last_signal = now
        if self.notify and (now - self.last_notice >= 5 or force and self.progress.phase in ("queued", "completed", "error", "cancelled")):
            v = self.view
            remaining = v["estimated_remaining_seconds"]
            estimate = (f"남은 시간 약 {remaining:.0f}초 (추정)" if remaining is not None else
                        "예상시간보다 지연됨 · 계속 처리 중" if v["estimate_exceeded"] else
                        "첫 실행 기록 측정 중" if v["state"] == "running" else "")
            persistent_notification.async_create(
                self.hass,
                f"{v['message']}\n\n경과 {v['elapsed_seconds']:.0f}초 · {estimate}\n\n"
                "중복 클릭해도 작업은 하나만 실행합니다. AI 추천은 유지합니다. "
                "[진행상황 열기](/lotto-645)",
                title="로또 번호 재생성", notification_id=self.notification_id,
            )
            self.last_notice = now

    def step(self, phase: str) -> None:
        self.progress.update({"phase": phase})
        self.publish(force=True)

    def _accept(self, token: str, event: dict) -> None:
        if self.closed or token != self.progress.run_id or not self.progress.active:
            return
        self.progress.update(event)
        self.publish(force=event["phase"] != "method_progress")

    async def build(self, *args):
        token = self.progress.run_id
        def report(event: dict) -> None:
            if self.cancel.is_set():
                raise GenerationCancelled()
            # This callback runs in the executor, never calls HA async APIs.
            self.hass.loop.call_soon_threadsafe(self._accept, token, event)
        self.worker = self.hass.async_add_executor_job(
            partial(build_analysis, *args, progress_callback=report)
        )
        try:
            return await asyncio.shield(self.worker)
        finally:
            if self.worker.done():
                self.worker = None

    def finish(self, state: str, error: str | None = None) -> None:
        if not self.progress.active:
            return
        self.progress.finish(state, error)
        if self.ticker:
            self.ticker.cancel()
            self.ticker = None
        self.publish(force=True)
        self.done.set()
        self.notify = False
        if state == "completed" and self.progress.worked and not self.closed:
            self.save_task = self.hass.async_create_task(self._save_timings())

    async def _save_timings(self) -> None:
        try:
            await self.store.async_save(self.progress.to_storage())
        except (OSError, HomeAssistantError):
            _LOGGER.warning("재생성 시간 기록 저장 실패: 추천·구매·리뷰 데이터는 영향 없음")

    def start(self) -> dict:
        """Accept quickly from HA buttons/WS; do not queue repeated user jobs."""
        if self.closed:
            raise GenerationCancelled()
        if self.progress.active or self.task and not self.task.done():
            self.notify = True
            self.publish(force=True)
            return self.view
        self.begin(manual=True)
        self.task = self.hass.async_create_task(self._drive())
        return self.view

    async def wait(self) -> None:
        self.start()
        if self.task and not self.task.done():
            await asyncio.shield(self.task)
        elif self.progress.active:
            await self.done.wait()

    async def _drive(self) -> None:
        try:
            await self.owner._async_regenerate_local()
            # A debouncer may only have queued the actual refresh. Complete
            # only when _async_update_data finishes, not when request returns.
            await self.done.wait()
        except (asyncio.CancelledError, GenerationCancelled):
            self.finish("cancelled")
        except Exception:
            self.finish("error", "번호를 재생성하지 못했습니다. 기존 표시번호를 확인하고 HA 로그를 확인하세요.")
            _LOGGER.exception("로또 번호 재생성 실패")

    async def shutdown(self) -> None:
        """Stop CPU work at the next checkpoint; don't leave a thread running."""
        self.cancel.set()
        self.finish("cancelled")
        self.closed = True
        if self.worker:
            await asyncio.gather(self.worker, return_exceptions=True)
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.save_task:
            await asyncio.gather(self.save_task, return_exceptions=True)
