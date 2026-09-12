"""Source-table and independent calendar anchors; no winning-probability claim."""
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from copy import deepcopy
import importlib

import pytest
from test_analysis_engine import myungri, _profile

rules = importlib.import_module('custom_components.lotto_645.saju_rules')
cal = importlib.import_module('custom_components.lotto_645.saju_calendar')

# Transcribed from uploaded prompt §1.2.4, not computed by the function tested.
GOD_ROWS = [
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
]

@pytest.mark.parametrize('row', range(10))
def test_all_ten_god_table_rows(row):
    assert [rules.ten_god(rules.STEMS[row], other) for other in rules.STEMS] == GOD_ROWS[row].split()

@pytest.mark.parametrize('branch', rules.BRANCHES)
def test_hidden_mass_is_one_and_named(branch):
    assert sum(rules.HIDDEN[branch].values()) == pytest.approx(1)
    assert set(rules.HIDDEN[branch]) <= set(rules.STEMS)

def test_prompt_school_difference_is_explicit():
    assert rules.HIDDEN['亥'] == {'戊': .23, '甲': .17, '壬': .60}
    assert '戊' in rules.pillar_record('丁亥', '甲')['hidden_stem_rule']

def test_kasi_2000_almanac_anchor_and_terms():
    seoul = ZoneInfo('Asia/Seoul')
    # KASI 2000 almanac: Jan1 戊午; LiChun Feb4 21:40 Korean standard time.
    assert cal.pillars_at(datetime(2000,1,1,12,tzinfo=seoul))['day']['ganzhi'] == '戊午'
    assert cal.year_month(datetime(2000,2,4,21,39,tzinfo=seoul)) == ('己卯', '丁丑')
    assert cal.year_month(datetime(2000,2,4,21,41,tzinfo=seoul)) == ('庚辰', '戊寅')

@pytest.mark.parametrize('year,expected', [(1900,'甲戌'),(2000,'戊午'),(2020,'癸卯'),(2025,'庚午'),(2026,'乙亥')])
def test_day_anchor_regression_against_lunar_and_korean(year, expected):
    from lunar_python import Solar
    from korean_lunar_calendar import KoreanLunarCalendar
    actual = cal.pillars_at(datetime(year,1,1,12,tzinfo=ZoneInfo('Asia/Seoul')))['day']['ganzhi']
    assert actual == expected
    assert Solar.fromYmd(year,1,1).getLunar().getDayInGanZhiExact2() == expected
    kc = KoreanLunarCalendar(); assert kc.setSolarDate(year,1,1)
    assert expected + '日' in kc.getChineseGapJaString()

def test_late_zi_uses_same_day_hour_stem_as_prompt():
    at23 = cal.pillars_at(datetime(2000,1,1,23,30,tzinfo=ZoneInfo('Asia/Seoul')))
    assert at23['day']['ganzhi'] == '戊午'
    assert at23['time']['ganzhi'] == '壬子'  # §1.2.8 戊日子時
    next_day = cal.pillars_at(datetime(2000,1,2,0,30,tzinfo=ZoneInfo('Asia/Seoul')))
    assert next_day['day']['ganzhi'] == '己未'
    assert next_day['time']['ganzhi'] == '甲子'

def test_lunar_february30_and_invalid_leap():
    p = _profile(); p.update(calendar='lunar', birth_date='2000-02-30', lunar_standard='korean')
    birth, _, _ = cal.resolve_birth(p)
    assert birth.date() == date(2000,4,4) # KASI month2 starts Mar6 and has30days
    p.update(birth_date='2000-02-01', lunar_leap_month=True)
    with pytest.raises(ValueError): cal.resolve_birth(p)

@pytest.mark.parametrize('key,value', [('birth_date','2001-02-30'),('birth_date','2000-01-01junk'),('birth_time','12:00junk'),('birth_time','24:00'),('longitude','nan'),('longitude','inf'),('timezone','invalid'),('calendar','other')])
def test_bad_profiles_rejected(key,value):
    p=_profile();p[key]=value
    with pytest.raises(ValueError): myungri.validate_saju_profile(p)

def test_dst_gap_and_fold_rejected():
    for month, day, hour in ((3,10,2),(11,3,1)):
        with pytest.raises(ValueError):
            cal.localize(datetime(2024,month,day,hour,30),ZoneInfo('America/New_York'))

