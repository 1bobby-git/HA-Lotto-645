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
    # Import the actual pure catalog, not the HA integration initializer.
    spec = importlib.util.spec_from_file_location('panel_tools_catalog', WWW.parent / 'methods.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.method_catalog() + [{'method_id':'home_assistant_ai','name':'Home Assistant AI 추천'}]


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
        await route.fulfill(path=str(WWW / 'methods' / name), content_type='text/markdown; charset=utf-8')

    await page.route('**/lotto_645_static/methods/**', serve_guide)
    await page.wait_for_function('!el._busy')
    await page.evaluate("""catalog => {
        window.tools=el.shadowRoot.querySelector('lotto-panel-tools');
        window.toolsFixture={...el._latestToolsData,method_catalog:catalog,
            draw_schedule:{round:1242,basis:'regular_schedule',scheduled_at:'2026-09-19T20:35:00+09:00',
                sales_reopen_at:'2026-09-20T06:00:00+09:00',rollover_at:'2026-09-20T06:00:00+09:00',server_now:new Date().toISOString()},
            winning:{status:'evaluated',round:1241,winning_game_count:0,results:catalog.map(m=>({method_id:m.method_id,sensor_name:m.name,source:'local',recommended_numbers:[1,7,15,24,33,45],prize:'미당첨'}))},
            reviews:catalog.map(m=>({method_id:m.method_id,display_name:'★1.0 · '+m.name,reviewed_rounds:1})),
            review_round:{},result_verification:{status:'official_confirmed'},result_round:1241};
        el.updateResults(toolsFixture);el._clearSmartSync();el.showScreen('home');
        window.wsBeforeTools=requests.length;
    }""", catalog)
    assert await page.locator('#predictions .method-info-trigger').count() == 18
    assert await page.locator('#reviews .method-info-trigger').count() == 18
    assert await page.locator('lotto-panel-tools').count() == 1
    assert await page.locator('.hero-draw-countdown').is_visible()
    assert '제 1,242회 추첨까지' in await page.locator('.hero-clock-label').text_content()
    assert '동행복권 정규 일정 기준' in await page.locator('.hero-clock-date').text_content()
    assert not await page.locator('lotto-panel-tools .countdown').is_visible()
    assert await page.locator('lotto-panel-tools').evaluate('n=>n.getBoundingClientRect().height===0')
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

    trigger = page.locator('#predictions [data-method-id="weighted_frequency"]')
    await trigger.click()
    await page.wait_for_function("tools.dialog.open && !tools.shadowRoot.querySelector('.method-body').hasAttribute('aria-busy')")
    body = page.locator('.method-body')
    assert '계산 예시' in await body.text_content()
    assert '0.34' in await body.text_content()
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
    ai = page.locator('#reviews [data-method-id="home_assistant_ai"]')
    await ai.click(); await page.locator('.method-retry').wait_for()
    await page.locator('.method-retry').click()
    await page.wait_for_function("!tools.shadowRoot.querySelector('.method-body').hasAttribute('aria-busy')")
    assert '개인정보' in await body.text_content()
    await page.keyboard.press('Escape')
    for method in catalog:
        await page.evaluate('(id)=>tools.openGuide(id)', method['method_id'])
        assert await body.locator('h2').count() >= 1, method['method_id']
        assert len(await body.text_content()) > 300, method['method_id']
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
        await page.locator('#predictions [data-method-id="weighted_frequency"]').click()
        assert await page.locator('.method-close').evaluate('n=>n.getBoundingClientRect().top>=59')
        assert await page.locator('.method-foot').evaluate('n=>n.getBoundingClientRect().bottom<=innerHeight-34+1')
        assert await body.evaluate('n=>n.scrollWidth<=n.clientWidth+1')
        await page.keyboard.press('Escape')
    await page.evaluate("el.style.removeProperty('--safe-area-inset-top');el.style.removeProperty('--safe-area-inset-bottom')")

    # Explicit instants: count reaches zero at draw time, remains zero until the
    # Sunday 06:00 sales boundary, then starts the following-round countdown.
    result = await page.evaluate("""async () => {
        const {countdownState,renderGuideMarkdown}=await import('/lotto_645_static/lotto-panel-tools.js?v=1.11.10');
        const s=toolsFixture.draw_schedule;
        const prior=countdownState(s,Date.parse(s.scheduled_at)-1000);
        const at=countdownState(s,Date.parse(s.scheduled_at));
        const beforeReopen=countdownState(s,Date.parse(s.rollover_at)-1000);
        const next=countdownState(s,Date.parse(s.rollover_at));
        tools.tickClock(Date.parse(s.scheduled_at));
        const zeroAt=el.shadowRoot.querySelector('.hero-clock-value').textContent;
        tools.tickClock(Date.parse(s.rollover_at)-1000);
        const zeroBefore=el.shadowRoot.querySelector('.hero-clock-value').textContent;
        const reopenNote=el.shadowRoot.querySelector('.hero-clock-date').textContent;
        tools.tickClock(Date.parse(s.rollover_at));
        const nextLabel=el.shadowRoot.querySelector('.hero-clock-label').textContent;
        const nextValue=el.shadowRoot.querySelector('.hero-clock-value').textContent;
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
    assert result['zeroAt'] == result['zeroBefore'] == '0일 00시간 00분 00초'
    assert '판매 시작' in result['reopenNote']
    assert '1,243회 추첨까지' in result['nextLabel'] and result['nextValue'] != '0일 00시간 00분 00초'
    assert result['invalid'] is None and not result['oldVisible']
    assert result['scripts'] == 0 and result['links'] == ['https:']
    # A timer tick must never send purchases_get/result_check/generate requests.
    await page.wait_for_timeout(1150)
    assert await page.evaluate('requests.length===wsBeforeTools')
    await page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    assert await page.evaluate('tools._clockTimer===null')
    await page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));el.remove()")
    assert await page.evaluate('tools._clockTimer===null && !tools.dialog.open && !el.hasAttribute("data-method-open")')
    print('PASS: 18 guides, single scroll, hero countdown zero-hold/restart, modal safe areas and no timer network')
