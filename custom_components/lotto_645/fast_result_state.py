"""Overlay fast published results without feeding provisional numbers to analysis."""
from __future__ import annotations

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
    snapshot = snapshot or {}
    if snapshot.get('target_round') == draw.round and snapshot.get('based_on_round', draw.round) < draw.round:
        for raw in snapshot.get('recommendations', []):
            if not isinstance(raw, dict):
                continue
            kind = 'ai_generated_at' if raw.get('source') in ('ai', 'ai_task') else 'local_generated_at'
            try:
                timestamp = datetime.fromisoformat(snapshot.get(kind) or '')
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
        if state.get('round', 0) > (official.round if official else 0):
            return {k: v for k, v in state.items() if k != 'draw'}
        metadata = {'status': 'official_history', 'sources': [],
                    'notice': '공식 이력 미러/캐시 기준', 'official_round': official.round if official else None,
                    'latest_poll': getattr(self, '_fast_diagnostics', {})}
        if official and state.get('round') == official.round and state.get('draw'):
            old = LottoDraw.from_storage(state['draw'])
            metadata.update(status='official_confirmed' if (old.numbers, old.bonus) == (official.numbers, official.bonus) else 'official_corrected',
                            sources=state.get('sources', []), notice='공식 이력과 재대조 완료')
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
        """Automatic publication-window polling; result checking never calls AI."""
        from .fast_results import FastResultClient
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        now = datetime.now(UTC)
        interval = poll_interval(now)
        if not force and interval is None:
            return
        if time.monotonic() - getattr(self, '_last_fast_poll', 0) < (55 if force else (interval or 900) - 1):
            return
        self._last_fast_poll = time.monotonic()
        target = current_draw_round(now)
        if target < 1 or self.data is None:
            return
        # Mirror/publication checks are independent; a slow mirror timeout must
        # not delay the first complete publisher result.
        if self.data.latest_draw.round < target:
            client = getattr(self, '_fast_client', None)
            if client is None:
                client = self._fast_client = FastResultClient(async_get_clientsession(self.hass))
                saved = getattr(self, '_fast_result', None) or {}
                if saved.get('round') == target and saved.get('draw'):
                    client.target = target
                    for source in saved.get('sources', []):
                        candidate = PublishedDraw.from_dict({'draw': saved['draw'], **source})
                        client.evidence[candidate.publisher] = candidate
            state = await client.check(target, now=now)
            self._fast_diagnostics = {'pending_round': target, 'checked_at': state.get('checked_at'),
                                      'providers': state.get('providers', {}), 'status': state.get('status')}
            async with self._manual_lock:
                if self._accept_fast_state(state):
                    await self._save_storage()
                self.async_update_listeners()
        # Official reconciliation is less frequent than the fast RSS path.
        if force or time.monotonic() - getattr(self, '_last_fast_mirror', 0) >= 300:
            self._last_fast_mirror = time.monotonic()
            self._suppress_ai_generation_once = True
            await self.async_check_draw_result()
