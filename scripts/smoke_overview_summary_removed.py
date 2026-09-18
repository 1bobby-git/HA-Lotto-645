"""Focused browser regression: no overview summary; saved review stays usable."""
import asyncio, json, os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]/'custom_components/lotto_645'
VERSION=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))['version']
PREFIX='/lotto_645_frontend/'+VERSION+'/'
ROW={'method_id':'uniform_floyd','label':'Test formula','numbers':[1,2,3,4,5,6], 'target_round':1242}
DATA={'round':1242,'revision':'','tickets':[],'values':{},'purchased':{'games':[]},'stored_rounds':[],
      'recommendation_target':1242,'recommendations':[ROW],'service_status':'ready',
      'result_round':1241,'draw':{'round':1241,'numbers':[7,13,16,23,24,43],'bonus':9},
      'result_verification':{'status':'official_history'},'winning':None,
      'review_round':{'round':1242,'status':'waiting','methods':[ROW],'peer_count':1},
      'reviews':[{'method_id':'uniform_floyd','label':'Test formula','reviewed_rounds':0}],
      'method_catalog':[{'method_id':'uniform_floyd','name':'Test formula'}]}
async def main():
    async with async_playwright() as pw:
        options={'headless':True}
        if executable:=os.environ.get('LOTTO_BROWSER_EXECUTABLE'):options['executable_path']=executable
        browser=await pw.chromium.launch(**options)
        page=await browser.new_page();page.set_default_timeout(8000)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        async def serve(route):
            path=urlparse(route.request.url).path
            if path=='/':await route.fulfill(content_type='text/html',body='<html><head><style>html,body{height:100%;margin:0}</style></head><body><script type="module" src="'+PREFIX+'lotto-panel-shell.js"></script></body></html>')
            elif path.startswith(PREFIX):
                file=ROOT/'www'/path.removeprefix(PREFIX)
                await route.fulfill(path=str(file),content_type='text/javascript' if file.suffix=='.js' else 'text/plain')
            elif path=='/lotto_645_brand/logo.png':await route.fulfill(path=str(ROOT/'brand/logo.png'))
            else:await route.fulfill(status=404,body='Not found')
        await page.route('**/*',serve)
        for width in (390,1280):
            await page.set_viewport_size({'width':width,'height':900})
            await page.goto('http://127.0.0.1/')
            tag='lotto-ticket-panel-v'+VERSION.replace('.','-')
            await page.wait_for_function('(tag)=>Boolean(customElements.get(tag))',arg=tag)
            await page.evaluate('''({tag,data,narrow})=>{
                window.fixture=data; window.el=document.createElement(tag);document.body.replaceChildren(el);
                el.panel={config:{entries:{test:'Test'}}};el.narrow=narrow;
                el.hass={themes:{darkMode:false},callWS:async()=>structuredClone(fixture)};
            }''',{'tag':tag,'data':DATA,'narrow':width<870})
            await page.wait_for_function('el._walletData && !el._busy')
            assert await page.locator('.recommendation-summary,#current-title,#current-count,#current-meta,#open-current-review').count()==0
            assert await page.locator('#screen-home .draw-stage').is_visible()
            assert await page.locator('#home-wallet-heading').is_visible()
            assert await page.locator('#screen-home .draw-stage + .dashboard-grid').count()==1
            await page.locator('#tab-review').click()
            assert await page.locator('#current-recommendations .prediction-row').count()==1
            assert await page.locator('#current-recommendations .ball').count()==6
            assert await page.locator('#current-recommendations [data-hit]').count()==0
            assert await page.locator('#predictions .prediction-row').count()==1
            assert await page.locator('#predictions .ball').count()==6
            assert await page.locator('#predictions .prize').inner_text()=='추첨 대기'
            await page.evaluate("el.updateResults({...fixture,service_status:'connection_unavailable'})")
            assert await page.locator('#predictions .ball').count()==6
            await page.locator('#tab-home').click()
            assert await page.locator('#screen-home .draw-stage').is_visible()
            assert not errors, errors
        await browser.close()
        print('PASS: mobile/desktop overview summary absent; result card, wallet, review, and live update intact')
if __name__=='__main__':asyncio.run(main())
