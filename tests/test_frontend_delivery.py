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
def test_overview_has_link_not_a_second_number_list():
    text=(R/'www/lotto-panel-view.js').read_text(encoding='utf-8')
    assert 'id="current-recommendations"' not in text
    assert 'id="open-current-review"' in text
    assert 'id="predictions"' in text
    assert 'data-go="review"' in text
    script=(R/'www/lotto-panel-core.js').read_text(encoding='utf-8')
    assert "this.node('current-recommendations')" not in script
    assert "reviewPresentation(data)" in script
