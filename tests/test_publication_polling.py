"""Bounded timing/route regression tests; not a live broadcast latency claim."""
import asyncio
import ast
from datetime import UTC, datetime, timedelta
import importlib
import logging
from pathlib import Path
from types import SimpleNamespace, ModuleType
import sys

from test_fast_results import candidate, NOW, pub, state_mod, models

fast = importlib.import_module('custom_components.lotto_645.fast_results')


def test_polling_has_no_midnight_or_sunday_gap_and_backs_off():
    start = pub.draw_cutoff(1240)
    assert pub.poll_interval(start) == 30
    assert pub.poll_interval(start + timedelta(hours=2)) == 120
    assert pub.poll_interval(start + timedelta(hours=6)) == 900
    assert pub.poll_interval(start + timedelta(days=2)) == 900
    assert pub.poll_interval(start + timedelta(weeks=1)) == 30


def test_feed_result_is_delivered_before_slow_publisher_finishes(monkeypatch):
    async def run():
        client = fast.FastResultClient(None)
        release = asyncio.Event()
        got = asyncio.Event()
        async def allowed(url): return True
        async def read(url, **kwargs):
            if 'yna.co.kr' in url:
                await release.wait()
            return b'<rss/>'
        def items(raw, publisher, target, now):
            if publisher != 'newsis': return []
            c = candidate()
            return [dict(title='1240회 로또 1등 11,13,19,20,31,44 보너스 27',
                         content='', url=c.url, published_at=NOW)]
        async def notify(result):
            if result['draw']: got.set()
        monkeypatch.setattr(client, '_allowed', allowed)
        monkeypatch.setattr(client, '_read', read)
        monkeypatch.setattr(fast, 'rss_items', items)
        task = asyncio.create_task(client.check(1240, now=NOW, on_result=notify))
        await asyncio.wait_for(got.wait(), 1)
        assert not task.done()
        release.set()
        result = await task
        assert result['draw']['bonus'] == 27
    asyncio.run(run())


def test_client_deduplicates_simultaneous_checks(monkeypatch):
    async def run():
        client = fast.FastResultClient(None)
        calls = []
        async def allowed(url): return True
        async def read(url, **kwargs): calls.append(url); return b'<rss/>'
        monkeypatch.setattr(client, '_allowed', allowed)
        monkeypatch.setattr(client, '_read', read)
        await asyncio.gather(client.check(1240, now=NOW), client.check(1240, now=NOW))
        assert len(calls) == len(pub.FEEDS)
    asyncio.run(run())


def test_result_poll_does_not_wait_for_mirror_or_regenerate(monkeypatch):
    async def run():
        published, release = asyncio.Event(), asyncio.Event()
        obj = state_mod.FastResultState()
        obj.hass = object()
        obj.data = SimpleNamespace(latest_draw=models.LottoDraw(1239, '2026-08-29', (1,2,3,4,5,6), 7))
        obj._manual_lock = asyncio.Lock()
        obj._prediction_snapshot = None
        obj.async_update_listeners = lambda: None
        async def save(): published.set()
        obj._save_storage = save
        async def mirror(target): await release.wait()
        obj.async_refresh_published_history = mirror
        class Client:
            async def check(self, target, **kwargs):
                result = pub.select_result([candidate()])
                await kwargs['on_result'](result)
                return result
        obj._fast_client = Client()
        class Clock:
            @staticmethod
            def now(tz): return NOW
        monkeypatch.setattr(state_mod, 'datetime', Clock)
        fake = ModuleType('homeassistant.helpers.aiohttp_client')
        fake.async_get_clientsession = lambda hass: None
        monkeypatch.setitem(sys.modules, fake.__name__, fake)
        task = asyncio.create_task(obj.async_poll_published_results())
        await asyncio.wait_for(published.wait(), 1)
        assert not task.done()
        # Overlapping scheduler tick must return rather than queue another sweep.
        await asyncio.wait_for(obj.async_poll_published_results(), 1)
        release.set(); await task
        assert obj.result_draw.round == 1240
        assert obj.data.latest_draw.round == 1239
    asyncio.run(run())


def test_confirmed_target_stops_network_checks(monkeypatch):
    async def run():
        obj = state_mod.FastResultState()
        obj.data = SimpleNamespace(latest_draw=candidate().draw)
        class Clock:
            @staticmethod
            def now(tz): return NOW
        monkeypatch.setattr(state_mod, 'datetime', Clock)
        fake = ModuleType('homeassistant.helpers.aiohttp_client')
        fake.async_get_clientsession = lambda hass: (_ for _ in ()).throw(AssertionError('network'))
        monkeypatch.setitem(sys.modules, fake.__name__, fake)
        await obj.async_poll_published_results()
    asyncio.run(run())


