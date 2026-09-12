"""Synthetic QR payloads only; no real receipt IDs or user purchases."""
import importlib
import pytest
from test_analysis_engine import models
qr=importlib.import_module('custom_components.lotto_645.ticket_qr')

BASE='https://m.dhlottery.co.kr/qr.do?method=winQr&v='

@pytest.mark.parametrize('mode', ['q','m','s'])
@pytest.mark.parametrize('count', [1,2,3,4,5])
def test_valid_five_games_and_discarded_receipt(mode,count):
    value=BASE+'1241'+(mode+'010715243345')*count+'0000000000'
    r=qr.parse_ticket_qr(value)
    assert r['round']==1241 and r['game_count']==count
    assert r['values']['game_a']=='1, 7, 15, 24, 33, 45'
    assert '0000000000' not in str(r)
    assert r['purchase_verified'] is False


def test_legacy_url_and_one_digit_numbers_zero_padded():
    r=qr.parse_ticket_qr('http://qr.645lotto.net/?v=0809q010203040506')
    assert r['round']==809
    assert r['values']=={'game_a':'1, 2, 3, 4, 5, 6'}

@pytest.mark.parametrize('value',[
    BASE+'1241q0102030405',BASE+'0000q010203040506',BASE+'1241q010203040546',
    BASE+'1241q010103040506',BASE+'1241q010203040506'*6,
    BASE+'1241'+('q010203040506')*6, BASE+'1241x010203040506',
    BASE+'1241q010203040506123',BASE+'1241q010203040506&v=1240q010203040506',
    'http://127.0.0.1/?v=1241q010203040506',
    'https://m.dhlottery.co.kr.evil/qr.do?v=1241q010203040506',
    'https://user:password@m.dhlottery.co.kr/qr.do?v=1241q010203040506',
    'https://m.dhlottery.co.kr:8080/qr.do?v=1241q010203040506',
    BASE+'1241q010203040506#x',BASE+'1241q010203040506&next=http://127.0.0.1',
    'javascript:alert(1)','',None,
])
def test_untrusted_malformed_ambiguous_rejected(value):
    with pytest.raises(ValueError):qr.parse_ticket_qr(value)

@pytest.mark.parametrize('receipt', ['', '0'*10, '0'*18])
def test_official_qr_host_empty_slots_and_receipt_lengths(receipt):
    value='https://qr.dhlottery.co.kr/?v=1241q010715243345n000000000000m020816253444n000000000000n000000000000'+receipt
    result=qr.parse_ticket_qr(value)
    assert result['game_count']==2
    assert set(result['values'])=={'game_a','game_c'}
    assert result['values']['game_c']=='2, 8, 16, 25, 34, 44'
    assert 'receipt' not in result

@pytest.mark.parametrize('payload',['1241n000000000000','1241q010715243345n010203040506','1241q010715243345'+'0'*17])
def test_empty_slot_is_not_a_ticket_or_an_arbitrary_suffix(payload):
    with pytest.raises(ValueError):qr.parse_ticket_qr('https://qr.dhlottery.co.kr/?v='+payload)
