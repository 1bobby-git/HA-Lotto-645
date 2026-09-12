"""Durable local review aggregation and inexpensive cached entity presentation."""
from __future__ import annotations

from .models import LottoDraw, Recommendation
from .result_evaluator import evaluate_recommendations


class ReviewState:
    """Cache presentation only; ledger stores actual snapshots and corrected results."""

    def _sync_reviews(self) -> None:
        if getattr(self, 'review_storage_error', False) or not hasattr(self, 'review_book'):
            return
        book = self.review_book
        changed = False
        for snapshot in (getattr(self, '_prediction_snapshot', None),
                         getattr(self, '_frozen_result_snapshot', None)):
            changed = book.record_snapshot(snapshot) or changed
        official = {draw.round: draw for draw in self.history}
        for key in book.rounds:
            if draw := official.get(int(key)):
                changed = book.set_result(draw, confirmed=True, status='official_history') or changed
        fast = getattr(self, '_fast_result', None) or {}
        if fast.get('round') not in official:
            if fast.get('status') == 'conflict':
                changed = book.invalidate_provisional(fast['round']) or changed
            elif fast.get('draw') and fast.get('status') in ('provisional', 'cross_checked'):
                changed = book.set_result(LottoDraw.from_storage(fast['draw']), confirmed=False,
                                          status=fast['status']) or changed
        if changed or not hasattr(self, '_review_reports'):
            self._review_reports = {int(key): book.round_review(int(key)) for key in book.rounds}
            ids = {method for row in book.rounds.values() for method in row['predictions']}
            self._review_summaries = {key: book.summary(key, self._review_reports) for key in ids}
        if changed:
            self._review_dirty = True

    def review_for_method(self, method_id: str) -> dict:
        if getattr(self, 'review_storage_error', False):
            return {'status': 'storage_error', 'notice': '리뷰 저장소 오류: 원본을 보존하며 누적하지 않습니다'}
        return getattr(self, '_review_summaries', {}).get(method_id, {})

    def review_for_round(self, round_no: int | None) -> dict:
        return getattr(self, '_review_reports', {}).get(round_no, {})

    def recorded_evaluation(self, draw: LottoDraw) -> dict | None:
        """Include deselected methods which really existed before this draw."""
        if getattr(self, 'review_storage_error', False) or not hasattr(self, 'review_book'):
            return None
        predictions = self.review_book.rounds.get(str(draw.round), {}).get('predictions', {})
        if not predictions:
            return None
        recommendations = [Recommendation(index, method_id, row['label'], 'saved_pre_draw',
                                           tuple(row['numbers']), '', None, {}, row['source'])
                           for index, (method_id, row) in enumerate(predictions.items(), 1)]
        report = evaluate_recommendations(draw, recommendations)
        for result in report['results']:
            prediction = predictions[result['method_id']]
            result['generated_at'] = prediction['generated_at']
            result['based_on_round'] = prediction['based_on_round']
        report['snapshot_policy'] = 'local_review_ledger_pre_draw_v1'
        return report