def history_method():
    path = Path(__file__).resolve().parents[1]/'custom_components/lotto_645/coordinator.py'
    cls = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef) and n.name=='Lotto645Coordinator')
    method = next(n for n in cls.body if getattr(n, 'name', '')=='async_refresh_published_history')
    from dataclasses import replace
    api = importlib.import_module('custom_components.lotto_645.api')
    namespace = {'replace': replace, 'LottoApiError': api.LottoApiError, '_LOGGER': logging.getLogger('test')}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(path), 'exec'), namespace)
    return namespace['async_refresh_published_history']


def test_successful_stale_mirror_uses_official_only_when_opted_in():
    async def run(allow):
        old = models.LottoDraw(1239,'2026-08-29',(1,2,3,4,5,6),7)
        draw = candidate().draw
        obj = SimpleNamespace(history=[old], data=models.Lotto645Data(
            latest_draw=old, analysis=None, history_count=1, generated_at=NOW, source_status="cache"),
            allow_official_fallback=allow, _manual_lock=asyncio.Lock())
        calls=[]
        async def mirror(): return [old], {}
        async def official(start,end): calls.append((start,end)); return [draw]
        async def save(): pass
        obj.client=SimpleNamespace(async_fetch_shared_mirror=mirror, begin_update_cycle=lambda:None,
                                   async_fetch_recent_range_official=official)
        obj._evaluate_prediction_snapshot=lambda:None; obj._sync_reviews=lambda:None
        obj._save_storage=save; obj.async_update_listeners=lambda:None
        await history_method()(obj,1240)
        assert calls == ([(1240,1240)] if allow else [])
        assert obj.history[-1].round == (1240 if allow else 1239)
    asyncio.run(run(True)); asyncio.run(run(False))


def test_history_save_failure_retries_without_losing_new_draw():
    async def run():
        old=models.LottoDraw(1239,'2026-08-29',(1,2,3,4,5,6),7)
        draw=candidate().draw
        obj=SimpleNamespace(history=[old], data=models.Lotto645Data(
            latest_draw=old, analysis=None, history_count=1, generated_at=NOW, source_status='cache'),
            allow_official_fallback=False, _manual_lock=asyncio.Lock())
        reads=[]; saves=[]
        async def mirror(): reads.append(1); return [old,draw],{}
        async def save():
            saves.append(1)
            if len(saves)==1: raise OSError('disk unavailable')
        obj.client=SimpleNamespace(async_fetch_shared_mirror=mirror)
        obj._save_storage=save; obj._evaluate_prediction_snapshot=lambda:None
        obj._sync_reviews=lambda:None; obj.async_update_listeners=lambda:None
        import pytest
        with pytest.raises(OSError): await history_method()(obj,1240)
        assert obj.data.latest_draw.round==1239
        await history_method()(obj,1240)
        assert obj.data.latest_draw.round==1240
        assert len(reads)==1 and len(saves)==2
    asyncio.run(run())


def test_partial_mirror_progress_is_not_lost_to_shared_etag():
    async def run():
        old=models.LottoDraw(1238,'2026-08-22',(1,2,3,4,5,6),7)
        partial=models.LottoDraw(1239,'2026-08-29',(2,3,4,5,6,7),8)
        obj=SimpleNamespace(history=[old], data=models.Lotto645Data(
            latest_draw=old, analysis=None, history_count=1, generated_at=NOW, source_status='cache'),
            allow_official_fallback=False, _manual_lock=asyncio.Lock())
        async def mirror(): return [old,partial],{}
        async def save(): pass
        obj.client=SimpleNamespace(async_fetch_shared_mirror=mirror)
        obj._save_storage=save; obj._evaluate_prediction_snapshot=lambda:None
        obj._sync_reviews=lambda:None; obj.async_update_listeners=lambda:None
        await history_method()(obj,1240)
        assert obj.history[-1].round==1239 and obj.data.latest_draw.round==1239
        assert obj._pending_result_round_transition is True
        assert obj._cached_ai_recommendation is None
        assert obj._local_generation_nonce == 0
    asyncio.run(run())


def test_pending_transition_clears_old_generation_cache_on_regular_refresh():
    path=Path(__file__).resolve().parents[1]/'custom_components/lotto_645/coordinator.py'
    tree=ast.parse(path.read_text())
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='_async_update_data')
    block=next(n for n in method.body if isinstance(n,ast.If)
               and '_pending_result_round_transition' in ast.unparse(n.test))
    function=ast.parse('def transition(self, old_latest_round):\n pass').body[0]
    function.body=[block]
    ns={}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(path),'exec'),ns)
    obj=SimpleNamespace(history=[candidate().draw],_pending_result_round_transition=True,
        _cached_ai_recommendation='old round',_cached_ai_generated_at=NOW,
        _local_generation_nonce=8,_regeneration_exclusions=((1,2,3,4,5,6),),
        _local_generated_at=NOW,_evaluate_prediction_snapshot=lambda:None)
    ns['transition'](obj,1240)
    assert obj._cached_ai_recommendation is None
    assert obj._cached_ai_generated_at is None
    assert obj._local_generation_nonce==0 and obj._regeneration_exclusions==()
    assert obj._pending_result_round_transition is False
