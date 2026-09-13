from pathlib import Path
root=Path('custom_components/lotto_645')
p=root/'review.py';s=p.read_text();pos=s.index('    def set_result(',s.index('class ReviewBook'))
s=s[:pos]+'''    def record_evaluation(self, evaluation: Any, *, now: datetime | None = None) -> tuple[bool, list[dict]]:
        """Recover real legacy evaluated tickets, not invented retrospective games.

        Old releases rotated prediction_snapshot to next week but kept
        draw_evaluation with original numbers/basis/timestamp. Never substitute
        evaluated_at (after the draw) or the current generation time.
        """
        if not isinstance(evaluation, dict):
            return False, []
        r = evaluation.get('round')
        if type(r) is not int or not 1 <= r <= 10000 or not isinstance(evaluation.get('results'), list):
            return False, []
        now = now or datetime.now(UTC)
        changed = False
        excluded = []
        for result in evaluation['results']:
            if not isinstance(result, dict) or result.get('source') == 'purchased':
                continue
            method = result.get('method_id')
            if not isinstance(method, str) or not 1 <= len(method) <= 100:
                continue
            # A verified snapshot already wins; never replace it from a summary.
            if method in self.rounds.get(str(r), {}).get('predictions', {}):
                continue
            source = result.get('source', 'analysis')
            ai = source in ('ai', 'ai_task')
            when = result.get('generated_at')
            if when is None:
                when = evaluation.get('prediction_ai_generated_at' if ai else 'prediction_generated_at')
            based = result.get('based_on_round', evaluation.get('prediction_based_on_round'))
            try:
                if type(based) is not int or not 0 < based < r:
                    raise ValueError('basis')
                stamp = _timestamp(when)
                if stamp >= _cutoff(r) or stamp > now:
                    raise ValueError('timestamp')
                numbers = parse_ticket(result.get('recommended_numbers', result.get('numbers')))
            except (TypeError, ValueError, KeyError):
                excluded.append({'method_id': method, 'round': r,
                                 'prize': str(result.get('prize', '')),
                                 'reason': '추첨 전 생성시각·기준회차를 확인할 수 없어 누적평가 제외'})
                continue
            snapshot = {'target_round': r, 'based_on_round': based,
                        'ai_generated_at' if ai else 'local_generated_at': stamp.isoformat(),
                        'recommendations': [{'method_id': method, 'source': source,
                          'label': result.get('sensor_name', result.get('label', method)),
                          'numbers': list(numbers)}]}
            changed = self.record_snapshot(snapshot, now=now) or changed
        return changed, excluded

''' +s[pos:];p.write_text(s)
p=root/'review_state.py';s=p.read_text();s=s.replace("        official = {draw.round: draw for draw in self.history}","""        recovered, exclusions = book.record_evaluation(getattr(self, '_draw_evaluation', None))
        changed = recovered or changed
        self._review_exclusions = exclusions
        official = {draw.round: draw for draw in self.history}""")
s=s.replace("        return getattr(self, '_review_summaries', {}).get(method_id, {})", """        summary = dict(getattr(self, '_review_summaries', {}).get(method_id, {}))
        excluded = next((row for row in getattr(self, '_review_exclusions', [])
                         if row['method_id'] == method_id), None)
        if excluded:
            summary['current_review_exclusion'] = excluded
        return summary""")
s=s.replace("        return getattr(self, '_review_reports', {}).get(round_no, {})", """        report = dict(getattr(self, '_review_reports', {}).get(round_no, {}))
        exclusions = [row for row in getattr(self, '_review_exclusions', []) if row['round'] == round_no]
        if exclusions:
            report.setdefault('round', round_no)
            report.setdefault('methods', [])
            report['excluded_methods'] = exclusions
        return report""")
p.write_text(s)
p=root/'result_evaluator.py';s=p.read_text().replace('        "prediction_generated_at": snapshot.get("local_generated_at"),','        "prediction_generated_at": snapshot.get("local_generated_at"),\n        "prediction_ai_generated_at": snapshot.get("ai_generated_at"),');p.write_text(s)
p=root/'fast_result_state.py';s=p.read_text().replace('    valid, excluded = [], []','    valid, excluded = [], []\n    timestamps = {}',1).replace('                valid.append(recommendation)','                valid.append(recommendation)\n                timestamps[recommendation.method_id] = timestamp.isoformat()',1).replace("    result['excluded_predictions'] = excluded", "    for row in result['results']:\n        row['generated_at'] = timestamps.get(row['method_id'])\n        row['based_on_round'] = based_on\n    result['excluded_predictions'] = excluded",1);p.write_text(s)
