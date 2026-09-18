"""Use exact production view/subscription functions with isolated HA fixtures."""
import ast
import asyncio
from datetime import datetime, UTC
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from test_analysis_engine import ROOT, models


def production_function(name, namespace):
    from custom_components.lotto_645.review_selection import review_method_ids, selected_round_review
    from custom_components.lotto_645.purchased_tickets import matching_purchase_games
    namespace.update(
        review_method_ids=review_method_ids,
        selected_round_review=selected_round_review,
        matching_purchase_games=matching_purchase_games,
    )
    namespace.setdefault("__package__", "custom_components.lotto_645")
    tree=ast.parse((ROOT/'custom_components/lotto_645/ticket_panel.py').read_text(encoding="utf-8"))
    if name == '_view':
        helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_purchase_formula_reviews')
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper],type_ignores=[])),'production','exec'),namespace)
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
        local_generation_sequence=4,configured_method_ids=('uniform_fisher_yates',),ai_enabled=False)
    view=production_function('_view',{'Any':object,'_review_rows':lambda c:[], 'panel_metadata':lambda *args:{'draw_schedule':{'round':31}}})(owner)
    assert view['recommendation_target']==31 and view['winning']['round']==30 and view['round']==29
    assert view['recommendations'][0]['numbers']==list(rec.numbers)
    assert view['recommendations'][0]['method_id']==rec.method_id and view['entry_id']=='entry'
    assert 'historical_validation' not in view


def test_view_includes_all_five_games_for_each_ticket_preview():
    from custom_components.lotto_645.purchased_tickets import PurchaseBook

    five_a = {
        "game_a": "1, 2, 3, 4, 5, 6",
        "game_b": "7, 8, 9, 10, 11, 12",
        "game_c": "13, 14, 15, 16, 17, 18",
        "game_d": "19, 20, 21, 22, 23, 24",
        "game_e": "25, 26, 27, 28, 29, 30",
    }
    five_b = {
        "game_a": "2, 3, 4, 5, 6, 7",
        "game_b": "8, 9, 10, 11, 12, 13",
        "game_c": "14, 15, 16, 17, 18, 19",
        "game_d": "20, 21, 22, 23, 24, 25",
        "game_e": "26, 27, 28, 29, 30, 31",
    }
    book = PurchaseBook().updated(31, five_a, now=datetime.now(UTC))
    first_id = book.selected_ticket_id
    book = book.updated(31, five_b, now=datetime.now(UTC), new_ticket=True)
    second_id = book.selected_ticket_id
    current = models.AnalysisResult(31, 30, (), {})
    owner = SimpleNamespace(
        result_draw=None,
        purchase_book=book,
        result_metadata={"status": "waiting"},
        result_round=30,
        data=SimpleNamespace(
            analysis=current,
            generated_at=datetime.now(UTC),
            ai_recommendation=None,
        ),
        result_history=[],
        winning_summary={"round": 30, "results": []},
        entry=SimpleNamespace(entry_id="entry"),
        purchase_storage_error=False,
        local_generation_sequence=1,
        configured_method_ids=(),
        ai_enabled=False,
    )
    view = production_function(
        "_view",
        {
            "Any": object,
            "_review_rows": lambda c: [],
            "panel_metadata": lambda *args: {"draw_schedule": {"round": 31}},
        },
    )(owner, 31, first_id)

    previews = view["ticket_previews"]
    assert [item["ticket_id"] for item in previews] == [first_id, second_id]
    assert [item["ticket_number"] for item in previews] == [1, 2]
    assert [item["game_count"] for item in previews] == [5, 5]
    assert all([game["slot"] for game in item["games"]] == list("ABCDE") for item in previews)


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


def test_view_marks_exact_same_round_purchase_matches():
    rec = models.Recommendation(
        1,
        "uniform_fisher_yates",
        "균등 공식",
        "local",
        (11, 13, 18, 22, 31, 32),
        "reason",
        None,
        {"target_round": 31, "generation_id": "generated-31"},
    )
    current = models.AnalysisResult(31, 30, (rec,), {})
    from custom_components.lotto_645.purchased_tickets import PurchaseBook

    book = PurchaseBook().updated(
        31, {"game_b": "11, 13, 18, 22, 31, 32"}, now=datetime.now(UTC)
    )
    ticket_id = book.selected_ticket_id
    owner = SimpleNamespace(
        result_draw=None,
        purchase_book=book,
        result_metadata={"status": "waiting"},
        result_round=30,
        data=SimpleNamespace(
            analysis=current,
            generated_at=datetime.now(UTC),
            ai_recommendation=None,
        ),
        result_history=[],
        winning_summary={"round": 30, "results": []},
        entry=SimpleNamespace(entry_id="entry"),
        purchase_storage_error=False,
        local_generation_sequence=4,
        configured_method_ids=("uniform_fisher_yates",),
        ai_enabled=False,
    )
    view = production_function(
        "_view",
        {
            "Any": object,
            "_review_rows": lambda c: [],
            "panel_metadata": lambda *args: {"draw_schedule": {"round": 31}},
        },
    )(owner)

    current_row = view["recommendations"][0]
    assert current_row["purchase_match"] is True
    assert current_row["purchase_match_count"] == 1
    assert current_row["purchase_matches"][0]["slot"] == "B"

    assert view["generation_matches"] == [
        {
            "ticket_id": ticket_id,
            "ticket_number": 1,
            "slot": "B",
            "numbers": [11, 13, 18, 22, 31, 32],
            "formula_id": "uniform_fisher_yates",
            "formula_label": "균등 공식",
            "generation_id": "generated-31",
        }
    ]


