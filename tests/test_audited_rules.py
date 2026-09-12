"""Rule conformance and numerical invariants, NOT tests of lottery predictivity."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

import pytest
from korean_lunar_calendar import KoreanLunarCalendar
from lunar_python import Solar

from test_analysis_engine import analysis, methods, models, myungri, _history, _profile
from custom_components.lotto_645 import saju_rules as rules


@pytest.mark.parametrize('branch', list(rules.BRANCHES))
def test_source_hidden_ratios(branch):
    assert sum(rules.HIDDEN[branch].values()) == pytest.approx(1.0)
    assert all(s in rules.STEMS and v > 0 for s, v in rules.HIDDEN[branch].items())


@pytest.mark.parametrize('day', list(rules.STEMS))
def test_all_ten_gods_against_source_matrix(day):
    rows = (
        '비견 겁재 식신 상관 편재 정재 편관 정관 편인 정인',
        '겁재 비견 상관 식신 정재 편재 정관 편관 정인 편인',
        '편인 정인 비견 겁재 식신 상관 편재 정재 편관 정관',
        '정인 편인 겁재 비견 상관 식신 정재 편재 정관 편관',
        '편관 정관 편인 정인 비견 겁재 식신 상관 편재 정재',
        '정관 편관 정인 편인 겁재 비견 상관 식신 정재 편재',
        '편재 정재 편관 정관 편인 정인 비견 겁재 식신 상관',
        '정재 편재 정관 편관 정인 편인 겁재 비견 상관 식신',
        '식신 상관 편재 정재 편관 정관 편인 정인 비견 겁재',
        '상관 식신 정재 편재 정관 편관 정인 편인 겁재 비견',
    )
    expected = rows[rules.STEMS.index(day)].split()
    assert [rules.ten_god(day, s) for s in rules.STEMS] == expected
    assert set(expected) == set(rules.TEN_GODS)


@pytest.mark.parametrize('value,expected', [
    ('1900-01-01','甲戌'),('2000-01-01','戊午'),('2020-01-01','癸卯'),
    ('2025-01-01','庚午'),('2026-01-01','乙亥'),('1992-08-15','癸亥'),
])
def test_corrected_anchors_with_independent_calendar(value, expected):
    date = datetime.fromisoformat(value)
    c = KoreanLunarCalendar()
    assert c.setSolarDate(date.year, date.month, date.day)
    assert expected + '日' in c.getChineseGapJaString()
    pillars, _ = myungri._clock_pillars(date, date, 'Asia/Seoul')
    assert pillars['day']['ganzhi'] == expected


def test_valid_lunar_february_30_not_rejected_as_gregorian():
    p = _profile() | {'calendar':'lunar','birth_date':'2024-02-30'}
    myungri.validate_saju_profile(p)
    _, meta = myungri._solar_from_profile(p)
    assert meta['birth_solar'].startswith('2024-04-08')


@pytest.mark.parametrize('update', [
    {'birth_date':'2024-02-30'}, {'birth_date':'1990-05-17evil'},
    {'birth_time':'14:30evil'}, {'birth_time':'24:00'},
    {'calendar':'lunar','birth_date':'2025-02-30'},
    {'calendar':'lunar','birth_date':'2024-01-01','lunar_leap_month':True},
    {'true_solar_time':True,'longitude':float('nan')},
    {'true_solar_time':True,'longitude':float('inf')},
    {'birth_date':'2026-03-08','birth_time':'02:30','timezone':'America/New_York'},
    {'birth_date':'2025-11-02','birth_time':'01:30','timezone':'America/New_York'},
])
def test_reject_invalid_dates_geo_and_dst(update):
    with pytest.raises(myungri.SajuProfileError):
        myungri.validate_saju_profile(_profile() | update)


def test_same_instant_has_same_year_and_month_across_timezones():
    china = datetime(2026, 2, 4, 0, 0)
    lunar = Solar.fromYmdHms(2026, 2, 4, 0, 0, 0).getLunar()
    lichun = datetime.fromisoformat(lunar.getJieQiTable()['立春'].toYmdHms())
    for sign in (-1, 1):
        instant = lichun + timedelta(seconds=sign)
        seoul = instant + timedelta(hours=1)
        a, _ = myungri._clock_pillars(instant, instant, 'Etc/GMT-8')
        b, _ = myungri._clock_pillars(seoul, seoul, 'Asia/Seoul')
        assert (a['year']['ganzhi'], a['month']['ganzhi']) == (b['year']['ganzhi'], b['month']['ganzhi'])
        if sign == -1:
            before = a
        else:
            assert before['year']['ganzhi'] != a['year']['ganzhi']
            assert before['month']['ganzhi'] != a['month']['ganzhi']


def test_late_zi_obeys_explicit_same_day_source_choice():
    for hour in (0, 22, 23):
        d = datetime(2000, 1, 1, hour, 30)
        pillars, _ = myungri._clock_pillars(d, d, 'Asia/Seoul')
        assert pillars['day']['ganzhi'] == '戊午'
        if hour == 23:
            assert pillars['time']['ganzhi'] == '壬子'


def test_source_12_growth_stages():
    expected = ('목욕 관대 건록 제왕 쇠 병 사 묘 절 태 양 장생').split()
    for branch, stage in zip(rules.BRANCHES, expected, strict=True):
        assert myungri._pillar_from_ganzhi('甲'+branch,'甲')['growth_stage'] == stage


def test_self_punishment_requires_distinct_positions():
    a = {'stem':'甲','branch':'辰'}
    assert rules.relations({'year':a}) == []
    events = rules.relations({'year':a,'day':a})
    assert any(e['kind'] == '자형' for e in events)
    assert all(e['transformation_confirmed'] is False for e in events)


@pytest.mark.parametrize('symbols,kind', [('寅卯辰','방합'),('申子辰','삼합'),('寅巳申','삼형'),('子酉','파'),('子未','해'),('子卯','자묘형')])
def test_full_source_relation_families(symbols, kind):
    pillars = {str(i): {'stem':'甲','branch':b} for i,b in enumerate(symbols)}
    assert any(e['kind'] == kind for e in rules.relations(pillars))


def test_personal_rules_and_layers_reach_actual_number_scores():
    ctx = myungri.build_myungri_context('2026-09-05',_profile())
    assert set(ctx['luck_layers']) == {'대운','세운','월운','일진','시진'}
    assert sum(layer['weight'] for layer in ctx['luck_layers'].values()) == pytest.approx(1)
    assert len(ctx['luck_cycle']['timeline']) >= 8
    assert ctx['natal_evaluation']['pattern']['name']
    assert set(ctx['number_ten_gods'].values()) == set(rules.TEN_GODS)
    assert len(set(ctx['number_resonance'].values())) >= 5
    for n, score in ctx['number_resonance'].items():
        assert sum(ctx['number_score_breakdown'][n].values()) == pytest.approx(score, abs=2e-6)
    # A structural relation changes the per-element layer scores, not just its label.
    target = {'day': {'ganzhi':'己丑','stem':'己','branch':'丑'}}
    pref = dict.fromkeys(rules.ELEMENTS,.5) | {'earth':.9}
    reports, effect = rules.evaluate_layers({'day':{'stem':'甲','branch':'子'}},target,{},pref)
    assert reports['일진']['relations']
    _, without = rules.evaluate_layers({'day':{'stem':'乙','branch':'申'}},target,{},pref)
    assert effect['earth'] != without['earth']


def test_missing_target_date_does_not_invent_today():
    with pytest.raises(myungri.SajuProfileError):
        myungri.build_myungri_context('',_profile())


def test_midrank_has_no_numeric_label_bias():
    assert set(analysis._rank01(dict.fromkeys(range(1,46),1.0)).values()) == {.5}
    assert analysis._rank01({1:0.,2:0.,3:1.,4:1.}) == {1:1/6,2:1/6,3:5/6,4:5/6}


def test_bayesian_shrinkage_preserves_magnitude():
    history = _history(60)
    light = analysis._bayesian_recent(history, prior_strength=45)
    heavy = analysis._bayesian_recent(history, prior_strength=450)
    for n in range(1,46):
        assert abs(heavy[n]) <= abs(light[n]) + 1e-12
    ranked, _ = analysis._feature_maps(history)
    assert ranked['bayesian_60'] == {n: .5 + .5*math.tanh(v / analysis.NUMBER_PROBABILITY) for n,v in light.items()}


def test_exact_sampling_probabilities_and_conservation():
    assert math.comb(45,6) == 8145060
    assert sum(analysis.OVERLAP_PROBABILITIES) == pytest.approx(1)
    assert sum(k*p for k,p in enumerate(analysis.OVERLAP_PROBABILITIES)) == pytest.approx(.8)
    assert analysis.PAIR_PROBABILITY == pytest.approx(math.comb(43,4)/math.comb(45,6))
    assert analysis.TRIPLET_PROBABILITY == pytest.approx(math.comb(42,3)/math.comb(45,6))
    assert sum(analysis._count_window(_history(120),30).values()) == 180
    assert sum(analysis._decayed_frequency(_history(120)).values()) == pytest.approx(0,abs=1e-10)


def test_all_score_profiles_are_defined_finite_normalized():
    ranked, _ = analysis._feature_maps(_history(30))
    for method in methods.METHODS:
        assert set(method.weights) <= set(ranked)
        assert all(math.isfinite(v) and v >= 0 for v in method.weights.values())
        scores = analysis._method_number_scores(method,ranked)
        assert all(0 <= v <= 1 for v in scores.values())


def test_disabled_saju_does_not_break_ordinary_recommendations():
    out = analysis.build_analysis(_history(30), [methods.METHOD_WEIGHTED_FREQUENCY], 0,
                                  _profile() | {'birth_time':'bad'})
    assert len(out.recommendations) == 1
    assert not analysis.build_analysis(_history(30), ()).recommendations


def test_manual_regeneration_each_method_changes_and_is_reproducible():
    history = _history(30)
    chosen = (methods.METHOD_MYUNGRI_HETU,methods.METHOD_BAYESIAN_SHRINKAGE)
    old = analysis.build_analysis(history,chosen,0,_profile())
    previous = {r.method_id:r.numbers for r in old.recommendations}
    new = analysis.build_analysis(history,chosen,1,_profile(),previous)
    again = analysis.build_analysis(history,chosen,1,_profile(),previous)
    assert new == again
    for r in new.recommendations:
        assert previous[r.method_id] != r.numbers
        assert 0 <= r.score <= 1


def test_branding_and_safe_data_policy_preserved():
    root = Path(__file__).resolve().parents[1]
    for name in ('logo','icon'):
        data=(root/'custom_components/lotto_645/brand'/f'{name}.png').read_bytes()
        assert data.startswith(b'\x89PNG\r\n\x1a\n')
    constants=(root/'custom_components/lotto_645/const.py').read_text()
    assert 'DEFAULT_ALLOW_OFFICIAL_FALLBACK = False' in constants
    assert 'OFFICIAL_CIRCUIT_BREAKER_SECONDS = 12 * 60 * 60' in constants