def test_year_month_is_based_on_absolute_instant_not_timezone_label():
    instant=datetime(2000,2,4,21,39,tzinfo=ZoneInfo('Asia/Seoul'))
    assert cal.year_month(instant) == cal.year_month(instant.astimezone(ZoneInfo('America/New_York')))
    a = cal.pillars_at(instant)
    b = cal.pillars_at(instant + timedelta(minutes=2))
    assert a['year']['ganzhi'] != b['year']['ganzhi']

def test_unknown_time_does_not_fabricate_pillar():
    p=_profile();p['birth_time']='미상'
    c=myungri.build_myungri_context('2026-09-05',p)
    assert set(c['natal_pillars']) == {'year','month','day'}
    assert c['profile']['birth_time_known'] is False
    assert '12:00' not in c['profile']['birth_solar']

def test_no_today_fallback_for_missing_draw():
    with pytest.raises(ValueError): myungri.build_myungri_context('',_profile())

def test_structure_pattern_luck_and_scores_are_inspectable():
    c=myungri.build_myungri_context('2026-09-05',_profile())
    st=c['structural_analysis']
    assert sum(st['balance'].values()) == pytest.approx(1)
    assert sum(st['visible_counts'].values()) == 8
    assert sum(st['strength_weights'].values()) == pytest.approx(1)
    assert st['pattern']['certainty']=='후보'
    assert {i['principle'] for i in c['favorable_analysis']['evidence']} >= {'억부','조후','통관','병약'}
    assert set(c['luck_layers']) == {'대운','세운','월운','일운','시운'}
    assert len(c['luck_cycle']['timeline']) == 12
    assert sum(c['number_score_weights'].values()) == pytest.approx(1)
    for n,tr in c['number_score_trace'].items():
        assert tr['ten_god'] in rules.GODS
        assert c['number_resonance'][n] == pytest.approx(sum(tr['parts'][k]*w for k,w in c['number_score_weights'].items()))
    details=myungri.combo_myungri_details((1,2,3,4,5,6),c)
    assert 'birth_profile' not in details
    assert _profile()['birth_date'] not in str(details)

def test_interaction_recognition_not_unconditional_transformation():
    p={'a': rules.pillar_record('甲辰','甲'), 'b':rules.pillar_record('己巳','甲'), 'c':rules.pillar_record('庚辰','甲')}
    events=rules.interactions(p)
    assert {'천간합','자형'} <= {e['type'] for e in events}
    assert not any(e['transformation_confirmed'] for e in events)
    assert not rules.interactions({'a':p['a']})
    natal={str(i):rules.pillar_record(v,'甲') for i,v in enumerate(('甲申','甲子','甲辰'))}
    assert '삼합' in {e['type'] for e in rules.interactions(natal)}
    incoming={'x':rules.pillar_record('乙卯','甲')}
    assert '삼합' not in {e['type'] for e in rules.interactions(natal,incoming)}

def test_interactions_change_actual_number_scores(monkeypatch):
    baseline=myungri.build_myungri_context('2026-09-05',_profile())
    monkeypatch.setattr(myungri,'interactions',lambda *args: [])
    without=myungri.build_myungri_context('2026-09-05',_profile())
    assert baseline['number_resonance'] != without['number_resonance']

def test_daeun_direction_and_boundary():
    p=_profile();c=myungri.build_myungri_context('2026-09-05',p)
    cycle=c['luck_cycle'];assert cycle['direction']=='순행' # 1990 庚 male
    birth,effective,meta=cal.resolve_birth(p);natal=cal.pillars_at(birth,effective)
    start=datetime.fromisoformat(cycle['timeline'][2]['start'])
    assert cal.luck_cycles(birth,natal,'male',start,True)['current']['ganzhi']==cycle['timeline'][2]['ganzhi']
    assert cal.luck_cycles(birth,natal,'male',start-timedelta(seconds=1),True)['current']['ganzhi']==cycle['timeline'][1]['ganzhi']
    assert cal.luck_cycles(birth,natal,'female',start,True)['direction']=='역행'


def test_source_branch_table_conflict_is_preserved_not_silently_reconciled():
    record=rules.pillar_record('戊午','甲')
    assert record['prompt_branch_ten_god']=='식신'
    assert record['hidden_main_ten_god']=='상관'
    assert '지장간' in record['branch_ten_god_policy']
