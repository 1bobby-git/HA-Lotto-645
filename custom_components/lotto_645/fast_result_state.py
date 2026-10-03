"""Overlay fast published results without feeding provisional numbers to analysis."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
import time
from typing import Any

from .models import LottoDraw, Recommendation
from .published_results import PublishedDraw, current_draw_round, draw_cutoff, poll_interval
from .purchased_tickets import combined_result
from .result_evaluator import evaluate_recommendations


def evaluate_saved(snapshot: dict | None, draw: LottoDraw) -> dict:
    """Only timestamped, pre-draw recommendations count as predictive results."""
    valid, excluded = [], []
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    based_on = snapshot.get('based_on_round')
    if (snapshot.get('target_round') == draw.round
            and type(based_on) is int and 0 < based_on < draw.round):
        rows = snapshot.get('recommendations', [])
        for raw in rows if isinstance(rows, list) else []:
            if not isinstance(raw, dict):
                continue
            kind = 'ai_generated_at' if raw.get('source') in ('ai', 'ai_task') else 'local_generated_at'
            try:
                timestamp = datetime.fromisoformat(raw.get('generated_at', snapshot.get(kind)) or '')
                recommendation = Recommendation.from_storage(raw)
                if timestamp.tzinfo is None or timestamp >= draw_cutoff(draw.round):
                    raise ValueError('not a pre-draw prediction')
            except (ValueError, TypeError, KeyError):
                excluded.append({'method_id': raw.get('method_id'),
                                 'reason': '추첨 전 생성 시각을 확인할 수 없거나 발표 이후 생성됨'})
            else:
                valid.append(recommendation)
    result = evaluate_recommendations(draw, valid, prediction_snapshot=snapshot)
    result['excluded_predictions'] = excluded
    result['snapshot_policy'] = 'pre_draw_v1'
    return result


class FastResultState:
    """Small mixin: result views use published facts, recommendation engine stays official."""

    @property
    def result_draw(self) -> LottoDraw | None:
        official = self.data.latest_draw if self.data else None
        state = getattr(self, '_fast_result', None) or {}
        if state.get('status') in ('provisional', 'cross_checked') and state.get('draw'):
            candidate = LottoDraw.from_storage(state['draw'])
            if official is None or candidate.round > official.round:
                return candidate
        return official

    @property
    def result_round(self) -> int | None:
        state = getattr(self, '_fast_result', None) or {}
        draw = self.result_draw
        if state.get('status') == 'conflict' and int(state.get('round', 0)) > (draw.round if draw else 0):
            return int(state['round'])
        return draw.round if draw else None

    @property
    def result_metadata(self) -> dict:
        state = getattr(self, '_fast_result', None) or {}
        official = self.data.latest_draw if self.data else None
        target = current_draw_round(datetime.now(UTC))
        waiting = {'pending': bool(target and (official is None or official.round < target)), 'round': target}
        if state.get('round', 0) > (official.round if official else 0):
            return {**{k: v for k, v in state.items() if k != 'draw'}, 'publication_wait': waiting}
        metadata = {'status': 'official_history', 'sources': [],
                    'notice': '공식 이력 미러/캐시 기준', 'official_round': official.round if official else None,
                    'latest_poll': getattr(self, '_fast_diagnostics', {})}
        if official and state.get('round') == official.round and state.get('draw'):
            old = LottoDraw.from_storage(state['draw'])
            metadata.update(status='official_confirmed' if (old.numbers, old.bonus) == (official.numbers, official.bonus) else 'official_corrected',
                            sources=state.get('sources', []), notice='공식 이력과 재대조 완료')
        metadata['publication_wait'] = waiting
        return metadata

    @property
    def result_history(self) -> list[LottoDraw]:
        draw = self.result_draw
        if draw and (not self.history or draw.round > self.history[-1].round):
            return [*self.history, draw]
        return self.history

    @property
    def winning_summary(self) -> dict[str, Any] | None:
        draw = self.result_draw
        if draw is None:
            return None
        metadata = self.result_metadata
        if metadata['status'] == 'conflict':
            return {'round': self.result_round, 'status': 'conflict', 'results': [],
                    'winners': [], 'losers': [], 'result_verification': metadata,
                    'checked_game_count': 0, 'winning_game_count': 0, 'losing_game_count': 0}
        snapshot = getattr(self, '_frozen_result_snapshot', None)
        evaluation = self._draw_evaluation
        if snapshot and snapshot.get('target_round') == draw.round:
            evaluation = evaluate_saved(snapshot, draw)
        # The ledger retains real pre-draw predictions for every generated method,
        # including methods later deselected. No backtest/invented recommendations.
        if hasattr(self, 'recorded_evaluation'):
            evaluation = self.recorded_evaluation(draw) or evaluation
        result = combined_result(draw, evaluation, self.purchase_book.report(self.result_history, draw.round))
        result['result_verification'] = metadata
        result['provisional'] = metadata['status'] in ('provisional', 'cross_checked')
        result['purchase_storage_error'] = self.purchase_storage_error
        result['pending_purchased_rounds'] = sorted(int(key) for key in self.purchase_book.records if int(key) > draw.round)
        if evaluation:
            result['excluded_predictions'] = evaluation.get('excluded_predictions', [])
        return result

    def _restore_fast_state(self, payload: dict) -> None:
        state = payload.get('fast_result')
        frozen = payload.get('frozen_result_snapshot')
        if not isinstance(state, dict) or state.get('status') not in ('provisional', 'cross_checked', 'conflict'):
            return
        if state.get('draw'):
            # Validate every persisted source and draw before showing it.
            for source in state.get('sources', []):
                PublishedDraw.from_dict({'draw': state['draw'], **source})
            if not state.get('sources'):
                return
        elif state.get('status') != 'conflict':
            return
        self._fast_result = state
        self._frozen_result_snapshot = frozen if isinstance(frozen, dict) else None

    def _accept_fast_state(self, state: dict) -> bool:
        if state.get('status') not in ('provisional', 'cross_checked', 'conflict'):
            return False
        old = getattr(self, '_fast_result', None) or {}
        if old.get('round', 0) > state.get('round', 0):
            return False
        if old.get('round') != state.get('round'):
            self._frozen_result_snapshot = deepcopy(self._prediction_snapshot)
        # Retain the SAME snapshot even if another publisher corrects the result.
        self._fast_result = state
        self._needs_storage_save = True
        return True

    async def async_poll_published_results(self, *, force: bool = False) -> None:
        """One bounded sweep at a time, until the target has official confirmation."""
        lock = getattr(self, '_fast_poll_lock', None)
        if lock is None:
            lock = self._fast_poll_lock = asyncio.Lock()
        if lock.locked():
            return
        async with lock:
            await self._async_poll_published_results(force=force)

    async def _async_poll_published_results(self, *, force: bool = False) -> None:
        from .fast_results import FastResultClient
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        now = datetime.now(UTC)
        target = current_draw_round(now)
        if target < 1 or self.data is None or self.data.latest_draw.round >= target:
            return
        interval = poll_interval(now)
        if interval is None:
            return
        saved = getattr(self, '_fast_result', None) or {}
        # Once publishers agree, lower traffic while waiting for official history.
        if saved.get('round') == target and saved.get('status') == 'cross_checked':
            interval = max(interval, 120)
        elapsed = time.monotonic() - getattr(self, '_last_fast_poll', -float('inf'))
        if elapsed < (29 if force else interval - 1):
            return
        self._last_fast_poll = time.monotonic()
        client = getattr(self, '_fast_client', None)
        if client is None:
            client = self._fast_client = FastResultClient(async_get_clientsession(self.hass))
            if saved.get('round') == target and saved.get('draw'):
                client.target = target
                for source in saved.get('sources', []):
                    evidence = PublishedDraw.from_dict({'draw': saved['draw'], **source})
                    client.evidence[evidence.publisher] = evidence

        async def accept(state: dict) -> None:
            self._fast_diagnostics = {
                'pending_round': target, 'checked_at': state.get('checked_at'),
                'providers': state.get('providers', {}), 'status': state.get('status'),
                'poll_interval_seconds': interval,
            }
            async with self._manual_lock:
                # Official history may have arrived while a publisher was slow.
                if self.data.latest_draw.round < target:
                    old = getattr(self, '_fast_result', None) or {}
                    changed = any(old.get(k) != state.get(k)
                                  for k in ('round', 'status', 'draw', 'sources'))
                    if changed:
                        self._accept_fast_state(state)
                    if getattr(self, "_needs_storage_save", False):
                        await self._save_storage()
                self.async_update_listeners()

        async def mirror() -> None:
            # Use a separate route concurrently. Never block a news result behind
            # a mirror timeout, and never regenerate recommendations or call AI.
            interval_mirror = max(60, interval)
            if force or time.monotonic() - getattr(self, '_last_fast_mirror', -float('inf')) >= interval_mirror - 1:
                self._last_fast_mirror = time.monotonic()
                await self.async_refresh_published_history(target)

        async def publishers() -> None:
            state = await client.check(target, now=now, on_result=accept)
            await accept(state)

        outcomes = await asyncio.gather(publishers(), mirror(), return_exceptions=True)
        for route, outcome in zip(('publishers', 'official_history'), outcomes):
            if isinstance(outcome, Exception):
                diagnostics = getattr(self, '_fast_diagnostics', {})
                diagnostics.setdefault('route_errors', {})[route] = type(outcome).__name__
                self._fast_diagnostics = diagnostics
                self.async_update_listeners()
