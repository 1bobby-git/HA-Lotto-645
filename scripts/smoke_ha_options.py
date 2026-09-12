"""Smoke-test actual HA classes/selectors; no live HA instance or AI provider calls."""
from __future__ import annotations
import asyncio
import ast
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
    init_tree=ast.parse((ROOT/'custom_components/lotto_645/__init__.py').read_text())
    schedule=next(ast.literal_eval(node.value) for node in init_tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='_RESULT_CHECKS_UTC' for target in node.targets))
    assert schedule == ((5,11,55),(5,12,20),(5,12,50),(5,13,30),(5,14,0),(6,0,40))
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
        obj._cached_ai_recommendation=ai;obj._cached_ai_generated_at=None
        obj.async_request_refresh=AsyncMock()
        await obj.async_refresh_and_regenerate()
        assert obj.data.ai_recommendation is ai
        assert obj._suppress_ai_generation_once is True
        assert set(obj._regeneration_exclusions)=={rec.numbers,saju.numbers,ai.numbers}
        assert 'DO NOT SEND PERSONAL SAJU' not in obj._ai_prompt(obj.data.analysis,1)
        obj.history=[obj.data.latest_draw]
        obj._prediction_snapshot={
            "target_round":30,"based_on_round":29,"local_generation_sequence":0,
            "local_generated_at":"2003-06-27T10:00:00+00:00","recommendations":[
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
        obj.entry=types.SimpleNamespace(entry_id='purchase-smoke', domain=const.DOMAIN, options={
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
        assert summary_sensor.native_value=='31회 추천 · 3게임'
        assert '추천 대상 회차' in summary_sensor.extra_state_attributes['purpose']
        purchased_sensor=sensor_module.LottoPurchasedTicketsSensor(obj)
        assert purchased_sensor.native_value=='30회 · 1개 당첨 · 최고 1등'
        win_sensor=sensor_module.LottoWinningStatusSensor(obj)
        assert win_sensor.name=='30회 당첨 여부'
        assert win_sensor.native_value=='2개 당첨 · 최고 1등'  # old recommendation 5th + A 1st
        assert obj.winning_summary['recommendation_game_count']==1
        assert obj.winning_summary['purchased_game_count']==2
        # Next round remains pending until matching result is actually adopted.
        await obj.async_save_purchase_record(31, {'game_c':'010203040506'})
        assert purchased_sensor.native_value=='31회 · 1게임 · 추첨 대기'
        assert obj.winning_summary['round']==30
        assert obj.winning_summary['purchased_game_count']==2
        assert obj.winning_summary['pending_purchased_rounds']==[31]
        before_nonce=obj._local_generation_nonce
        before_ai=obj._cached_ai_recommendation
        calls=obj.async_request_refresh.await_count
        obj._suppress_ai_generation_once=False
        await obj.async_check_draw_result()
        assert obj._suppress_ai_generation_once is True
        assert obj._local_generation_nonce==before_nonce
        assert obj._cached_ai_recommendation is before_ai
        assert obj._manual_result_refresh_requested is True
        assert obj.async_request_refresh.await_count==calls+1
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
        # New panel backend: real HA decorators with an admin-authenticated mock
        # connection. Parsing a QR is a preview only, not a purchase write.
        import inspect
        from unittest.mock import patch
        panel_module=importlib.import_module('custom_components.lotto_645.ticket_panel')
        from homeassistant.exceptions import Unauthorized
        unauthorized=types.SimpleNamespace(user=types.SimpleNamespace(is_admin=False))
        try:
            panel_module.qr_preview(hass,unauthorized,{'id':50,'entry_id':'purchase-smoke','qr':'ignored'})
        except Unauthorized:
            pass
        else:
            raise AssertionError('QR endpoint permitted non-admin')
        connection=types.SimpleNamespace(user=types.SimpleNamespace(is_admin=True),send_result=Mock(),send_error=Mock())
        original=obj.purchase_book.to_storage()
        with patch.object(hass, 'config_entries', types.SimpleNamespace(async_get_entry=lambda entry_id: obj.entry if entry_id == obj.entry.entry_id else None)):
            await inspect.unwrap(panel_module.qr_preview)(hass,connection,{'id':51,'entry_id':'purchase-smoke',
                'qr':'https://m.dhlottery.co.kr/qr.do?method=winQr&v=0031q0102030405060000000000'})
            preview=connection.send_result.call_args.args[1]
            assert preview['round']==31 and preview['values']['game_a']=='1, 2, 3, 4, 5, 6'
            assert obj.purchase_book.to_storage()==original
            await inspect.unwrap(panel_module.purchases_save)(hass,connection,{'id':52,'entry_id':'purchase-smoke',
                'round':31,'revision':'','clear':False,'values':preview['values']})
            assert '31' in obj.purchase_book.records
            await inspect.unwrap(panel_module.purchases_save)(hass,connection,{'id':53,'entry_id':'purchase-smoke',
                'round':31,'revision':'','clear':False,'values':{'game_a':'10 11 12 13 14 15'}})
            assert connection.send_error.call_args.args[1]=='purchase_revision_conflict'
            assert obj.purchase_book.records['31']['games'][0]['numbers']==[1,2,3,4,5,6]
        # New review storage, category grouping and binary prize details use
        # actual HA entity classes/registry. No fabricated user tickets.
        review_module=importlib.import_module('custom_components.lotto_645.review')
        binary_module=importlib.import_module('custom_components.lotto_645.binary_sensor')
        button_module=importlib.import_module('custom_components.lotto_645.button')
        from homeassistant.helpers.entity import EntityCategory
        obj.review_book=review_module.ReviewBook();obj.review_storage_error=False
        obj._review_dirty=False;obj._review_save_error=False;obj._review_save_lock=asyncio.Lock()
        obj._review_store=Store(hass,1,'lotto_review_smoke')
        obj._store=Store(hass,3,'lotto_history_review_smoke')
        obj._regeneration_exclusions=();obj._local_generated_at=None
        obj._frozen_result_snapshot=None;obj._fast_result=None
        obj._prediction_snapshot={"target_round":30,"based_on_round":29,
            "local_generated_at":"2003-06-27T10:00:00+00:00",
            "recommendations":[models.Recommendation(1,"old","old sensor","test",(30,31,32,1,2,3),"",None,{}).to_storage()]}
        obj._sync_reviews()
        await obj._save_storage()
        restored=review_module.ReviewBook.from_storage(await obj._review_store.async_load())
        assert restored.summary('old')['reviewed_rounds']==1
        assert obj.review_for_method('old')['winning_rounds']==1
        # Method label reads the actual local review, not the engine's fit score.
        game_sensor=sensor_module.LottoGameSensor(obj,'weighted_frequency')
        assert game_sensor.name.startswith('☆평가대기')
        obj._review_summaries['weighted_frequency']={'mean_score':80.,'stars':4.,'reviewed_rounds':1}
        assert game_sensor.name.startswith('★4.0 · 80.0점')
        assert game_sensor.entity_category is None
        assert summary_sensor.entity_category==EntityCategory.DIAGNOSTIC
        assert sensor_module.LottoMethodGuideSensor(obj).entity_category==EntityCategory.DIAGNOSTIC
        assert numbers_sensor.device_info['identifiers'] != game_sensor.device_info['identifiers']
        detail=binary_module.LottoWinningDetailSensor(obj)
        assert detail.name=='30회 당첨 상세'
        assert detail.is_on is True
        attrs=detail.extra_state_attributes
        assert attrs['winning_game_count']==2
        assert attrs['winners'][0]['recommended_numbers']
        assert attrs['winners'][0]['prize_rank'] is not None
        assert all('entity_id' in row for row in attrs['results'])
        assert attrs['review_notice']
        result_button=button_module.LottoResultCheckButton(obj)
        obj.async_poll_published_results=AsyncMock()
        await result_button.async_press()
        obj.async_poll_published_results.assert_awaited_once_with(force=True)
        # Unknown is never reported as false/no-win on a pending/conflicted draw.
        obj._fast_result={'status':'conflict','round':31,'sources':[]}
        assert detail.is_on is None
        assert detail.extra_state_attributes['results']==[]
        # A store write failure keeps the ledger dirty for retry, not a fake success.
        obj._fast_result=None;obj._review_dirty=True
        actual_review_store=obj._review_store
        obj._review_store=types.SimpleNamespace(async_save=AsyncMock(side_effect=OSError('test disk error')))
        await obj._save_storage()
        assert obj._review_dirty and obj._review_save_error
        obj._review_store=actual_review_store
        await obj._save_storage()
        assert not obj._review_dirty and not obj._review_save_error
        await hass.async_stop(force=True)
    print('PASS: real HA options menu/forms/JSON serialization/profile save/compact normalization/gating; coordinator manual/AI contracts; purchased five-line round storage, restore, atomic save and draw-name checks')

if __name__=='__main__':asyncio.run(main())
