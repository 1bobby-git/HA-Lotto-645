"""Real ES-module and bundled jsQR browser smoke, using isolated HA fixtures."""
from __future__ import annotations

import asyncio
import hashlib
import struct
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import qrcode
from playwright.async_api import async_playwright
from smoke_panel_safe_area import verify_safe_area
from smoke_panel_design_system import verify_component_design
from smoke_panel_tools import verify_panel_tools

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'custom_components/lotto_645/www'
QR = 'https://qr.dhlottery.co.kr/?v=1241q010715243345n000000000000n000000000000n000000000000n000000000000000000000000000000'


async def run():
    logo = ROOT / 'custom_components/lotto_645/brand/logo.png'
    content = logo.read_bytes()
    assert hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest() == '63e5458355b4308068db08a0d02a1d5f06c7bb3b'
    assert content[:8] == b'\x89PNG\r\n\x1a\n' and content[12:16] == b'IHDR'
    logo_size = struct.unpack('>II', content[16:24])
    assert logo_size[0] > logo_size[1] > 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            **({'executable_path': '/usr/bin/chromium'} if Path('/usr/bin/chromium').exists() else {}),
            args=['--no-sandbox'],
        )
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
        errors = []
        assets = set()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog: dialog.accept())
        resources = {f'/lotto_645_static/{name}': WWW / name for name in (
            'jsQR.js', 'lotto-panel-shell.js', 'lotto-panel.js', 'lotto-panel-core.js', 'lotto-panel-view.js', 'lotto-panel-design.js', 'lotto-panel-tools.js'
        )}
        resources['/lotto_645_brand/logo.png'] = logo

        async def serve(route):
            url = urlparse(route.request.url)
            assert url.hostname == 'lotto.test', f'Unexpected external request: {url.hostname}'
            if url.path == '/':
                await route.fulfill(content_type='text/html', body='''<!doctype html><html lang="ko"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{height:100%;margin:0}</style><script type="module" src="/lotto_645_static/lotto-panel-shell.js"></script></head><body></body></html>''')
            elif url.path in resources:
                assets.add(url.path)
                await route.fulfill(path=str(resources[url.path]), content_type='image/png' if url.path.endswith('.png') else 'text/javascript')
            else:
                await route.fulfill(status=404, body='Not found')

        await page.route('**/*', serve)
        await page.goto('http://lotto.test/')
        await page.wait_for_function("Boolean(customElements.get('lotto-ticket-panel'))")
        await page.evaluate('(size)=>window.expectedLogoSize=size', list(logo_size))
        await page.evaluate("""() => {
            window.requests=[];window.saved={};window.revision='';
            window.el=document.createElement('lotto-ticket-panel');document.body.replaceChildren(el);
            el.panel={config:{entries:{test:'테스트 로또'}}};
            el.hass={themes:{darkMode:false},callWS:async msg=>{
                requests.push(structuredClone(msg));
                if(msg.type==='lotto_645/qr_preview'){
                    if(msg.qr!==window.expectedQR)throw Error('decoded QR differs');
                    return {round:1241,game_count:1,values:{game_a:'1, 7, 15, 24, 33, 45'},revision:'',will_replace:false};
                }
                if(msg.type==='lotto_645/purchases_save'){saved=msg.values;revision='saved-1';}
                return {round:msg.round||1241,revision,values:saved,stored_rounds:revision?[1241]:[],purchased:{games:Object.entries(saved).filter(([,v])=>v.trim()).map(([k,v])=>({slot:k.at(-1).toUpperCase(),numbers:v.split(', ').map(Number),prize:'추첨 대기'}))},draw:{numbers:[11,13,19,20,31,44],bonus:27},result_round:1240,result_verification:{status:'official_history'},winning:null,recommendation_target:1241};
            }};
        }""")
        await page.evaluate('(qr)=>window.expectedQR=qr', QR)
        await page.wait_for_function('el._walletData && !el._busy')
        await page.wait_for_function("el.node('brand').complete && el.node('brand').naturalWidth===expectedLogoSize[0] && el.node('brand').naturalHeight===expectedLogoSize[1]")
        assert await page.locator('.ha-component-title').count() == 0
        assert await page.locator('.ha-host-title').text_content() == 'Lotto 6/45 Analysis'
        assert await page.locator('.ha-host-header').evaluate("n=>getComputedStyle(n).display==='none'")
        await page.evaluate('el.narrow=true')
        assert await page.locator('.ha-host-header').evaluate("n=>getComputedStyle(n).display==='flex'")
        await page.evaluate('el.narrow=false')
        assert await page.locator('.ha-host-header').evaluate("n=>getComputedStyle(n).display==='none'")
        assert await page.locator('#drawtitle').text_content() == '제 1,240회'
        assert await page.locator('#numbers .ball').count() == 7
        assert resources.keys() <= assets
        assert await page.locator('.draw-stage').evaluate("n=>getComputedStyle(n).backgroundColor==='rgb(255, 255, 255)' && getComputedStyle(n).backgroundImage==='none'")

        assert await page.evaluate('el._poll===null')
        assert '30초마다' not in await page.locator('#sync-status').text_content()
        assert '공식 결과 확인 완료' in await page.locator('#sync-status').text_content()
        policies = await page.evaluate("""() => ({
            weekday: el._smartSyncPolicy(Date.UTC(2026,8,14,0,0,0)).mode,
            drawWindow: el._smartSyncPolicy(Date.UTC(2026,8,12,12,0,0)).mode,
            settled: (() => {
                const state=[el._panelResultStatus,el._panelResultRound,el._targetRound];
                el._panelResultStatus='official_confirmed';el._panelResultRound=1241;el._targetRound=1241;
                const mode=el._smartSyncPolicy(Date.UTC(2026,8,14,0,0,0)).mode;
                [el._panelResultStatus,el._panelResultRound,el._targetRound]=state;
                return mode;
            })(),
        })""")
        assert policies == {'weekday': 'wake', 'drawWindow': 'poll', 'settled': 'idle'}

        await page.locator('[data-register]').first.click()
        assert await page.locator('#editor').evaluate('n=>n.open')
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / 'fixture.png'
            qrcode.make(QR).save(image)
            await page.locator('#file').set_input_files(str(image))
            await page.wait_for_function("!el._busy && el.node('game_a').value==='1, 7, 15, 24, 33, 45'")
        assert not await page.evaluate("requests.some(r=>r.type==='lotto_645/purchases_save')")
        assert '아직 저장하지' in await page.locator('#editor-message').text_content()
        await page.locator('#save').click()
        await page.wait_for_function("!el._busy && !el.node('editor').open && requests.some(r=>r.type==='lotto_645/purchases_save')")
        saves = await page.evaluate("requests.filter(r=>r.type==='lotto_645/purchases_save')")
        assert saves[-1]['round'] == 1241
        assert saves[-1]['revision'] == ''
        assert 'qr' not in saves[-1] and 'image' not in saves[-1]
        assert saves[-1]['values']['game_a'] == '1, 7, 15, 24, 33, 45'
        assert await page.locator('#wallet-games .ticket-row').count() == 1
        assert await page.locator('#wallet-games .ball').count() == 6

        await page.locator('#edit-wallet').click()
        await page.locator('#game_a').fill('2, 3, 4, 5, 6, 7')
        await page.evaluate("""async()=>{
            const base=el._hass.callWS;
            window.draftRevision=el._revision;
            el._hass.callWS=async msg=>({...await base(msg),revision:'server-newer',
                result_round:1241,draw:{numbers:[7,13,16,23,24,43],bonus:9},
                result_verification:{status:'provisional'},
                reviews:[{method_id:'test',display_name:'★4.5 · 90.0점 | 시험',reviewed_rounds:2}],
                review_round:{round:1241,status:'provisional',peer_count:1,methods:[{method_id:'test',review_score:85,exact_match_count:5,near_match_count:1,rank_this_round:1}]}});
            await el.refreshStatus();
        }""")
        assert await page.locator('#drawtitle').text_content() == '제 1,241회'
        assert await page.locator('#game_a').input_value() == '2, 3, 4, 5, 6, 7'
        assert await page.evaluate("el._revision===draftRevision && el._walletData.revision==='server-newer'")
        assert '★4.5' in await page.locator('#reviews').text_content()
        assert '잠정' in await page.locator('#reviews').text_content()
        assert 'HA 상태 자동 동기화 중' in await page.locator('#sync-status').text_content()
        await page.evaluate("""async()=>{
            const base=el._hass.callWS;
            el._hass.callWS=async msg=>({...await base(msg),review_round:{},
                reviews:[{method_id:'old',display_name:'☆평가대기 | 종합 앙상블',reviewed_rounds:0,
                    unrated_result:{round:1241,comparison:{prize:'5등'},counts_toward_rating:false}}]});
            await el.refreshStatus();
        }""")
        assert '1241회 5등 · 누적 제외' in await page.locator('#reviews').text_content()
        assert '생성시각' in await page.locator('#reviewstatus').text_content()
        assert await page.locator('#game_a').input_value() == '2, 3, 4, 5, 6, 7'
        await page.evaluate("""async()=>{
            const base=el._hass.callWS;
            el._hass.callWS=async msg=>({...await base(msg),result_round:1241,
                draw:{numbers:[7,24,30,31,32,42],bonus:9},result_verification:{status:'official_confirmed'},
                winning:{status:'evaluated',round:1241,winning_game_count:2,highest_prize:'2등',
                    winning_numbers:[7,24,30,31,32,42],bonus_number:9,results:[
                      {method_id:'public_ensemble',sensor_name:'공개 공식 · 종합 앙상블',source:'local',recommended_numbers:[7,13,15,24,38,42],prize:'5등',prize_rank:5,main_match_count:3,matched_main_numbers:[7,24,42],bonus_match:false,matched_bonus_number:null},
                      {method_id:'weighted_frequency',sensor_name:'공개 공식 · 가중 빈도',source:'local',recommended_numbers:[7,9,24,30,31,32],prize:'2등',prize_rank:2,main_match_count:5,matched_main_numbers:[7,24,30,31,32],bonus_match:true,matched_bonus_number:9}
                    ]}});
            await el.refreshStatus();
        }""")
        await page.locator('#tab-review').click()
        winning_rows=page.locator('#predictions tr[data-winning="true"]')
        assert await winning_rows.count()==2
        first=winning_rows.nth(0)
        assert await first.locator('.ball[data-hit="main"]').count()==3
        assert await first.locator('.ball[data-hit="miss"]').count()==3
        label=await first.locator('.result-balls').get_attribute('aria-label')
        assert '당첨번호 일치 7, 24, 42' in label and '미일치 13, 15, 38' in label
        assert float(await first.locator('.ball[data-hit="miss"]').first.evaluate('n=>getComputedStyle(n).opacity')) < 0.5
        assert await first.locator('.ball[data-hit="main"]').first.evaluate("n=>getComputedStyle(n).outlineStyle==='solid'")
        second=winning_rows.nth(1)
        assert await second.locator('.ball[data-hit="bonus"]').count()==1
        assert await second.locator('.ball[data-hit="bonus"]').evaluate("n=>getComputedStyle(n).outlineStyle==='dashed'")
        assert '보너스 9' in await second.locator('.result-detail').text_content()
        await page.locator('#close-editor').click()
        assert await page.get_by_role('link', name='로또 통합 및 센서 설정').get_attribute('href') == '/config/integrations/integration/lotto_645'
        await page.evaluate("window.menuCount=0;el.addEventListener('hass-toggle-menu',()=>menuCount++);el.narrow=true")
        await page.locator('#menu').click()
        assert await page.evaluate('menuCount') == 1
        await page.evaluate('el.narrow=false')
        for width in (320, 390, 768, 870, 871, 1440):
            await page.set_viewport_size({'width': width, 'height': 900})
            await page.evaluate('(narrow)=>el.narrow=narrow', width <= 870)
            for name in ('home', 'wallet', 'review'):
                await page.locator(f'#tab-{name}').click()
                assert await page.evaluate('el.scrollWidth<=el.clientWidth+1'), (width, name)
        await page.evaluate("el.hass={...el._hass,themes:{darkMode:true}}")
        assert await page.evaluate("el.getAttribute('data-theme')==='dark' && el.node('brand').naturalWidth===expectedLogoSize[0] && el.node('brand').naturalHeight===expectedLogoSize[1]")
        assert await page.locator('.draw-stage').evaluate("n=>getComputedStyle(n).backgroundColor==='rgb(255, 255, 255)' && getComputedStyle(n).color==='rgb(25, 31, 40)'")
        await verify_safe_area(page)
        await verify_component_design(page)
        await verify_panel_tools(page)
        assert not errors, errors
        await browser.close()
        print('PASS: smart sync, HA-driven narrow host header, real ES modules, canonical logo, PNG QR, explicit save, draft preservation, safe areas, responsive views and panel tools')


if __name__ == '__main__':
    asyncio.run(run())
