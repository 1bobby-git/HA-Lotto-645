"""Printed Lotto 6/45 slip contract for registered wallet tickets (no browser required)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components/lotto_645'
WWW = COMPONENT / 'www'
VIEW = (WWW / 'lotto-panel-view.js').read_text(encoding='utf-8')
CORE = (WWW / 'lotto-panel-core.js').read_text(encoding='utf-8')
SHELL = (WWW / 'lotto-panel-shell.js').read_text(encoding='utf-8')
NUMBER_SELECTOR = '.ticket-receipt .receipt-sheet .receipt-lines .ticket-row .ticket-balls.result-balls .ball[data-band]'


def specificity(selector: str) -> int:
    """Class/attribute/pseudo-class count; :host(<compound>) adds its argument."""
    return selector.count('.') + selector.count('[') + selector.count(':host(')


def test_wallet_slip_has_printed_ticket_structure():
    for token in ('.receipt-sheet{', '.receipt-sheet::before{', '.receipt-ribbon{', '.receipt-watermark{',
                  '--receipt-stage:#a9d6cf', 'radial-gradient(circle at 50% 0,var(--receipt-stage)',
                  'box-shadow:var(--receipt-drop) var(--receipt-drop) 0 var(--receipt-stage-shadow)'):
        assert token in VIEW, token
    assert "createReceiptSheet(top,list,receiptLegend(list),createReceiptTotal(round,ticket,index))" in CORE
    assert "ticketRows(list,ticket.games||[],Infinity,matches,true);decorateReceiptRows(list);" in CORE
    for label in ("'등록일'", "'추첨일'", "'게임수'", "'금액'", '보관용 표시'):
        assert label in CORE, label


def test_slip_numbers_outrank_every_shell_ball_palette_rule():
    rule = re.search(re.escape(NUMBER_SELECTOR) + r'\{([^}]+)\}', VIEW)
    assert rule, NUMBER_SELECTOR
    for declaration in ('background:transparent!important', 'color:var(--receipt-ink)!important',
                        'outline:none!important', 'text-shadow:none!important'):
        assert declaration in rule.group(1), declaration
    palette = SHELL.split('const LOTTO_BALL_AND_COUNTDOWN_STYLE = `', 1)[1].split('`;', 1)[0]
    palette = palette.split('@media', 1)[0]
    shell_selectors = [part.strip() for block in re.findall(r'([^{}]+)\{', palette)
                       for part in block.split(',') if '.ball' in part]
    assert any(':host([data-theme="dark"])' in s for s in shell_selectors)
    strongest = max(map(specificity, shell_selectors))
    assert specificity(NUMBER_SELECTOR) > strongest, (specificity(NUMBER_SELECTOR), strongest)


def test_slip_draw_date_matches_backend_rule_and_art_is_decorative():
    backend = (COMPONENT / 'published_results.py').read_text(encoding='utf-8')
    assert 'FIRST_DRAW = date(2002, 12, 7)' in backend
    assert 'timedelta(weeks=round_no - 1)' in backend
    assert 'const FIRST_DRAW_UTC=Date.UTC(2002,11,7);' in CORE
    assert '(round-1)*7*86400000' in CORE
    for helper in ('receiptQr(receiptSeed(', 'receiptBarcode(receiptSeed('):
        assert helper in CORE, helper
    assert CORE.count("setAttribute('aria-hidden','true')") >= 4


def test_scan_icon_path_is_well_formed():
    assert 'a1 1 0 0 0 1-1-1v-4' not in VIEW
    assert 'h4a1 1 0 0 0 1-1v-4M3 12h18' in VIEW
