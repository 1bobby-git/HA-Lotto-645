"""Browser checks for read-only research UI, including stale response isolation."""
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / 'custom_components/lotto_645/www/lotto-panel-research.js').read_text()
WHEEL = {
    'target_round': 100, 'tickets': [[1, 5, 10, 15, 20, 25], [1, 5, 10, 15, 35, 45],
                                  [1, 5, 20, 25, 35, 45], [10, 15, 20, 25, 35, 45]],
    'notice': '4게임 전체에만 조건부 보장이 적용됩니다.',
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
    page = browser.new_page(viewport={'width': 360, 'height': 800})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_content('<meta charset="utf-8"><style>body{margin:8px;font-family:sans-serif}</style>')
    page.evaluate('''() => {
      window.calls = []; window.pending = [];
      class TestPanel extends HTMLElement {
        constructor(){super();this.attachShadow({mode:'open'});}
        node(id){return this.shadowRoot.getElementById(id);}
        render(){this.shadowRoot.innerHTML = `<style>:host{display:block;--line:#bbb;--ink:#222;--muted:#555;--surface:white;--field:#888} [hidden]{display:none!important}</style><select id="entry"><option value="one">one</option><option value="two">two</option></select><section id="screen-home"></section>`;}
        disconnectedCallback(){}
        request(type,payload){calls.push({type,payload,entry:this.node('entry').value});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}
      }
      customElements.define('test-panel', TestPanel); window.TestPanel=TestPanel;
    }''')
    page.evaluate(MODULE.replace('export function ', 'function ') + '''
      installResearchTools(TestPanel);
      window.panel=document.createElement('test-panel');document.body.append(panel);panel.render();
    ''')
    box = page.locator('#research-tools')
    assert not box.evaluate('(el)=>el.open')
    box.locator('summary').click()
    field = box.locator('input')
    submit = box.locator('button[type=submit]')
    # 1. Invalid/duplicate input never calls HA.
    field.fill('1 2 3 4 5 6 7 7'); submit.click()
    assert page.evaluate('calls.length') == 0
    assert '중복 없는' in box.locator('[role=status]').inner_text()
    # 2. Valid input returns four visible, unpurchased games.
    field.fill('1, 5, 10, 15, 20, 25, 35, 45'); submit.click()
    assert page.evaluate('calls[0].type') == 'covering_wheel'
    page.evaluate('(result)=>pending.shift().resolve(result)', WHEEL)
    assert box.locator('.research-game').count() == 4
    assert '미구매' in box.locator('[data-research-title]').inner_text()
    assert '저장하지 않았습니다' in box.locator('[role=status]').inner_text()
    # 3. No overflow at mobile width; generated numbers never collapse together.
    assert box.evaluate('(el)=>el.scrollWidth <= el.clientWidth')
    # 4. Changing inputs invalidates previous results and pending responses.
    submit.click(); field.fill('2 5 10 15 20 25 35 45')
    page.evaluate('(result)=>pending.shift().resolve(result)', WHEEL)
    assert box.locator('[data-research-wheel]').is_hidden()
    # 5. Entry changes clear results and ignore responses from the other entry.
    submit.click(); page.locator('#entry').select_option('two')
    page.evaluate('(result)=>pending.shift().resolve(result)', WHEEL)
    assert box.locator('[data-research-wheel]').is_hidden() and field.input_value() == ''
    # 6. Diagnostic is read-only, sample shortage is explicit, errors are accessible.
    box.locator('[data-research-diagnostic]').click()
    page.evaluate("pending.shift().resolve({sample_size:30,p_value:null,notice:'예측에 사용하지 않습니다.'})")
    assert '표본 부족' in box.locator('[data-research-diagnostic-result]').inner_text()
    box.locator('[data-research-diagnostic]').click()
    page.evaluate("pending.shift().reject(new Error('통합을 다시 불러오는 중입니다'))")
    assert '다시 불러오는 중' in box.locator('[role=status]').inner_text()
    assert all(c['type'] in ('covering_wheel', 'research_diagnostics') for c in page.evaluate('calls'))
    assert not errors, errors
    browser.close()
print('6 research browser scenarios passed (mobile, validation, previews, stale input/entry, read-only errors).')
