"""Real HA validation, explicit review import, persistence and publication reset."""
import asyncio
from copy import deepcopy
from datetime import date, timedelta
import inspect
import json
from pathlib import Path
import random
from types import SimpleNamespace
from unittest.mock import Mock, patch


async def verify_historical_validation(hass, owner):
    import voluptuous as vol
    from homeassistant.exceptions import Unauthorized
    from custom_components.lotto_645 import ticket_panel as panel
    from custom_components.lotto_645 import historical_validation_scores as scores
    from custom_components.lotto_645.models import LottoDraw

    unauthorized = SimpleNamespace(user=SimpleNamespace(is_admin=False))
    for handler in (panel.historical_validate, panel.historical_validation_state, panel.historical_validation_import):
        try:
            handler(hass, unauthorized, {'id': 600})
        except Unauthorized:
            pass
        else:
            raise AssertionError('All validation endpoints must require admin')
    schema = panel.historical_validate._ws_schema
    valid = schema({'id': 601, 'type': 'lotto_645/historical_validate', 'entry_id': owner.entry.entry_id,
                    'round': 61, 'method_ids': ['uniform_floyd']})
    assert 'seed' not in valid and valid['round'] == 61
    for key, bad in [('round', True), ('round', 31.5), ('seed', 0), ('seed', -1)]:
        msg = {**valid, key: bad}
        try:
            schema(msg)
        except vol.Invalid:
            pass
        else:
            raise AssertionError(f'Invalid integer accepted: {key}={bad}')
    import_schema = panel.historical_validation_import._ws_schema
    consent = {'id': 603, 'type': 'lotto_645/historical_validation_import',
               'entry_id': owner.entry.entry_id, 'confirmed': True, 'revision': 'a' * 64}
    assert import_schema(consent)['confirmed'] is True
    for bad in (False, 1, 'true', None):
        try:
            import_schema({**consent, 'confirmed': bad})
        except vol.Invalid:
            pass
        else:
            raise AssertionError(f'Non-boolean consent accepted: {bad!r}')
    for bad in ({k: v for k, v in consent.items() if k != 'confirmed'}, {**consent, 'methods': {'fake': 99}}):
        try:
            import_schema(bad)
        except vol.Invalid:
            pass
        else:
            raise AssertionError('Client-supplied score data or absent consent accepted')

    rng = random.Random(1845)
    previous_history = owner.history
    owner.history = [LottoDraw(i, (date(2002, 12, 7) + timedelta(weeks=i-1)).isoformat(), tuple(sorted(a[:6])), a[6])
                     for i in range(1, 66) for a in [rng.sample(range(1, 46), 7)]]
    fields = ['_prediction_snapshot', '_draw_evaluation', '_local_generation_nonce', '_regeneration_exclusions',
              '_review_summaries', '_review_dirty', '_review_save_error', '_sampling_cache', '_frozen_result_snapshot']
    before = {key: deepcopy(getattr(owner, key, None)) for key in fields}
    live = owner.data
    review = deepcopy(owner.review_book.to_storage())
    purchases = deepcopy(owner.purchase_book.to_storage())
    directory = Path(hass.config.config_dir) / '.storage'
    storage = {str(p): p.read_bytes() for p in directory.glob('*') if p.is_file()}
    score_name = f'lotto_645.validation_scores.{owner.entry.entry_id}'

    async def request(handler, **values):
        connection = SimpleNamespace(user=SimpleNamespace(is_admin=True), send_result=Mock(), send_error=Mock())
        await inspect.unwrap(handler)(hass, connection, {'id': 604, 'entry_id': owner.entry.entry_id, **values})
        connection.send_error.assert_not_called()
        return connection.send_result.call_args.args[1]

    try:
        with patch.object(hass, 'config_entries', SimpleNamespace(async_get_entry=lambda key: owner.entry if key == owner.entry.entry_id else None)):
            result = await request(panel.historical_validate, round=61,
                                   method_ids=['uniform_floyd', 'uniform_fisher_yates', 'selected_median_consensus', 'home_assistant_ai'])
            assert result['mode'] == 'historical_validation' and result['based_on_round'] == 60
            assert result['counts_toward_reviews'] is False and result['persisted'] is False
            assert len(result['results']) == 4
            board = result['validation_scoreboard']
            assert board['total_runs'] == 1 and board['unique_rounds'] == 1 and board['cycle_round'] == 65
            assert board['threshold'] == 3 and len(board['methods']) == 4
            assert board['unimported_runs'] == 1 and not scores.cached_reviews(hass, owner.entry.entry_id)
            json.dumps(result, allow_nan=False)
            # Drop process caches to exercise an actual HA Store read, not a UI snapshot.
            hass.data.pop(scores.CACHE_KEY, None)
            panel._validation_states(hass).pop(owner.entry.entry_id, None)
            state = await request(panel.historical_validation_state)
            assert state['status'] == 'completed' and state['result']['target_round'] == 61
            assert state['validation_scoreboard']['revision'] == board['revision']
            imported = await request(panel.historical_validation_import, confirmed=True, revision=board['revision'])
            assert imported['validation_scoreboard']['unimported_runs'] == 0
            historical = {r['method_id']: r['historical_review'] for r in imported['reviews'] if r.get('historical_review')}
            assert len(historical) == 4
            assert all(r['attempts'] == 1 and r['source'] == 'historical_validation' for r in historical.values())
            again = await request(panel.historical_validation_import, confirmed=True, revision=board['revision'])
            assert again['validation_scoreboard']['review_runs'] == 1
            assert scores.cached_reviews(hass, owner.entry.entry_id) == historical
            # A newly confirmed result resets only this cycle. Imported evidence survives.
            owner.history.append(LottoDraw(66, (date(2002, 12, 7) + timedelta(weeks=65)).isoformat(), (1, 2, 3, 4, 5, 6), 7))
            reset = await request(panel.historical_validation_state)
            assert reset['status'] == 'idle' and reset['validation_scoreboard']['total_runs'] == 0
            assert reset['validation_scoreboard']['cycle_round'] == 66 and reset['validation_scoreboard']['reset_at']
            assert scores.cached_reviews(hass, owner.entry.entry_id) == historical
            stale = SimpleNamespace(user=SimpleNamespace(is_admin=True), send_result=Mock(), send_error=Mock())
            await inspect.unwrap(panel.historical_validation_import)(hass, stale, {**consent, 'revision': board['revision']})
            stale.send_result.assert_not_called()
            assert stale.send_error.call_args.args[1] == 'validation_revision_conflict'
            hass.data.pop(scores.CACHE_KEY, None)
            restored = await request(panel.historical_validation_state)
            assert restored['validation_scoreboard']['total_runs'] == 0
            assert scores.cached_reviews(hass, owner.entry.entry_id) == historical
            # Publication while an executor is still computing must not re-add
            # an expired cycle or clear the imported review evidence.
            from custom_components.lotto_645 import historical_validation_runtime as runtime
            from custom_components.lotto_645.historical_validation import HistoricalValidationError
            worker = asyncio.get_running_loop().create_future()
            executor = Mock(return_value=worker)
            with patch.object(hass, 'async_add_executor_job', executor):
                task = asyncio.create_task(runtime.async_validate_history(hass, owner, 61, ('uniform_floyd',)))
                for _ in range(20):
                    if executor.called:
                        break
                    await asyncio.sleep(0)
                assert executor.called
                owner.history.append(LottoDraw(67, (date(2002, 12, 7) + timedelta(weeks=66)).isoformat(), (1, 2, 3, 4, 5, 6), 7))
                worker.set_result(result)
            try:
                await task
            except HistoricalValidationError as err:
                assert err.code == 'validation_cycle_expired'
            else:
                raise AssertionError('Expired CPU result was recorded')
            expired = await request(panel.historical_validation_state)
            assert expired['validation_scoreboard']['total_runs'] == 0
            assert expired['validation_scoreboard']['cycle_round'] == 67
            assert scores.cached_reviews(hass, owner.entry.entry_id) == historical

        assert owner.data is live
        assert before == {key: deepcopy(getattr(owner, key, None)) for key in fields}
        assert owner.review_book.to_storage() == review and owner.purchase_book.to_storage() == purchases
        after = {str(p): p.read_bytes() for p in directory.glob('*') if p.is_file()}
        changed = {path for path in set(storage) | set(after) if storage.get(path) != after.get(path)}
        assert changed and all(Path(path).name == score_name for path in changed), changed
    finally:
        owner.history = previous_history
    print('PASS: real HA admin/schema, persisted restoration, explicit/idempotent import, publication reset, stale consent rejection; actual pre-draw review and purchase bytes unchanged')
