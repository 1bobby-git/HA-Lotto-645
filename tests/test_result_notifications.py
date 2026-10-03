"""Notification contracts with HA service/storage fakes; no live device claim."""
import asyncio
from dataclasses import replace
from types import ModuleType, SimpleNamespace
import sys

from test_fast_results import candidate, NOW, pub
from custom_components.lotto_645 import result_notifications as alerts


def test_only_complete_target_result_and_conflict_correction_labels():
    a = alerts.announcement(candidate().draw, {'status':'provisional'}, NOW)
    assert '공식 확인 전' in a['message']
    assert alerts.announcement(None, {'status':'waiting'}, NOW) is None
    assert alerts.announcement(replace(candidate().draw,round=1239), {'status':'official_history'}, NOW) is None
    b = alerts.announcement(candidate().draw, {'status':'cross_checked'}, NOW,a)
    assert b['key']==a['key']
    correction=alerts.announcement(replace(candidate().draw,bonus=28), {'status':'official_corrected'},NOW,b)
    assert correction['key']!=b['key'] and '정정' in correction['title']
    conflict=alerts.announcement(candidate().draw,{'status':'conflict'},NOW,a)
    assert '보류' in conflict['title'] and '11, 13' not in conflict['message']
    assert alerts.announcement(candidate().draw, {'status':'conflict'}, NOW) is None


def harness(monkeypatch, *, fail_save=False):
    calls=[]; events=[]
    storage={'saved':None,'fail':fail_save}
    class Store:
        def __init__(self,*args): pass
        async def async_load(self): return storage['saved']
        async def async_save(self,payload):
            if storage['fail']: raise OSError('disk')
            storage['saved']=payload
    service=SimpleNamespace(async_create=lambda hass,message,**kw:calls.append((message,kw)))
    component=ModuleType('homeassistant.components');component.persistent_notification=service
    module=ModuleType('homeassistant.helpers.storage');module.Store=Store
    monkeypatch.setitem(sys.modules,'homeassistant.components',component)
    monkeypatch.setitem(sys.modules,'homeassistant.helpers.storage',module)
    class Clock:
        @staticmethod
        def now(tz): return NOW
    monkeypatch.setattr(alerts,'datetime',Clock)
    def coordinator():
        return SimpleNamespace(entry=SimpleNamespace(entry_id='entry-a'),result_draw=candidate().draw,
            result_metadata={'status':'provisional'},
            hass=SimpleNamespace(bus=SimpleNamespace(async_fire=lambda *args:events.append(args))))
    return coordinator,storage,calls,events


def test_one_card_per_round_restart_dedup_and_official_updates(monkeypatch):
    async def run():
        make,storage,calls,events=harness(monkeypatch)
        c=make();await alerts.async_publish_result_notification(c)
        await alerts.async_publish_result_notification(c)
        assert len(calls)==1 and len(events)==1
        c=make();await alerts.async_publish_result_notification(c)
        assert len(calls)==1
        c.result_metadata={'status':'official_confirmed'}
        await alerts.async_publish_result_notification(c)
        assert len(calls)==2 and calls[0][1]['notification_id']==calls[1][1]['notification_id']
        assert events[0][1]['announcement']['key']==events[1][1]['announcement']['key']
        assert set(events[0][1])=={'entry_id','announcement'}
    asyncio.run(run())


def test_first_install_baselines_old_official_not_future_announcement(monkeypatch):
    async def run():
        make,storage,calls,events=harness(monkeypatch)
        c=make();c.result_metadata={'status':'official_history'}
        await alerts.async_publish_result_notification(c)
        assert not calls and storage['saved']['initialized']
        # First setup before announcement records initialization but no result.
        storage['saved']=None;c=make();c.result_draw=replace(candidate().draw,round=1239)
        c.result_metadata={'status':'official_history'}
        await alerts.async_publish_result_notification(c)
        c.result_draw=candidate().draw
        await alerts.async_publish_result_notification(c)
        assert len(calls)==1
    asyncio.run(run())


def test_failed_save_retries_same_card_before_emitting_event(monkeypatch):
    async def run():
        make,storage,calls,events=harness(monkeypatch,fail_save=True)
        c=make()
        import pytest
        with pytest.raises(OSError):await alerts.async_publish_result_notification(c)
        assert not events
        storage['fail']=False
        await alerts.async_publish_result_notification(c)
        assert len(calls)==2 and calls[0][1]['notification_id']==calls[1][1]['notification_id']
        assert len(events)==1
    asyncio.run(run())


def test_delayed_result_is_not_a_clock_based_announcement():
    from datetime import timedelta
    delayed=NOW+timedelta(days=2)
    assert pub.poll_interval(delayed)==900
    assert alerts.announcement(None,{'status':'waiting'},delayed) is None
    assert alerts.announcement(candidate().draw,{'status':'official_history'},delayed)


def test_browser_opt_in_background_and_dedup():
    import subprocess, shutil
    import pytest
    if not shutil.which('node'):pytest.skip('Node unavailable; browser contract test not run')
    result=subprocess.run(['node','tests/js/result-notifications.mjs'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr
