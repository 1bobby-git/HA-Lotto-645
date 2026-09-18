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
    assert "reviewPresentation(data)" in script
    assert "purchase_match" in text and "match-badge" in text
    assert "generation_matches" in script and "구매번호 일치" in text
    assert 'id="home-wallet-heading"' in text and 'class="draw-stage"' in text


def test_native_formula_entities_expose_purchase_match_marker():
    sensor = (R / 'sensor.py').read_text(encoding='utf-8')
    assert sensor.count('✓구매일치 |') == 2
    assert sensor.count('mdi:ticket-confirmation') >= 2
    assert '"purchase_match": bool(matches)' in sensor
    assert '"purchase_matches": matches' in sensor
