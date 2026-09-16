"""Render actual selected-only response projection; no live HA modifications."""
import asyncio,json,os,sys
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_selected_review_visibility import owner_for,render,SELECTED,AI_METHOD_ID
C=ROOT/'custom_components/lotto_645'
VERSION=json.loads((C/'manifest.json').read_text(encoding='utf-8'))['version']
PREFIX='/lotto_645_frontend/'+VERSION+'/'

def payload(owner):
    data=render(owner)
    data['method_catalog']=[{'method_id':k,'name':k} for k in (*SELECTED,AI_METHOD_ID)]
    return data

async def main():
    async with async_playwright() as pw:
        opts={'headless':True}
        if path:=os.environ.get('LOTTO_BROWSER_EXECUTABLE'):opts['executable_path']=path
        browser=await pw.chromium.launch(**opts)
        page=await browser.new_page();page.set_default_timeout(8000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        async def serve(route):
            path=urlparse(route.request.url).path
            if path=='/':
                await route.fulfill(content_type='text/html',body='<html><head><style>html,body{height:100%;margin:0}</style></head><body><script type="module" src="'+PREFIX+'lotto-panel-shell.js"></script></body></html>')
            elif path.startswith(PREFIX):
                file=C/'www'/path.removeprefix(PREFIX)
                await route.fulfill(path=str(file),content_type='text/javascript' if file.suffix=='.js' else 'text/plain')
            elif path=='/lotto_645_brand/logo.png':await route.fulfill(path=str(C/'brand/logo.png'))
            else:await route.fulfill(status=404,body='Not found')
        await page.route('**/*',serve)
        for width in (390,1280):
            owner,ledger=owner_for();initial=payload(owner)
            await page.set_viewport_size({'width':width,'height':900})
            await page.goto('http://127.0.0.1/')
            tag='lotto-ticket-panel-v'+VERSION.replace('.','-')
            await page.wait_for_function('(tag)=>Boolean(customElements.get(tag))',arg=tag)
            await page.evaluate('''({tag,data,narrow})=>{
                window.fixture=data;window.el=document.createElement(tag);document.body.replaceChildren(el);
                el.panel={config:{entries:{test:'Test'}}};el.narrow=narrow;
                el.hass={themes:{darkMode:false},callWS:async()=>structuredClone(fixture)};
            }''',{'tag':tag,'data':initial,'narrow':width<870})
            await page.wait_for_function('el._walletData && !el._busy')
            await page.locator('#tab-review').click()
            for selector in ('#predictions','#reviews'):
                actual=await page.locator(selector+' .method-info-trigger').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.methodId)')
                assert actual==[*SELECTED,AI_METHOD_ID],actual
            assert await page.locator('#method-count').inner_text()=='11개 공식'
            assert await page.locator('#predictions .prize').all_inner_texts()==['추첨 대기']*11
            assert 'personal_lucky' not in await page.locator('#screen-review').inner_text()
            assert await page.locator('.recommendation-summary').count()==0
            owner.configured_method_ids=SELECTED[:2];owner.ai_enabled=False
            await page.evaluate('(data)=>{window.fixture=data;el.updateResults(data)}',payload(owner))
            assert await page.locator('#predictions .prediction-row').count()==2
            assert await page.locator('#reviews .method-info-trigger').count()==2
            assert await page.locator('#method-count').inner_text()=='2개 공식'
            assert len(ledger['methods'])==23
            owner.configured_method_ids=SELECTED;owner.ai_enabled=True
            await page.evaluate('(data)=>{window.fixture=data;el.updateResults(data)}',payload(owner))
            assert await page.locator('#predictions .prediction-row').count()==11
            assert await page.locator('#method-count').inner_text()=='11개 공식'
            assert not errors,errors
        await browser.close()
        print('PASS: selected 10 + enabled AI only; counts/tables agree; deselect/reselect and AI-off update without erasing 23 stored records')
if __name__=='__main__':asyncio.run(main())
