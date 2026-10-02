"""Release paths and user-facing recommendation placement."""
from pathlib import Path
import ast,json,re
R=Path(__file__).resolve().parents[1]/'custom_components/lotto_645'
def test_release_has_isolated_resource_path_and_matching_element():
    v=json.loads((R/'manifest.json').read_text(encoding='utf-8'))['version']
    backend=(R/'ticket_panel.py').read_text(encoding='utf-8')
    assert "FRONTEND_PATH = f'/lotto_645_frontend/{VERSION}'" in backend
    assert "f'{FRONTEND_PATH}/lotto-panel-shell.js'" in backend
    assert 'StaticPathConfig(FRONTEND_PATH, str(WWW), False)' in backend
    assert 'lotto-ticket-panel-v'+v.replace('.','-') in backend
    for name in ['lotto-panel-shell.js','lotto-panel.js','lotto-panel-core.js','lotto-panel-tools.js']:
        text=(R/'www'/name).read_text(encoding='utf-8')
        for found in re.findall(r'\.js\?v=([0-9.]+)',text):assert found==v
        for found in re.findall(r'lotto-(?:ticket-panel|panel-tools)-v([0-9-]+)',text):assert found==v.replace('.','-')
def test_overview_has_no_recommendation_summary():
    text=(R/'www/lotto-panel-view.js').read_text(encoding='utf-8')
    home=text.split('id="screen-home"',1)[1].split('id="screen-wallet"',1)[0]
    assert 'id="current-recommendations"' not in home
    assert 'id="current-recommendations"' in text.split('id="screen-review"',1)[1]
    for obsolete in ('recommendation-summary','current-title','current-count','current-meta','open-current-review'):
        assert obsolete not in text
    assert 'id="predictions"' in text
    assert 'data-go="review"' in text
    script=(R/'www/lotto-panel-core.js').read_text(encoding='utf-8')
    assert 'currentRecommendations(data)' in script
    for obsolete in ('current-title','current-count','current-meta','open-current-review'):
        assert obsolete not in script
    assert "lastReviewPresentation(data)" in script
    assert "match-badge" in text and "적용 공식" in text
    assert "generation_matches" in script and "formula_links" in text
    assert "purchase_formula_reviews" not in text
    assert 'id="home-wallet-heading"' in text and 'class="draw-stage last-draw"' in text
    assert 'id="upcoming-countdown"' in text
    assert 'class="import-promo"' in home and 'MY LOTTO' in home and 'QR로 가져오기' in home
    assert 'id="hero-ticket-summary"' in home and 'id="hero-ticket-items"' in home
    assert 'home-purchase-status' not in home
    assert 'heroTicketSummary.hidden=false' in script and '등록 복권' in script


def test_home_wallet_renders_five_games_and_multiple_tickets_as_swiper():
    view = (R / 'www/lotto-panel-view.js').read_text(encoding='utf-8')
    core = (R / 'www/lotto-panel-core.js').read_text(encoding='utf-8')
    backend = (R / 'ticket_panel.py').read_text(encoding='utf-8')
    assert 'id="mini-swiper-track"' in view
    assert 'id="mini-swiper-nav"' in view
    assert 'scroll-snap-type:x mandatory' in view
    assert "ticket_previews" in backend
    assert "renderMiniWallet(data)" in core
    assert "ticketRows(list,ticket.games||[],Infinity,matches)" in core
    assert "games,3" not in core
    assert "games.length>3" not in core


