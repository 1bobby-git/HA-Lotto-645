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


def test_native_formula_entities_expose_purchase_match_marker():
    sensor = (R / 'sensor.py').read_text(encoding='utf-8')
    assert sensor.count('✓구매일치 |') == 2
    assert sensor.count('mdi:ticket-confirmation') >= 2
    assert '"purchase_match": bool(matches)' in sensor
    assert '"purchase_matches": matches' in sensor
