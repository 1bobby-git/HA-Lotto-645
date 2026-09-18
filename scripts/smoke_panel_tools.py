"""Full-panel help, clock and scroll tests; HA network is an isolated fixture."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from urllib.parse import urlparse

from smoke_panel_host_layout import verify_panel_host_layout

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'custom_components/lotto_645/www'


def guide_catalog():
    # Use only the shipped public catalog; never import private calculation code.
    import json
    rows=json.loads((WWW.parent/'catalog_seed.json').read_text(encoding='utf-8'))['methods']
    return [{'method_id':r['formula_id'],'name':r['name'], 'description':r['public_summary']} for r in rows] + [{'method_id':'home_assistant_ai','name':'Home Assistant AI 추천'}]


async def verify_panel_tools(page):
    catalog = guide_catalog()
    requests = []
    fail_ai = [True]

    async def serve_guide(route):
        path = urlparse(route.request.url).path
        requests.append(path)
        if path.endswith('/home_assistant_ai.md') and fail_ai[0]:
            fail_ai[0] = False
            await route.fulfill(status=503, body='temporary test failure')
            return
        name = Path(path).name
        assert name in {m['method_id']+'.md' for m in catalog}
        content=(WWW / 'methods' / name).read_text(encoding='utf-8')
        if name == 'weighted_frequency.md':
            # Exercise long-document rendering without restoring private weights.
            content += '\n\n## Public rendering fixture\n\n' + ('| Item | State |\n|---|---|\n| Example | Ready |\n\n' * 24)
        await route.fulfill(body=content, content_type='text/markdown; charset=utf-8')

    await page.route('**/lotto_645_static/methods/**', serve_guide)
    await page.wait_for_function('!el._busy')
    await page.evaluate("""catalog => {
        window.tools=el.shadowRoot.querySelector('lotto-panel-tools-v2-3-3');
        window.toolsFixture={...el._latestToolsData,method_catalog:catalog,
            draw_schedule:{round:1242,basis:'regular_schedule',scheduled_at:'2026-09-19T20:35:00+09:00',
                sales_reopen_at:'2026-09-20T06:00:00+09:00',rollover_at:'2026-09-20T06:00:00+09:00',server_now:new Date().toISOString()},
            winning:{status:'evaluated',round:1241,winning_game_count:0,results:[]},
            reviews:catalog.map(m=>({method_id:m.method_id,label:m.name,display_name:'★1.0 · '+m.name,reviewed_rounds:1,mean_score:20,stars:1,total_score:20,history_preview:[{round:1241,review_score:20,exact_match_count:1}]})),
            review_round:{},
            last_review_round:{round:1241,status:'confirmed',peer_count:catalog.length,methods:catalog.map(m=>({method_id:m.method_id,label:m.name,numbers:[1,7,15,24,33,45],prize:'미당첨',prize_rank:null,exact_match_count:1,main_match_count:1,near_match_count:0,matched_main_numbers:[1],bonus_match:false,matched_bonus_number:null,review_score:20,stars:1,rank_this_round:1}))},
            result_verification:{status:'official_confirmed'},result_round:1241};
        // Reconnection refreshes use the same fixture, so layout changes cannot
        // replace the deliberately populated guide/review tables with old data.
        const previousWS=el._hass.callWS;
        el.hass={...el._hass,callWS:async msg=>{
            if(msg.type==='lotto_645/purchases_get'){
                requests.push(structuredClone(msg));return structuredClone(toolsFixture);
            }
            return previousWS(msg);
        }};
        el.updateResults(toolsFixture);el._clearSmartSync();el.showScreen('home');
        window.wsBeforeTools=requests.length;
    }""", catalog)
    assert await page.locator('#predictions .method-info-trigger').count() == len(catalog)
    assert await page.locator('#reviews .method-info-trigger').count() == len(catalog)
    assert await page.locator('lotto-panel-tools-v2-3-3').count() == 1
    assert await page.locator('#upcoming-countdown').is_visible()
    assert '다가오는 제 1,242회' in await page.locator('#upcoming-round').text_content()
    assert '한국시간' in await page.locator('#upcoming-date').text_content()
    assert not await page.locator('lotto-panel-tools-v2-3-3 .countdown').is_visible()
    assert await page.locator('lotto-panel-tools-v2-3-3').evaluate('n=>n.getBoundingClientRect().height===0')
    await page.evaluate("el.showScreen('review')")

    # Test unpositioned, sidebar-offset HA layouts as well as a positioned box.
    await verify_panel_host_layout(page)

    # Place the real panel under an inline ha-panel-custom-like element and a
    # positioned, allocated viewport. Never claim this is a live HA instance.
    await page.evaluate("""() => {
        const viewport=document.createElement('section');viewport.id='allocated';
        viewport.style.cssText='position:absolute;top:12px;bottom:12px;left:20px;right:20px';
        const inline=document.createElement('ha-panel-custom');viewport.append(inline);
        document.body.append(viewport);inline.append(el);
        el._clearSmartSync();el.showScreen('review');
    }""")
    # The two fixture moves above run real disconnect/connect callbacks.
    # Allow their read-only refreshes, then keep the no-layout/no-timer-I/O gate.
    await page.wait_for_function('!el._busy && !el._livePending && !el._liveQueued')
    assert await page.evaluate("requests.slice(wsBeforeTools).every(r=>r.type==='lotto_645/purchases_get')")
    await page.evaluate('wsBeforeTools=requests.length;el._clearSmartSync()')
    for width in (320,390,560,615,870,871,1366):
        await page.set_viewport_size({'width':width,'height':900})
        await page.evaluate('(narrow)=>{el.narrow=narrow;el.scrollTop=0}', width <= 870)
        geometry = await page.evaluate("""() => ({
            outer:document.scrollingElement.scrollHeight, viewport:innerHeight,
            box:el.getBoundingClientRect().height,expected:document.querySelector('#allocated').clientHeight,
            scrolls:el.scrollHeight>el.clientHeight,
            overflow:el.scrollWidth>el.clientWidth+1,
            nested:[...el.shadowRoot.querySelectorAll('.table-scroll')].some(n=>getComputedStyle(n).overflowY==='auto'),
        })""")
        assert geometry['outer'] <= geometry['viewport']+1, (width, geometry)
        assert abs(geometry['box']-geometry['expected']) <= 1, (width, geometry)
        assert geometry['scrolls'] and not geometry['overflow'] and not geometry['nested'], (width, geometry)
        await page.evaluate('el.scrollTop=el.scrollHeight')
        assert await page.locator('.review-footnote').is_visible()
    await page.set_viewport_size({'width':1000,'height':900})
    await page.evaluate('el.scrollTop=0')

    trigger = page.locator('#predictions .method-info-trigger[data-method-id="weighted_frequency"]')
    await trigger.click()
    await page.wait_for_function("tools.dialog.open && !tools.shadowRoot.querySelector('.method-body').hasAttribute('aria-busy')")
    body = page.locator('.method-body')
    assert '공개 분석식' in await body.text_content()
    assert 'Public rendering fixture' in await body.text_content()
    assert await body.locator('table').count() >= 2
    assert await page.evaluate("el.hasAttribute('data-method-open') && getComputedStyle(el).overflowY==='hidden'")
    assert await body.evaluate('n=>n.scrollHeight>n.clientHeight')
    before = await page.evaluate('el.scrollTop')
    await body.hover(); await page.mouse.wheel(0,800); await page.wait_for_timeout(120)
    assert await page.evaluate('el.scrollTop') == before
    assert await body.evaluate('n=>n.scrollTop') > 0
    await page.keyboard.press('Escape')
    assert not await page.evaluate('tools.dialog.open')
    assert await page.evaluate("el.shadowRoot.activeElement?.dataset.methodId==='weighted_frequency'")
    count = len(requests)
    await trigger.click(); await page.wait_for_function("!tools.shadowRoot.querySelector('.method-body').hasAttribute('aria-busy')")
    assert len(requests) == count, 'same guide must be cached'
    await page.keyboard.press('Escape')

    # Every packaged guide can be read from either table without generating AI.
    ai = page.locator('#reviews .method-info-trigger[data-method-id="home_assistant_ai"]')
    await ai.click(); await page.locator('.method-retry').wait_for()
    await page.locator('.method-retry').click()
    await page.wait_for_function("!tools.shadowRoot.querySelector('.method-body').hasAttribute('aria-busy')")
    assert 'AI는 번호를 변경하거나 당첨을 보장하지 않습니다.' in await body.text_content()
    await page.keyboard.press('Escape')
    for method in catalog:
        await page.evaluate('(id)=>tools.openGuide(id)', method['method_id'])
        assert await body.locator('h1,h2').count() >= 1, method['method_id']
        assert len(await body.text_content()) > 50, method['method_id']
        assert await body.locator('script,img,iframe').count() == 0
        await page.evaluate('tools.closeGuide()')

    # Focus trapping and restoration after a background result refresh.
    await trigger.click(); await page.wait_for_function("!tools.shadowRoot.querySelector('.method-body').hasAttribute('aria-busy')")
    await page.locator('.method-source').focus(); await page.keyboard.press('Tab')
    assert await page.locator('.method-close').evaluate('n=>n===n.getRootNode().activeElement')
    await page.keyboard.press('Shift+Tab')
    assert await page.locator('.method-source').evaluate('n=>n===n.getRootNode().activeElement')
    await page.evaluate('el.updateResults(toolsFixture);el._clearSmartSync()')
    await page.keyboard.press('Escape')
    assert await page.evaluate("el.shadowRoot.activeElement?.dataset.methodId==='weighted_frequency'")

    # Dialog must respect notches in both desktop and mobile layouts.
    for width in (320,390,870):
        await page.set_viewport_size({'width':width,'height':844})
        await page.evaluate("""() => {
            el.style.setProperty('--safe-area-inset-top','59px');el.style.setProperty('--safe-area-inset-bottom','34px');
            el.narrow=true;el.scrollTop=0;
        }""")
        await page.locator('#predictions .method-info-trigger[data-method-id="weighted_frequency"]').click()
        assert await page.locator('.method-close').evaluate('n=>n.getBoundingClientRect().top>=59')
        assert await page.locator('.method-foot').evaluate('n=>n.getBoundingClientRect().bottom<=innerHeight-34+1')
        assert await body.evaluate('n=>n.scrollWidth<=n.clientWidth+1')
        await page.keyboard.press('Escape')
    await page.evaluate("el.style.removeProperty('--safe-area-inset-top');el.style.removeProperty('--safe-area-inset-bottom')")

    # Explicit instants: count reaches zero at draw time, remains zero until the
    # Sunday 06:00 sales boundary, then starts the following-round countdown.
    result = await page.evaluate("""async () => {
        const {countdownState,renderGuideMarkdown}=await import('/lotto_645_static/lotto-panel-tools.js?v=2.3.3');
        const s=toolsFixture.draw_schedule;
        const prior=countdownState(s,Date.parse(s.scheduled_at)-1000);
        const at=countdownState(s,Date.parse(s.scheduled_at));
        const beforeReopen=countdownState(s,Date.parse(s.rollover_at)-1000);
        const next=countdownState(s,Date.parse(s.rollover_at));
        tools.tickClock(Date.parse(s.scheduled_at));
        const zeroAt=el.shadowRoot.querySelector('#upcoming-countdown').textContent;
        tools.tickClock(Date.parse(s.rollover_at)-1000);
        const zeroBefore=el.shadowRoot.querySelector('#upcoming-countdown').textContent;
        const reopenNote=el.shadowRoot.querySelector('#upcoming-date').textContent;
        tools.tickClock(Date.parse(s.rollover_at));
        const nextLabel=el.shadowRoot.querySelector('#upcoming-round').textContent;
        const nextValue=el.shadowRoot.querySelector('#upcoming-countdown').textContent;
        const invalid=countdownState({...s,scheduled_at:'bad'});
        const div=document.createElement('div');
        div.append(renderGuideMarkdown('# Test\\n\\n<script>window.bad=1</script>\\n\\n[x](javascript:alert) [data](data:text/html,bad) [ok](https://example.com/)','https://github.com/1bobby-git/HA-Lotto-645/blob/v1.11.10/docs/methods/a.md'));
        tools.tickClock(Date.now()+(tools._clockOffset||0));
        return {prior:prior.seconds,atWaiting:at.waiting,at:at.seconds,
            beforeWaiting:beforeReopen.waiting,before:beforeReopen.seconds,next:next.round,
            zeroAt,zeroBefore,reopenNote,nextLabel,nextValue,invalid,
            oldVisible:!tools.shadowRoot.querySelector('.countdown').hidden,
            scripts:div.querySelectorAll('script').length,links:[...div.querySelectorAll('a')].map(n=>n.protocol)};
    }""")
    assert result['prior'] == 1
    assert result['atWaiting'] and result['at'] == 0
    assert result['beforeWaiting'] and result['before'] == 0
    assert result['next'] == 1243
    assert result['zeroAt'] == result['zeroBefore'] == '추첨 예정 시각이 지났습니다.'
    assert '한국시간' in result['reopenNote']
    assert '다가오는 제 1,243회' in result['nextLabel'] and result['nextValue'] != '추첨 예정 시각이 지났습니다.'
    assert result['invalid'] is None and not result['oldVisible']
    assert result['scripts'] == 0 and result['links'] == ['https:']
    # A timer tick must never send purchases_get/result_check/generate requests.
    await page.wait_for_timeout(1150)
    assert await page.evaluate('requests.length===wsBeforeTools')
    await page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    assert await page.evaluate('tools._clockTimer===null')
    await page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));el.remove()")
    assert await page.evaluate('tools._clockTimer===null && !tools.dialog.open && !el.hasAttribute("data-method-open")')
    print(f'PASS: {len(catalog)} guides, single scroll, upcoming countdown restart, modal safe areas and no timer network')
