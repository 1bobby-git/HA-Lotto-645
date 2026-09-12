"""Exercise the actual coordinator method AST without importing a running HA.

These verify method behavior, not UI/end-to-end Home Assistant compatibility.
"""
import ast
import asyncio
from datetime import UTC, datetime
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from test_analysis_engine import models, methods, const, _history


def method(name):
    path=Path(__file__).resolve().parents[1]/'custom_components/lotto_645/coordinator.py'
    tree=ast.parse(path.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Lotto645Coordinator')
    node=next(n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    code=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])
    ns={'math':math,'AiRecommendationError':ValueError,'Recommendation':models.Recommendation,
        'AI_METHOD_ID':const.AI_METHOD_ID,'FIRST_PRIZE_ODDS':const.FIRST_PRIZE_ODDS,
        'DISCLAIMER':const.DISCLAIMER,'datetime':datetime,'UTC':UTC,
        'METHOD_MYUNGRI_HETU':methods.METHOD_MYUNGRI_HETU}
    exec(compile(ast.fix_missing_locations(code),str(path),'exec'),ns)
    return ns[name]


@pytest.mark.parametrize('bad',[True,3.7,float('nan'),float('inf'),'3',None])
def test_ai_does_not_coerce_invalid_numbers(bad):
    obj=SimpleNamespace(history=_history(30),configured_ai_entity_id=None)
    payload={f'number_{i}':i for i in range(1,7)} | {'reason':'테스트'}
    payload['number_3']=bad
    result=SimpleNamespace(recommendations=(),target_round=31,based_on_round=30)
    with pytest.raises(ValueError):
        method('_parse_ai_result')(obj,payload,result)


def test_ai_prompt_excludes_personal_saju_details():
    personal=SimpleNamespace(method_id=methods.METHOD_MYUNGRI_HETU,label='private',numbers=(1,2,3,4,5,6),reason='PRIVATE_BIRTH_SECRET')
    public=SimpleNamespace(method_id=methods.METHOD_WEIGHTED_FREQUENCY,label='freq',numbers=(2,4,6,8,10,12),reason='PUBLIC_STATS')
    result=SimpleNamespace(recommendations=(personal,public),summary={},target_round=31,based_on_round=30)
    text=method('_ai_prompt')(object(),result,1)
    assert 'PRIVATE_BIRTH_SECRET' not in text and 'PUBLIC_STATS' in text


def test_manual_refresh_serializes_and_does_not_touch_cached_ai():
    async def run():
        obj=SimpleNamespace(_regenerate_lock=asyncio.Lock(),_local_generation_nonce=4,
            _cached_ai_recommendation=object(),async_request_refresh=AsyncMock())
        previous=obj._cached_ai_recommendation
        refresh=method('async_refresh_and_regenerate')
        await asyncio.gather(refresh(obj),refresh(obj))
        assert obj._local_generation_nonce==6
        assert obj._suppress_ai_generation_once is True
        assert obj._cached_ai_recommendation is previous
        assert obj.async_request_refresh.await_count==2
    asyncio.run(run())
