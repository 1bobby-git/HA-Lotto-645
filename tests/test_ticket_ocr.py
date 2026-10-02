"""Ticket photo OCR grouping (does not import Home Assistant)."""
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
PACKAGE = 'lotto_ocr_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
ocr = __import__(PACKAGE + '.ticket_ocr', fromlist=['ticket_ocr'])

# The real layout of the 동행복권 "티켓 보기" screen: a serial row, dates, the
# round, five game rows and the price. Only the five game rows may be accepted.
SCREENSHOT_LINES = [
    ['1244', '회'],
    ['발행일', '2026/10/02', '(금)', '10:20:39'],
    ['추첨일', '2026/10/03', '지급기간', '2027/10/04'],
    ['67695', '82934', '21392', '94243', '86960', '57436'],
    ['A', '수동', '10', '13', '15', '31', '34', '43'],
    ['B', '수동', '2', '10', '13', '31', '32', '43'],
    ['C', '수동', '10', '13', '15', '32', '34', '43'],
    ['D', '수동', '10', '13', '15', '31', '43', '44'],
    ['E', '수동', '2', '11', '13', '31', '32', '34'],
    ['함계', '5,000', '원'],
]


def test_only_the_game_rows_are_read_from_a_ticket_screen_photo():
    result = ocr.import_from_lines(SCREENSHOT_LINES)
    assert result['game_count'] == 5
    assert result['values']['game_a'] == '10, 13, 15, 31, 34, 43'
    assert result['values']['game_e'] == '2, 11, 13, 31, 32, 34'
    # The serial row and the price must never become a game.
    assert result['purchase_verified'] is False


def test_the_five_game_rows_do_not_leak_into_a_sixth_slot():
    values = ocr.import_from_lines(SCREENSHOT_LINES)['values']
    assert sorted(values) == ['game_a', 'game_b', 'game_c', 'game_d', 'game_e']


def test_a_line_without_exactly_six_numbers_is_ignored():
    assert ocr.games_from_lines([['10', '13', '15']]) == []
    assert ocr.games_from_lines([['10', '13', '15', '31', '34', '43', '44']]) == []
    assert ocr.games_from_lines([[]]) == []


@pytest.mark.parametrize('line', [
    ['10', '13', '15', '31', '34', '99'],      # out of range
    ['0', '13', '15', '31', '34', '43'],       # zero
    ['10', '13', '15', '31', '34', '10'],      # duplicate
    ['10', '13', '15', '31', '34', '134'],     # not a 1-2 digit token
])
def test_an_impossible_group_is_never_accepted(line):
    assert ocr.games_from_lines([line]) == []


def test_mixed_noise_text_and_numbers_still_yield_the_row():
    assert ocr.games_from_lines([['A', '수동', 'auto', '4', '9', '16', '25', '33', '45']]) == [
        [4, 9, 16, 25, 33, 45]
    ]


def test_a_repeated_row_is_stored_once_but_the_next_game_still_lands():
    games = ocr.games_from_lines([
        ['1', '2', '3', '4', '5', '6'],
        ['1', '2', '3', '4', '5', '6'],
        ['2', '3', '4', '5', '6', '7'],
    ])
    assert games == [[1, 2, 3, 4, 5, 6], [2, 3, 4, 5, 6, 7]]


def test_at_most_five_games_are_read_from_a_slip_with_more_rows():
    lines = [[str(n), str(n + 1), str(n + 2), str(n + 3), str(n + 4), str(n + 5)] for n in range(1, 30, 2)]
    assert len(ocr.games_from_lines(lines)) == 5


def test_the_two_ocr_passes_are_merged_and_a_missed_row_is_appended():
    """The engine's line pass drops the last row; the word pass recovers it."""
    line_pass = [
        ['10', '13', '15', '31', '34', '43'],
        ['2', '10', '13', '31', '32', '43'],
        ['10', '13', '15', '32', '34', '43'],
        ['10', '13', '15', '31', '43', '44'],
    ]
    # Word pass: same four games in a different token order, plus the fifth.
    word_pass = [
        ['43', '34', '31', '15', '13', '10'],
        ['2', '11', '13', '31', '32', '34'],
    ]
    games = ocr.games_from_lines([*line_pass, *word_pass])
    assert len(games) == 5
    assert games[-1] == [2, 11, 13, 31, 32, 34]
    assert ocr.import_from_lines([*line_pass, *word_pass])['values']['game_e'] == '2, 11, 13, 31, 32, 34'


def test_the_line_pass_keeps_its_slot_when_both_passes_read_the_same_game():
    games = ocr.games_from_lines([
        ['10', '13', '15', '31', '34', '43'],
        ['43', '34', '31', '15', '13', '10'],
    ])
    assert games == [[10, 13, 15, 31, 34, 43]]


def test_junk_shapes_are_refused_without_a_crash():
    for payload in (None, 'text', {}, [None], [[None]], [[[1]]], list(range(5000))):
        with pytest.raises(ValueError):
            ocr.import_from_lines(payload)


def test_row_rebuilding_keeps_a_row_the_engine_misgrouped():
    """A dropped row is a silently unregistered game, so rows are rebuilt by y."""
    view = (BASE / 'www/lotto-panel-view.js').read_text(encoding='utf-8')
    assert 'export function rowsFromWords' in view
    assert 'Math.abs(row.bottom-word.bottom)' in view
    core = (BASE / 'www/lotto-panel-core.js').read_text(encoding='utf-8')
    # Line text stays the primary path: a character whitelist collapsed the word
    # spacing and made every row unreadable, so it must not be reintroduced.
    assert 'this._ocrWorker.recognize(canvas);' in core
    assert 'tessedit_char_whitelist' not in core
    # Both passes travel together; a fallback-only path drops the last row again.
    assert 'return [...lines, ...rowsFromWords(words)];' in core


def test_a_partial_read_is_reported_with_what_it_actually_found():
    core = (BASE / 'www/lotto-panel-core.js').read_text(encoding='utf-8')
    assert '읽은 번호:' in core
    # Never imply a partial read is a whole ticket.
    assert 'games<5?' in core
    assert '일부만 읽혔을 수 있으니' in core