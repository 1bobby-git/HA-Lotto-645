"""Smoke-test actual HA classes/selectors; no live HA instance or AI provider calls."""
from __future__ import annotations
import asyncio
from dataclasses import replace
from pathlib import Path
import importlib
import json
import sys
import tempfile
import types
from unittest.mock import AsyncMock

ROOT=Path(__file__).resolve().parents[1]
for name,path in [('custom_components',ROOT/'custom_components'),('custom_components.lotto_645',ROOT/'custom_components/lotto_645')]:
    module=types.ModuleType(name);module.__path__=[str(path)];sys.modules.setdefault(name,module)

from probatio import to_field_list
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.data_entry_flow import FlowResultType

flow_module=importlib.import_module('custom_components.lotto_645.config_flow')
coordinator_module=importlib.import_module('custom_components.lotto_645.coordinator')
models=importlib.import_module('custom_components.lotto_645.models')
const=importlib.import_module('custom_components.lotto_645.const')


def serialize_form(result):
    schema=to_field_list(result['data_schema'],custom_serializer=cv.custom_serializer)
    json.dumps(schema,allow_nan=False)
    for field in schema:
        assert field.get('default','missing') is not None


async def main():
    with tempfile.TemporaryDirectory() as folder:
        hass=HomeAssistant(folder)
        flow=flow_module.Lotto645OptionsFlow(types.SimpleNamespace(options={}))
        flow.hass=hass;flow.handler='synthetic-config-entry';flow.flow_id='synthetic-flow'
        menu=await flow.async_step_init()
        assert menu['type']==FlowResultType.MENU
        assert menu['menu_options']==['recommendations','saju','purchases']
        serialize_form(await flow.async_step_recommendations())
        serialize_form(await flow.async_step_saju())
        result=await flow.async_step_recommendations({const.CONF_SELECTED_METHODS:['weighted_frequency']})
        assert result['type']==FlowResultType.CREATE_ENTRY
        invalid=await flow.async_step_recommendations({const.CONF_SELECTED_METHODS:['myungri_hetu_day_pillar']})
        assert invalid['errors']['base']=='saju_profile_required'
        submitted={
            'saju_calendar':'lunar', 'saju_lunar_standard':'korean', 'saju_birth_date':'20000230',
            'saju_birth_time':'1430','saju_gender':'male','saju_birth_place':'SYNTHETIC',
            'saju_timezone':'Asia/Seoul','saju_lunar_leap_month':False, 'saju_true_solar_time':False,
        }
        result=await flow.async_step_saju(submitted)
        assert result['type']==FlowResultType.CREATE_ENTRY,result
        assert result['data']['saju_birth_date']=='2000-02-30'
        assert result['data']['saju_birth_time']=='14:30'
        saved=flow_module.Lotto645OptionsFlow(types.SimpleNamespace(options=result['data']))
        saved.hass=hass;saved.handler='synthetic';saved.flow_id='synthetic'
        saved_form=await saved.async_step_saju()
        serialize_form(saved_form)
        fields=to_field_list(saved_form['data_schema'],custom_serializer=cv.custom_serializer)
        defaults={field.get('name'):field.get('default') for field in fields}
        assert defaults.get('saju_birth_date')=='2000-02-30'
        assert defaults.get('saju_birth_time')=='14:30'
        good=await saved.async_step_recommendations({const.CONF_SELECTED_METHODS:['myungri_hetu_day_pillar','bayesian_shrinkage']})
        assert good['type']==FlowResultType.CREATE_ENTRY,good
        submitted['saju_birth_date']='20000231'
        rejected=await flow.async_step_saju(submitted)
        assert rejected['errors']['base']=='invalid_saju_profile'
        serialize_form(rejected)
        # Test the coordinator's manual/AI parsing contracts without network/store.
        cls=coordinator_module.Lotto645Coordinator
        obj=object.__new__(cls)
        obj.entry=types.SimpleNamespace(options={})
        obj._manual_lock=asyncio.Lock();obj._local_generation_nonce=0
        obj._local_generated_at=None
        obj._saju_profile_valid=False
        obj._prediction_snapshot=None;obj._draw_evaluation=None;obj._needs_storage_save=False
        rec=models.Recommendation(1,'weighted_frequency','local','stats',(1,2,3,4,5,6),'local reason',.5,{})
        saju=models.Recommendation(2,'myungri_hetu_day_pillar','saju','saju',(7,8,9,10,11,12),'DO NOT SEND PERSONAL SAJU',.5,{})
        ai=models.Recommendation(3,'home_assistant_ai','ai','ai',(13,14,15,16,17,18),'ai',None,{},'ai_task')
        from datetime import datetime,timezone
        obj.data=models.Lotto645Data(models.LottoDraw(30,'2026-09-05',(30,31,32,33,34,35),36),models.AnalysisResult(31,30,(rec,saju),{}),30,datetime.now(timezone.utc),'cache',ai)
        obj.async_request_refresh=AsyncMock()
        await obj.async_refresh_and_regenerate()
        assert obj.data.ai_recommendation is ai
        assert obj._suppress_ai_generation_once is True
        assert set(obj._regeneration_exclusions)=={rec.numbers,saju.numbers,ai.numbers}
        assert 'DO NOT SEND PERSONAL SAJU' not in obj._ai_prompt(obj.data.analysis,1)
        obj.history=[obj.data.latest_draw]
        obj._prediction_snapshot={
            "target_round":30,"based_on_round":29,"local_generation_sequence":0,
            "local_generated_at":None,"recommendations":[
                models.Recommendation(1,"old","old sensor","test",(30,31,32,1,2,3),"r",.5,{}).to_storage()
            ]
        }
        obj._evaluate_prediction_snapshot()
        assert obj._draw_evaluation["round"]==30
        assert obj._draw_evaluation["results"][0]["prize"]=="5등"
        for bad in (1.5,True,float('nan'),float('inf')):
            payload={f'number_{i}':i for i in range(1,7)};payload['number_1']=bad;payload['reason']='x'
            try:obj._parse_ai_result(payload,obj.data.analysis)
            except coordinator_module.AiRecommendationError:pass
            else:raise AssertionError(f'invalid AI number accepted: {bad}')
        # Purchased tickets use a separate durable store; normal options/AI are untouched.
        purchase_module=importlib.import_module('custom_components.lotto_645.purchased_tickets')
        sensor_module=importlib.import_module('custom_components.lotto_645.sensor')
        from homeassistant.helpers.storage import Store
        obj.hass=hass
        obj.entry=types.SimpleNamespace(entry_id='purchase-smoke', options={
            const.CONF_SELECTED_METHODS:['weighted_frequency'], 'saju_birth_date':'2000-01-01',
        }, runtime_data=obj)
        obj.purchase_book=purchase_module.PurchaseBook()
        obj.purchase_storage_error=False
        obj._purchase_lock=asyncio.Lock()
        obj._purchase_store=Store(hass,1,'lotto_purchase_smoke')
        from unittest.mock import Mock
        obj.async_update_listeners=Mock()
        before_ai=obj.data.ai_recommendation
        before_nonce=obj._local_generation_nonce
        refresh_calls=obj.async_request_refresh.await_count
        def purchase_flow():
            f=flow_module.Lotto645OptionsFlow(obj.entry)
            f.hass=hass;f.handler='purchase-smoke';f.flow_id='purchase-flow'
            return f
        f=purchase_flow()
        serialize_form(await f.async_step_purchases())
        bad_round=await f.async_step_purchases({'purchase_round':'wrong'})
        assert bad_round['errors']['purchase_round']=='invalid_purchase_round'
        form=await f.async_step_purchases({'purchase_round':'30'})
        assert form['step_id']=='purchase_games'
        serialize_form(form)
        invalid=await f.async_step_purchase_games({'game_b':'1 1 2 3 4 5'})
        assert invalid['errors']['game_b']=='invalid_purchase_numbers'
        assert not obj.purchase_book.records
        saved=await f.async_step_purchase_games({
            'game_a':'303132333435', 'game_e':'1, 2, 3, 4, 5, 6',
        })
        assert saved['type']==FlowResultType.CREATE_ENTRY
        assert saved['data']==obj.entry.options
        assert obj._local_generation_nonce==before_nonce
        assert obj.data.ai_recommendation is before_ai
        assert obj.async_request_refresh.await_count==refresh_calls
        disk=await obj._purchase_store.async_load()
        restored=purchase_module.PurchaseBook.from_storage(disk)
        assert restored.records==obj.purchase_book.records
        assert restored.report(obj.history)['winning_game_count']==1
        form=await purchase_flow().async_step_purchases({'purchase_round':'30'})
        serialize_form(form)
        fields=to_field_list(form['data_schema'],custom_serializer=cv.custom_serializer)
        defaults={field['name']:field.get('default') for field in fields}
        assert defaults['game_a']=='30, 31, 32, 33, 34, 35'
        # Dynamically named draw sensor keeps_unique_id unchanged across rounds.
        numbers_sensor=sensor_module.LottoDrawNumbersSensor(obj)
        unique=numbers_sensor.unique_id
        assert numbers_sensor.name=='30회 추첨번호'
        assert numbers_sensor.native_value=='30, 31, 32, 33, 34, 35'
        old_data=obj.data
        obj.data=replace(obj.data, latest_draw=models.LottoDraw(31,'2026-09-12',(1,2,3,4,5,6),7))
        assert numbers_sensor.name=='31회 추첨번호' and numbers_sensor.unique_id==unique
        obj.data=old_data
        summary_sensor=sensor_module.LottoRecommendationsSensor(obj)
        assert summary_sensor.native_value==31
        assert '추천 대상 회차' in summary_sensor.extra_state_attributes['purpose']
        purchased_sensor=sensor_module.LottoPurchasedTicketsSensor(obj)
        assert purchased_sensor.native_value=='30회 · 1개 당첨 · 최고 1등'
        win_sensor=sensor_module.LottoWinningStatusSensor(obj)
        assert win_sensor.native_value=='2개 당첨 · 최고 1등'  # old recommendation 5th + A 1st
        assert obj.winning_summary['recommendation_game_count']==1
        assert obj.winning_summary['purchased_game_count']==2
        # Next round remains pending until matching result is actually adopted.
        await obj.async_save_purchase_record(31, {'game_c':'010203040506'})
        assert purchased_sensor.native_value=='31회 · 1게임 · 추첨 대기'
        assert obj.winning_summary['round']==30
        assert obj.winning_summary['purchased_game_count']==2
        assert obj.winning_summary['pending_purchased_rounds']==[31]
        # Roll back neither memory nor old rows on failed durable save.
        before=obj.purchase_book.to_storage()
        actual_store=obj._purchase_store
        obj._purchase_store=types.SimpleNamespace(async_save=AsyncMock(side_effect=OSError('synthetic disk failure')))
        f=purchase_flow();await f.async_step_purchases({'purchase_round':'31'})
        failed=await f.async_step_purchase_games({'game_a':'10 11 12 13 14 15'})
        assert failed['errors']['base']=='purchase_storage_unavailable'
        assert obj.purchase_book.to_storage()==before
        obj._purchase_store=actual_store
        obj.purchase_storage_error=True
        blocked=await purchase_flow().async_step_purchases()
        assert blocked['type']==FlowResultType.ABORT
        assert blocked['reason']=='purchase_storage_unavailable'
        obj.purchase_storage_error=False
        await obj.async_save_purchase_record(31, {}, clear=True)
        assert '30' in obj.purchase_book.records and '31' not in obj.purchase_book.records
        await hass.async_stop(force=True)
    print('PASS: real HA options menu/forms/JSON serialization/profile save/compact normalization/gating; coordinator manual/AI contracts; purchased five-line round storage, restore, atomic save and draw-name checks')

if __name__=='__main__':asyncio.run(main())
