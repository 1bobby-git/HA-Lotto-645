"""Real HA decorators, isolated computation and validation-only score storage."""
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
    from custom_components.lotto_645.models import LottoDraw

    unauthorized=SimpleNamespace(user=SimpleNamespace(is_admin=False))
    try:panel.historical_validate(hass,unauthorized,{'id':600})
    except Unauthorized:pass
    else:raise AssertionError('historical validation must require admin')
    schema=panel.historical_validate._ws_schema
    valid=schema({'id':601,'type':'lotto_645/historical_validate','entry_id':owner.entry.entry_id,
                  'round':61,'method_ids':['uniform_floyd']})
    assert 'seed' not in valid and valid['round']==61
    for key,bad in [('round',True),('round',31.5),('seed',0),('seed',-1)]:
        msg={'id':601,'type':'lotto_645/historical_validate','entry_id':owner.entry.entry_id,
             'round':61,'method_ids':['uniform_floyd'],key:bad}
        try:schema(msg)
        except vol.Invalid:pass
        else:raise AssertionError(f'Invalid integer accepted: {key}={bad}')
    # Use the real coordinator's stored review, purchase, live and frozen data,
    # but give it a synthetic contiguous history for this dedicated request.
    rng=random.Random(1845)
    previous_history=owner.history
    owner.history=[LottoDraw(i,(date(2002,12,7)+timedelta(weeks=i-1)).isoformat(),tuple(sorted(a[:6])),a[6])
                   for i in range(1,66) for a in [rng.sample(range(1,46),7)]]
    fields=['_prediction_snapshot','_draw_evaluation','_local_generation_nonce','_regeneration_exclusions',
            '_review_summaries','_review_dirty','_review_save_error','_sampling_cache','_frozen_result_snapshot']
    before={key:deepcopy(getattr(owner,key,None)) for key in fields}
    live=owner.data
    review=deepcopy(owner.review_book.to_storage());purchases=deepcopy(owner.purchase_book.to_storage())
    directory=Path(hass.config.config_dir)/'.storage'
    storage={str(p):p.read_bytes() for p in directory.glob('*') if p.is_file()}
    score_name=f'lotto_645.validation_scores.{owner.entry.entry_id}'
    connection=SimpleNamespace(user=SimpleNamespace(is_admin=True),send_result=Mock(),send_error=Mock())
    with patch.object(hass,'config_entries',SimpleNamespace(async_get_entry=lambda key:owner.entry if key==owner.entry.entry_id else None)):
        await inspect.unwrap(panel.historical_validate)(hass,connection,{
            'id':602,'entry_id':owner.entry.entry_id,'round':61,
            'method_ids':['uniform_floyd','uniform_fisher_yates','selected_median_consensus','home_assistant_ai']})
    connection.send_error.assert_not_called()
    result=connection.send_result.call_args.args[1]
    assert result['mode']=='historical_validation' and result['based_on_round']==60
    assert result['counts_toward_reviews'] is False and result['persisted'] is False
    assert len(result['results'])==4
    board=result['validation_scoreboard']
    assert board['total_runs']==1 and board['unique_rounds']==1
    assert board['threshold']==3 and len(board['methods'])==4
    json.dumps(result,allow_nan=False)
    assert owner.data is live
    assert before=={key:deepcopy(getattr(owner,key,None)) for key in fields}
    assert owner.review_book.to_storage()==review and owner.purchase_book.to_storage()==purchases
    after={str(p):p.read_bytes() for p in directory.glob('*') if p.is_file()}
    changed={path for path in set(storage)|set(after) if storage.get(path)!=after.get(path)}
    assert changed and all(Path(path).name==score_name for path in changed), changed
    owner.history=previous_history
    print('PASS: admin-only historical validation, strict prefix-only simulation; live/review/purchase data unchanged and only validation score storage updated')
