"""Real-browser read-only portfolio tests at desktop and small screen sizes."""
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / 'custom_components/lotto_645/www/lotto-panel-portfolio.js').read_text()
RESULT = {'target_round':100,'tickets':[[1,2,3,4,5,6],[1,2,3,7,8,9],[4,5,6,7,8,9]],
          'ticket_count':3,'candidate_count':9,'number_coverage':9,'pair_coverage':36,
          'triple_coverage':57,'maximum_overlap':3,'verification_complete':True,
          'verification_cases':465,'conditional_min_match':{'4':3,'6':4},
          'saved_rules_applied':True,'notice':'후보 적중·1등을 보장하지 않습니다.'}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=shutil.which('chromium'))
    page = browser.new_page(viewport={'width':360,'height':800})
    errors=[]; page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content('<meta charset="utf-8"><style>body{margin:8px;font-family:sans-serif}</style>')
    page.evaluate('''() => {
      window.calls=[];window.pending=[];
      class TestPanel extends HTMLElement {
        constructor(){super();this.attachShadow({mode:'open'});}
        node(id){return this.shadowRoot.getElementById(id);}
        render(){this.shadowRoot.innerHTML='<style>:host{display:block}</style><select id="entry"><option value="one">one</option><option value="two">two</option></select><section id="screen-home"></section>';}
        disconnectedCallback(){}
        request(type,payload){calls.push({type,payload,entry:this.node('entry').value});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}
      }
      customElements.define('test-panel',TestPanel);window.TestPanel=TestPanel;
    }''')
    page.evaluate(MODULE.replace('export function ','function ')+'''
      installPortfolioTools(TestPanel);window.panel=document.createElement('test-panel');document.body.append(panel);panel.render();
    ''')
    box=page.locator('#portfolio-tools');box.locator('summary').click()
    field=box.locator('#portfolio-candidates');button=box.locator('button[type=submit]')
    status=box.locator('[role=status]');output=box.locator('[data-portfolio-result]')
    field.fill('1 2 3 4 5 5');button.click()
    assert page.evaluate('calls.length')==0 and '중복 없는' in status.inner_text()
    field.fill('1 2 3 4 5 6 7 8 9');box.locator('#portfolio-mode').select_option('wheel9');button.click()
    assert page.evaluate('calls.length')==0 and '3개' in status.inner_text()
    box.locator('#portfolio-count').select_option('3');button.click()
    assert page.evaluate('calls[0].type')=='portfolio_coverage'
    assert page.evaluate('calls[0].payload.apply_rules') is True
    assert button.is_disabled() and box.get_attribute('aria-busy')=='true'
    page.evaluate('(r)=>pending.shift().resolve(r)',RESULT)
    assert box.locator('.portfolio-game').count()==3 and output.is_visible()
    assert '미구매' in box.locator('[data-portfolio-title]').inner_text()
    assert '본번호 4개 포함 → 한 게임 이상 최소 3개 일치' in box.locator('[data-portfolio-bound]').inner_text()
    for width in (320,360,1280):
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert box.evaluate('(el)=>el.scrollWidth <= el.clientWidth + 1')
    # Invalid stale results cannot be attached after inputs change.
    button.click();field.fill('1 2 3 4 5 6 7 8 10')
    page.evaluate('(r)=>pending.shift().resolve(r)',RESULT)
    assert output.is_hidden()
    # Entry changes isolate input and output.
    button.click();page.locator('#entry').select_option('two')
    page.evaluate('(r)=>pending.shift().resolve(r)',RESULT)
    assert output.is_hidden() and field.input_value()==''
    field.fill('1 2 3 4 5 6 7 8 9');box.locator('#portfolio-rules').uncheck();button.click()
    assert page.evaluate('calls.at(-1).payload.apply_rules') is False
    page.evaluate("pending.shift().reject({message:'조건을 지키는 조합을 찾지 못했습니다.'})")
    assert '조건을 지키는' in status.inner_text() and output.is_hidden() and button.is_enabled()
    # Unverified status is explicit, then malformed budget is rejected.
    button.click();page.evaluate('(r)=>pending.shift().resolve(r)',{**RESULT,'saved_rules_applied':False,'verification_complete':False,'conditional_min_match':{}})
    assert '전수 검증하지 않았습니다' in box.locator('[data-portfolio-bound]').inner_text()
    assert '저장 조건 미적용' in box.locator('[data-portfolio-notice]').inner_text()
    button.click();page.evaluate('(r)=>pending.shift().resolve(r)',{**RESULT,'tickets':RESULT['tickets'][:2]})
    assert output.is_hidden() and '요청한 게임 수' in status.inner_text()
    assert all(c['type']=='portfolio_coverage' for c in page.evaluate('calls'))
    button.click();page.evaluate('panel.remove()');page.evaluate('(r)=>pending.shift().resolve(r)',RESULT)
    assert not errors,errors
    browser.close()
print('9 portfolio browser scenarios passed: input, explicit budget, render, 320/360/1280 layout, stale inputs, entry isolation, errors, verification, disconnect.')