def test_every_field_the_panel_sends_is_declared_by_the_command_schema():
    """The page mirrors the editor request; a missing field is a hard error."""
    import re
    backend = (R / 'ticket_panel.py').read_text(encoding='utf-8')
    core = (R / 'www/lotto-panel-core.js').read_text(encoding='utf-8')

    def declared(command):
        start = backend.index(f"'type': 'lotto_645/{command}'")
        block = backend[start:backend.index('})', start)]
        return set(re.findall(r"vol\.(?:Required|Optional)\('([a-z_]+)'", block))

    for command, request in (('purchases_save', "request('purchases_save'"),
                             ('purchases_import_ocr', "request('purchases_import_ocr'")):
        start = core.index(request)
        call = core[start:core.index('});', start)]
        sent = set(re.findall(r'[{,](\w+):', call.split('){', 1)[-1]))
        missing = {field for field in sent if field != 'entry_id'} - declared(command)
        assert not missing, f'{command} schema does not accept {sorted(missing)}'


def test_the_offline_ocr_assets_are_shipped_and_pinned():
    import hashlib
    import json
    ocr = R / 'www' / 'ocr'
    for name in ('tesseract.min.js', 'worker.min.js', 'tesseract-core-lstm.wasm.js',
                 'tesseract-core-lstm.wasm', 'eng.traineddata.gz'):
        asset = ocr / name
        assert asset.exists() and asset.stat().st_size > 1000, f'missing OCR asset: {name}'
    pin = json.loads((R / 'www' / 'ocr-decoder-pin.json').read_text(encoding='utf-8'))
    assert set(pin['files']) == {'eng.traineddata.gz', 'tesseract-core-lstm.wasm',
                                 'tesseract-core-lstm.wasm.js', 'tesseract.min.js', 'worker.min.js'}
    for name, meta in pin['files'].items():
        data = (ocr / name).read_bytes()
        assert len(data) == meta['bytes'], f'{name} size drifted from its pin'
        assert hashlib.sha256(data).hexdigest() == meta['sha256'], f'{name} is not the pinned build'


def test_photo_import_falls_back_to_ocr_and_sends_lines_to_the_server():
    view = (R / 'www/lotto-panel-view.js').read_text(encoding='utf-8')
    core = (R / 'www/lotto-panel-core.js').read_text(encoding='utf-8')
    backend = (R / 'ticket_panel.py').read_text(encoding='utf-8')
    # QR stays the first path; OCR only runs when no QR was decoded.
    assert "if(value){await this.preview(value);return;}" in core
    assert 'this.ocrLines(im)' in core
    assert "request('purchases_import_ocr'" in core
    # The engine is bundled and loaded on demand, never from a CDN.
    assert 'tesseract.min.js' in core and 'cdn' not in core.split('loadOcrEngine')[1][:600]
    assert 'worker.min.js' in core and 'tesseract-core-lstm.wasm.js' in core
    # Reading must stay on the proven line-text path (a character whitelist
    # collapsed the word spacing and made every row unreadable).
    # Server-side validation, then the same save path the editor uses.
    assert "'type': 'lotto_645/purchases_import_ocr'" in backend
    assert 'import_from_lines' in backend
    assert 'async_save_purchase_record' in backend
    assert 'purchases_import_ocr' in backend[backend.index('for handler in ('):][:400]
    assert 'QR이 없는 온라인 구매 화면도 읽어요' in view


def test_native_formula_entities_expose_purchase_match_marker():
    sensor = (R / 'sensor.py').read_text(encoding='utf-8')
    entities = (R / 'game_entities.py').read_text(encoding='utf-8')
    assert sensor.count('✓구매일치 |') + entities.count('✓구매일치 |') == 2
    assert sensor.count('mdi:ticket-confirmation') >= 2
    assert '"purchase_match": bool(matches)' in sensor
    assert '"purchase_matches": matches' in sensor


def test_the_formula_badge_names_the_game_it_came_from():
    view = (R / 'www/lotto-panel-view.js').read_text(encoding='utf-8')
    core = (R / 'www/lotto-panel-core.js').read_text(encoding='utf-8')
    assert 'export function formulaLinkLabels' in view
    assert '${link.formula_game}번 ${name}' in view
    assert 'formulaLinkLabels(linked)' in view
    assert 'formulaLinkLabels(game.formula_links)' in core
    assert 'formulaLinkLabels' in core.split('\n')[2]
