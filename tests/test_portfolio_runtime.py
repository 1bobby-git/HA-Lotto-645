"""Execute the actual async handler body with isolated HA boundary fixtures."""
import ast
import asyncio
from copy import deepcopy
from functools import partial
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace

from test_analysis_engine import _history
from test_recommended_formulas import portfolio, rules

SOURCE=Path(__file__).resolve().parents[1]/'custom_components/lotto_645/portfolio_runtime.py'


def handler(monkeypatch):
    tree=ast.parse(SOURCE.read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='portfolio_preview')
    text=ast.get_source_segment(SOURCE.read_text(),fn)
    decorators=[ast.unparse(n) for n in fn.decorator_list]
    assert 'websocket_api.require_admin' in decorators
    assert 'websocket_api.async_response' in decorators
    assert "'ticket_count'" in decorators[0]
    fn.decorator_list=[]
    package=ModuleType('_portfolio_handler_fixture');package.__path__=[]
    module=ModuleType('_portfolio_handler_fixture.ticket_panel')
    module._coordinator=lambda hass,msg:hass.owner
    monkeypatch.setitem(sys.modules,package.__name__,package)
    monkeypatch.setitem(sys.modules,module.__name__,module)
    ns=dict(__package__=package.__name__,asyncio=asyncio,deepcopy=deepcopy,partial=partial,
            threading=threading,ConstraintError=rules.ConstraintError,RULES_KEY=rules.RULES_KEY,
            JOBS_KEY='jobs',generate_portfolio=portfolio.generate_portfolio,HomeAssistantError=RuntimeError)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(SOURCE),'exec'),ns)
    return ns['portfolio_preview'],ns


def setup(gate=None):
    owner=SimpleNamespace(history=_history(30),entry=SimpleNamespace(options={}),data=None)
    async def run(fn):
        if gate is not None: await gate.wait()
        return await asyncio.to_thread(fn)
    hass=SimpleNamespace(owner=owner,data={},async_add_executor_job=lambda fn:asyncio.create_task(run(fn)))
    results=[];errors=[]
    connection=SimpleNamespace(send_result=lambda *v:results.append(v),send_error=lambda *v:errors.append(v))
    message={'id':1,'entry_id':'one','candidate_numbers':list(range(1,10)), 'ticket_count':3,'mode':'wheel9','apply_rules':True}
    return hass,connection,message,results,errors


def test_read_only_result_is_scoped_and_worker_is_released(monkeypatch):
    fn,_=handler(monkeypatch)
    async def check():
        hass,conn,msg,results,errors=setup(); before=deepcopy(hass.owner.__dict__)
        await fn(hass,conn,msg);await asyncio.sleep(0)
        assert not errors and len(results)==1
        out=results[0][1]
        assert out['target_round']==31 and not out['saved_as_purchase']
        assert out['saved_rules_applied'] is True and out['verification_complete']
        assert hass.owner.__dict__==before and not hass.data['jobs']
    asyncio.run(check())


def test_one_inflight_job_and_stale_history_are_rejected(monkeypatch):
    fn,_=handler(monkeypatch)
    async def check():
        gate=asyncio.Event();hass,conn,msg,results,errors=setup(gate)
        task=asyncio.create_task(fn(hass,conn,msg));await asyncio.sleep(0)
        await fn(hass,conn,{**msg,'id':2})
        assert errors[-1][1]=='generation_busy'
        hass.owner.history=hass.owner.history[:-1]
        gate.set();await task
        assert not results and errors[-1][1]=='stale_context'
    asyncio.run(check())


def test_invalid_rules_remain_errors_not_partial_portfolios(monkeypatch):
    fn,_=handler(monkeypatch)
    async def check():
        hass,conn,msg,results,errors=setup();hass.owner.entry.options={'generation_rules':{'fixed':[1]}}
        await fn(hass,conn,msg)
        assert not results and errors[-1][1]=='infeasible_rules'
        await fn(hass,conn,{**msg,'apply_rules':False})
        assert len(results)==1 and not results[0][1]['saved_rules_applied']
    asyncio.run(check())


def test_timeout_cancels_bounded_work_and_retains_busy_gate_until_done(monkeypatch):
    fn,ns=handler(monkeypatch)
    async def timeout(*args,**kwargs): raise TimeoutError()
    ns['asyncio']=SimpleNamespace(wait_for=timeout,shield=asyncio.shield,CancelledError=asyncio.CancelledError)
    async def check():
        hass,conn,msg,results,errors=setup()
        await fn(hass,conn,msg)
        assert not results and errors[-1][1]=='search_limit'
        active=list(hass.data['jobs'].values())
        await asyncio.gather(*active,return_exceptions=True);await asyncio.sleep(0)
        assert not hass.data['jobs']
    asyncio.run(check())
