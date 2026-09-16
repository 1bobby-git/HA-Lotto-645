"""Use exact production view/subscription functions with isolated HA fixtures."""
import ast
import asyncio
from datetime import datetime, UTC
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from test_analysis_engine import ROOT, models


def production_function(name, namespace):
    tree=ast.parse((ROOT/'custom_components/lotto_645/ticket_panel.py').read_text(encoding="utf-8"))
    node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    node.decorator_list=[]
    if name=='subscribe_updates':
        # Decorator is only HA callback annotation, not business logic.
        node.body=[n for n in node.body if not isinstance(n,ast.ImportFrom)]
        for inner in node.body:
            if isinstance(inner,ast.FunctionDef):inner.decorator_list=[]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'production','exec'),namespace)
    return namespace[name]


def test_view_includes_current_sensor_records_separate_from_last_draw():
    rec=models.Recommendation(1,'uniform_fisher_yates','균등','local',(2,8,17,25,34,43),'reason',None,{})
    current=models.AnalysisResult(31,30,(rec,),{})
    from custom_components.lotto_645.purchased_tickets import PurchaseBook
    book=PurchaseBook(); book.selected_round=29
    owner=SimpleNamespace(result_draw=None,purchase_book=book,result_metadata={'status':'waiting'},result_round=30,
        data=SimpleNamespace(analysis=current,generated_at=datetime.now(UTC),ai_recommendation=None),
        result_history=[],winning_summary={'round':30,'results':[]},entry=SimpleNamespace(entry_id='entry'),purchase_storage_error=False,
        local_generation_sequence=4)
    view=production_function('_view',{'Any':object,'_review_rows':lambda c:[], 'panel_metadata':lambda *args:{'draw_schedule':{'round':31}}})(owner)
    assert view['recommendation_target']==31 and view['winning']['round']==30 and view['round']==29
    assert view['recommendations'][0]['numbers']==list(rec.numbers)
    assert view['recommendations'][0]['method_id']==rec.method_id and view['entry_id']=='entry'
    assert 'historical_validation' not in view


def test_subscription_is_entry_scoped_and_contains_no_numbers_or_profiles():
    registrations={}
    def listen(event,callback):
        registrations[event]=callback
        return lambda:registrations.pop(event,None)
    hass=SimpleNamespace(config_entries=SimpleNamespace(async_get_entry=lambda key:SimpleNamespace(domain='lotto_645')),
                         bus=SimpleNamespace(async_listen=listen))
    conn=SimpleNamespace(subscriptions={},send_event=Mock(),send_result=Mock(),send_error=Mock())
    fn=production_function('subscribe_updates',{'DOMAIN':'lotto_645'})
    asyncio.run(fn(hass,conn,{'id':7,'entry_id':'entry'}))
    callback=registrations['lotto_645_updated']
    callback(SimpleNamespace(data={'entry_id':'other','numbers':[1,2,3]}))
    conn.send_event.assert_not_called()
    callback(SimpleNamespace(data={'entry_id':'entry','numbers':[1,2,3]}))
    conn.send_event.assert_called_once_with(7,{'entry_id':'entry'})
    conn.subscriptions[7]()
    assert not registrations


def test_pruner_keeps_guide_and_active_formula_but_removes_deselected():
    source=ast.parse((ROOT/'custom_components/lotto_645/sensor.py').read_text(encoding="utf-8"))
    keep={'_active_optional_sensor_unique_ids','_prune_stale_optional_sensor_entities'}
    nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in keep]
    entries=[SimpleNamespace(domain='sensor',platform='lotto_645',unique_id='entry_'+name,entity_id=name)
             for name in ['method_guide','method_uniform_fisher_yates','method_personal_lucky','recommendations']]
    entries.append(SimpleNamespace(domain='sensor',platform='other',unique_id='entry_method_other',entity_id='other'))
    registry=SimpleNamespace(async_remove=Mock())
    er=SimpleNamespace(async_get=lambda h:registry,async_entries_for_config_entry=lambda r,e:entries)
    env={'Lotto645Coordinator':object,'HomeAssistant':object,'ConfigEntry':object,'er':er,'DOMAIN':'lotto_645',
         'METHOD_MYUNGRI_HETU':'myungri_hetu_day_pillar'}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'sensor','exec'),env)
    entry=SimpleNamespace(entry_id='entry')
    owner=SimpleNamespace(entry=entry,selected_method_ids=['uniform_fisher_yates'],configured_method_ids=['uniform_fisher_yates'],ai_enabled=False)
    env['_prune_stale_optional_sensor_entities'](object(),entry,owner)
    registry.async_remove.assert_called_once_with('method_personal_lucky')
