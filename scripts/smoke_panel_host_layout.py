"""Regression for a panel escaping HA's unpositioned, sidebar-offset content.

Only the test fixture reads ancestor geometry. Production uses normal CSS flow
and never measures or changes the HA drawer, sidebar, or document styles.
"""
from __future__ import annotations

from playwright.async_api import Page

# viewport width/height, sidebar reservation, narrow, document direction
CASES = (
    (1366, 720, 256, False, 'ltr'),
    (871, 900, 256, False, 'ltr'),
    (870, 900, 0, True, 'ltr'),
    (390, 844, 0, True, 'ltr'),
    (320, 740, 0, True, 'ltr'),
    (1366, 720, 56, False, 'ltr'),
    (1366, 720, 0, False, 'ltr'),
    (1366, 720, 300, False, 'ltr'),
    (1666, 896, 256, False, 'ltr'),
    (1366, 720, 256, False, 'rtl'),
)


async def verify_panel_host_layout(page: Page) -> None:
    """Use real panel modules under slots and non-positioned inline wrappers."""
    await page.wait_for_function('!el._busy')
    await page.evaluate("""() => {
        window.hostLayoutPrevious={parent:el.parentNode,next:el.nextSibling,
            css:el.style.cssText,hass:el._hass,narrow:el.narrow,screen:el._screen};
        window.hostLayoutRequests=requests.length;
        const fixture=document.createElement('lotto-ha-layout-fixture');
        fixture.id='ha-layout-fixture';
        fixture.style.cssText='display:block;height:100%;min-width:0;';
        const root=fixture.attachShadow({mode:'open'});
        root.innerHTML=`<style>
          :host{--fixture-sidebar:256px;display:block;height:100%}
          .layout{height:100%}
          .sidebar{position:fixed;inset-block:0;inset-inline-start:0;
            width:var(--fixture-sidebar);overflow:auto;z-index:6;
            background:white;color:#191f28;box-sizing:border-box}
          .sidebar-content{height:1800px;padding:16px;box-sizing:border-box}
          .app-content{position:static;box-sizing:border-box;min-width:0;
            padding-inline-start:var(--fixture-sidebar);width:100%;height:100%;overflow:unset}
          .reserve{display:none}
          :host([data-layout="margin"]) .app-content{
            padding-inline-start:0;margin-inline-start:var(--fixture-sidebar);width:auto}
          :host([data-layout="flex"]) .layout{display:flex}
          :host([data-layout="flex"]) .reserve{display:block;width:var(--fixture-sidebar);flex:none}
          :host([data-layout="flex"]) .app-content{padding:0;width:auto;flex:1;min-width:0}
        </style><aside class="sidebar"><div class="sidebar-content">Home Assistant</div></aside>
        <div class="layout"><div class="reserve"></div><div class="app-content"><slot name="appContent"></slot></div></div>`;
        const resolver=document.createElement('partial-panel-resolver');
        resolver.slot='appContent';
        const custom=document.createElement('ha-panel-custom');
        resolver.append(custom);fixture.append(resolver);document.body.append(fixture);
        // Intentionally do not position or size either inline wrapper. The
        // former positioned '#allocated' fixture hid the v1.11.8 regression.
        el.style.removeProperty('width');el.style.removeProperty('margin-left');
        custom.append(el);el._clearSmartSync();
    }""")
    # Moving a live panel deliberately reconnects it. Settle that read-only
    # refresh before proving CSS/sidebar changes themselves do not fetch data.
    await page.wait_for_function('!el._busy && !el._livePending && !el._liveQueued')
    assert await page.evaluate("requests.slice(hostLayoutRequests).every(r=>r.type==='lotto_645/purchases_get')")
    await page.evaluate('hostLayoutRequests=requests.length;el._clearSmartSync()')
    checked = 0
    try:
        for layout in ('padding', 'margin', 'flex'):
            for width, height, sidebar, narrow, direction in CASES:
                await page.set_viewport_size({'width': width, 'height': height})
                await page.evaluate("""p => {
                    const fixture=document.querySelector('#ha-layout-fixture');
                    fixture.dataset.layout=p.layout;fixture.dir=p.direction;
                    fixture.style.setProperty('--fixture-sidebar',p.sidebar+'px');
                    fixture.shadowRoot.querySelector('.sidebar').style.display=p.sidebar?'block':'none';
                    el.narrow=p.narrow;
                    el.hass={...el._hass,kioskMode:false,dockedSidebar:p.sidebar?'docked':'always_hidden'};
                    el._clearSmartSync();el.scrollTop=0;
                }""", {'layout': layout, 'direction': direction, 'sidebar': sidebar, 'narrow': narrow})
                for screen in ('home', 'wallet', 'review'):
                    await page.evaluate('(screen)=>{el.showScreen(screen);el.scrollTop=0}', screen)
                    await page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(resolve))')
                    geometry = await page.evaluate("""() => {
                        const box=n=>n.getBoundingClientRect().toJSON();
                        const fixture=document.querySelector('#ha-layout-fixture');
                        const q=s=>el.shadowRoot.querySelector(s);
                        return {panel:box(el),position:getComputedStyle(el).position,
                            outerHeight:document.scrollingElement.scrollHeight,outerWidth:document.scrollingElement.scrollWidth,
                            outerTop:document.scrollingElement.scrollTop,
                            resolverDisplay:getComputedStyle(fixture.querySelector('partial-panel-resolver')).display,
                            customDisplay:getComputedStyle(fixture.querySelector('ha-panel-custom')).display,
                            contentPosition:getComputedStyle(fixture.shadowRoot.querySelector('.app-content')).position,
                            scrolls:el.scrollHeight>el.clientHeight,
                            overflow:el.scrollWidth>el.clientWidth+1,
                            header:getComputedStyle(q('.ha-host-header')).display,
                            brand:box(q('.brand-logo')),tabs:box(q('.main-tabs')),
                            title:box(q('#screen-'+el._screen+' h1')),
                            clock:box(q('lotto-panel-tools-v2-3-3'))};
                    }""")
                    label = (layout, width, height, sidebar, narrow, direction, screen)
                    left = sidebar if direction == 'ltr' else 0
                    right = width if direction == 'ltr' else width - sidebar
                    assert geometry['position'] == 'relative', (label, geometry)
                    assert geometry['resolverDisplay'] == geometry['customDisplay'] == 'inline', (label, geometry)
                    assert geometry['contentPosition'] == 'static', (label, geometry)
                    assert abs(geometry['panel']['left'] - left) <= 1, (label, geometry)
                    assert abs(geometry['panel']['right'] - right) <= 1, (label, geometry)
                    assert abs(geometry['panel']['height'] - height) <= 1, (label, geometry)
                    assert abs(geometry['panel']['top']) <= 1, (label, geometry)
                    assert geometry['outerHeight'] <= height + 1 and geometry['outerWidth'] <= width + 1, (label, geometry)
                    assert geometry['outerTop'] == 0 and not geometry['overflow'], (label, geometry)
                    assert geometry['header'] == ('flex' if narrow or sidebar == 0 else 'none'), (label, geometry)
                    for key in ('brand', 'tabs', 'title', 'clock'):
                        assert geometry[key]['left'] >= left - 1 and geometry[key]['right'] <= right + 1, (label, key, geometry)
                    if screen == 'review':
                        assert geometry['scrolls'], (label, geometry)
                        await page.evaluate('el.scrollTop=el.scrollHeight')
                        footer = await page.locator('.footer').bounding_box()
                        assert footer and footer['y'] >= 0 and footer['y'] + footer['height'] <= height + 1, (label, footer)
                        assert await page.evaluate('document.scrollingElement.scrollTop===0'), label
                        # The HA sidebar retains its own independent scrollbar.
                        before = await page.evaluate('el.scrollTop')
                        await page.evaluate("document.querySelector('#ha-layout-fixture').shadowRoot.querySelector('.sidebar').scrollTop=100")
                        assert await page.evaluate('el.scrollTop') == before, label
                checked += 1

        # Negative control: put the old out-of-flow rule back temporarily. It
        # MUST escape this fixture, proving that sidebar overlap is detectable.
        await page.set_viewport_size({'width': 1366, 'height': 720})
        regression = await page.evaluate("""() => {
            const fixture=document.querySelector('#ha-layout-fixture');
            fixture.dataset.layout='padding';fixture.dir='ltr';
            fixture.style.setProperty('--fixture-sidebar','256px');
            const old=document.createElement('style');
            old.textContent=':host{position:absolute;inset:0}';el.shadowRoot.append(old);
            const r=el.getBoundingClientRect();const result={left:r.left,width:r.width};
            old.remove();return result;
        }""")
        assert regression['left'] < 256 and regression['width'] > 1110, regression
        assert await page.evaluate('requests.length===hostLayoutRequests')
    finally:
        await page.evaluate("""() => {
            const previous=hostLayoutPrevious;
            previous.parent.insertBefore(el,previous.next);
            document.querySelector('#ha-layout-fixture').remove();
            el.style.cssText=previous.css;el.narrow=previous.narrow;el.hass=previous.hass;
            el.showScreen(previous.screen);el.scrollTop=0;el._clearSmartSync();
            delete window.hostLayoutPrevious;delete window.hostLayoutRequests;
        }""")
    print(f'PASS: {checked} unpositioned HA shell fixtures, 3 screens, docked/rail/hidden sidebar, 870/871, RTL, single scroll and old-rule negative control')