def test_purchase_formula_lineage_survives_later_regeneration_in_panel_payload():
    from custom_components.lotto_645.purchased_tickets import PurchaseBook

    old_numbers = (11, 13, 18, 22, 31, 32)
    new_numbers = (2, 8, 17, 25, 34, 43)
    link = {
        "formula_id": "uniform_floyd",
        "formula_label": "균등 공식 · Floyd",
        "source": "core_service",
        "generated_at": "2026-09-18T08:00:00+00:00",
        "based_on_round": 30,
        "target_round": 31,
        "generation_sequence": 4,
        "formula_version": "1",
        "core_version": "1.22.1",
        "generation_id": "old-generation",
    }
    book = PurchaseBook().updated(
        31,
        {"game_a": ", ".join(map(str, old_numbers))},
        now=datetime(2026, 9, 18, 8, 5, tzinfo=UTC),
        formula_links_by_slot={"A": [link]},
    )
    current_rec = models.Recommendation(
        1,
        "uniform_floyd",
        "균등 공식 · Floyd",
        "균등",
        new_numbers,
        "new",
        None,
        {"target_round": 31, "generation_id": "new-generation"},
    )
    current = models.AnalysisResult(31, 30, (current_rec,), {})
    latest_review = {
        "round": 31,
        "status": "waiting",
        "methods": [{
            "method_id": "uniform_floyd",
            "label": "균등 공식 · Floyd",
            "numbers": list(new_numbers),
            "target_round": 31,
            "status": "waiting",
        }],
        "peer_count": 1,
    }
    owner = SimpleNamespace(
        result_draw=None,
        purchase_book=book,
        result_metadata={"status": "waiting"},
        result_round=30,
        data=SimpleNamespace(
            analysis=current,
            generated_at=datetime.now(UTC),
            ai_recommendation=None,
        ),
        result_history=[],
        winning_summary={"round": 30, "results": []},
        entry=SimpleNamespace(entry_id="entry"),
        purchase_storage_error=False,
        local_generation_sequence=5,
        configured_method_ids=("uniform_floyd",),
        ai_enabled=False,
        review_for_round=lambda round_no: latest_review,
    )
    view = production_function(
        "_view",
        {
            "Any": object,
            "_review_rows": lambda c: [],
            "panel_metadata": lambda *args: {"draw_schedule": {"round": 31}},
        },
    )(owner)

    assert view["recommendations"][0]["numbers"] == list(new_numbers)
    assert view["recommendations"][0]["purchase_match"] is False
    tracked = view["purchase_formula_reviews"]
    assert len(tracked) == 1
    assert tracked[0]["formula_id"] == "uniform_floyd"
    assert tracked[0]["recommended_numbers"] == list(old_numbers)
    assert tracked[0]["generation_id"] == "old-generation"
    assert tracked[0]["purchase_linked"] is True


def test_purchase_linked_generation_gets_same_round_draw_result():
    from custom_components.lotto_645.purchased_tickets import PurchaseBook
    draw = models.LottoDraw(40, "2003-09-06", (1, 2, 3, 4, 5, 6), 7)
    link = {
        "formula_id": "uniform_floyd",
        "formula_label": "균등 공식 · Floyd",
        "source": "core_service",
        "generated_at": "2026-09-18T08:00:00+00:00",
        "based_on_round": 39,
        "target_round": 40,
        "generation_sequence": 3,
        "generation_id": "generation-40",
    }
    book = PurchaseBook().updated(
        40,
        {"game_a": "1 2 3 4 5 6"},
        now=datetime(2026, 9, 18, 8, 5, tzinfo=UTC),
        formula_links_by_slot={"A": [link]},
    )
    rows = production_function("_purchase_formula_reviews", {})(book, [draw], 40)
    assert len(rows) == 1
    assert rows[0]["prize"] == "1등"
    assert rows[0]["prize_rank"] == 1
    assert rows[0]["main_match_count"] == 6
    assert rows[0]["counts_toward_rating"] is False
