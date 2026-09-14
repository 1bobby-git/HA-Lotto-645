"""Computed presentation contracts on the real production modules.

Fixtures use the same browser font environment. They simulate allocated panel
width, NOT a live HA sidebar or a physical iPhone. No external fonts are fetched.
"""
from __future__ import annotations

from playwright.async_api import Page

# Browser viewport, allocated panel width, HA narrow property.
# 871/615 guards against confusing component width with HA's narrow state.
CASES = (
    (320, 320, True), (350, 350, True), (390, 390, True),
    (430, 430, True), (560, 560, True), (561, 561, True),
    (768, 768, True), (870, 870, True), (871, 615, False),
    (1100, 844, False), (1366, 1110, False), (1440, 1184, False),
)


async def verify_component_design(page: Page) -> None:
    """Assert effective CSS, not just declarations in the legacy template."""
    await page.wait_for_function('!el._busy')
    await page.evaluate("""async () => {
        const { applyComponentDesign } = await import('/lotto_645_static/lotto-panel-design.js?v=1.11.7');
        applyComponentDesign(el); applyComponentDesign(el);
        el._clearSmartSync();
        window.designRequestsBefore = requests.length;
    }""")
    assert await page.locator('style[data-lotto-component-design]').count() == 1
    assert await page.locator('.component-version').count() == 1
    assert await page.locator('.settings-copy').count() == 1
    assert await page.locator('.ha-component-title').count() == 0
    assert await page.locator('.component-version').text_content() == 'v1.11.7'
    checked = 0
    for dark in (False, True):
        for viewport, width, narrow in CASES:
            await page.set_viewport_size({'width': viewport, 'height': 1000})
            await page.evaluate("""p => {
                el.style.width=p.width+'px';
                el.style.marginLeft=(p.viewport-p.width)+'px';
                el.narrow=p.narrow;
                el.hass={...el._hass,themes:{darkMode:p.dark},kioskMode:false,dockedSidebar:'docked'};
                el.showScreen('home'); el.scrollTop=0;
            }""", {'viewport': viewport, 'width': width, 'narrow': narrow, 'dark': dark})
            state = await page.evaluate("""() => {
                const q=s=>el.shadowRoot.querySelector(s);
                const style=s=>getComputedStyle(q(s));
                const rect=s=>q(s).getBoundingClientRect().toJSON();
                return {
                  hostHeader:style('.ha-host-header').display,
                  height:rect('.header-row').height,
                  logo:rect('.brand-logo'),
                  logoFit:style('.brand-logo').objectFit,
                  tabs:rect('.main-tabs'),
                  gap:style('.main-tabs').columnGap,
                  tabFont:style('.main-tabs button').fontSize,
                  connection:style('.connection').display,
                  connectionRect:rect('.connection'),settings:rect('.settings'),
                  version:style('.component-version').display,
                  headerBg:style('.app-header').backgroundColor,
                  tabColor:style('[aria-selected="true"]').color,
                  main:rect('main'),gutter:style('main').paddingLeft,
                  mainTop:style('main').paddingTop,
                  baseFont:getComputedStyle(el).fontFamily,
                  headerFont:style('.connection').fontFamily,
                  bodyFont:style('.page-heading p').fontFamily,
                  lead:style('.page-heading p').fontSize,
                  kicker:style('.kicker').fontSize,kickerWeight:style('.kicker').fontWeight,
                  footer:style('.footer').fontSize,
                  hero:style('.draw-stage').borderRadius,
                  card:style('.ticket-paper').borderRadius,
                  button:style('.page-heading .primary').borderRadius,
                  shadow:style('.draw-stage').boxShadow,
                  drawBg:style('.draw-stage').backgroundColor,
                  drawOverflow:q('.draw-numbers').scrollWidth>q('.draw-numbers').clientWidth+1,
                  overflow:el.scrollWidth>el.clientWidth+1,
                  palette:[...q('.draw-numbers').querySelectorAll('.ball')].map(n=>({
                    band:n.dataset.band,bg:getComputedStyle(n).backgroundColor,
                    color:getComputedStyle(n).color,image:getComputedStyle(n).backgroundImage
                  }))
                };
            }""")
            label = (viewport, width, narrow, dark)
            mobile = width <= 560
            assert state['hostHeader'] == ('flex' if narrow else 'none'), (label, state)
            assert state['height'] == (68 if mobile else 76), (label, state)
            assert state['logo']['height'] == (30 if width <= 350 else 32 if mobile else 38), (label, state)
            assert state['logoFit'] == 'contain' and state['logo']['width'] > 0, (label, state)
            assert state['tabs']['height'] == 48 and state['tabFont'] == '14px', (label, state)
            assert state['gap'] == ('24px' if mobile else '30px'), (label, state)
            assert state['connection'] == 'inline-flex', (label, state)
            assert state['version'] == ('none' if mobile else 'block'), (label, state)
            assert state['headerBg'] == 'rgb(255, 255, 255)', (label, state)
            assert state['tabColor'] == 'rgb(25, 31, 40)', (label, state)
            assert 'Noto Sans KR' in state['baseFont'], (label, state)
            assert state['headerFont'] == state['bodyFont'] == state['baseFont'], (label, state)
            assert state['lead'] == '15px' and state['footer'] == '12px', (label, state)
            assert state['kicker'] == '12px' and state['kickerWeight'] == '800', (label, state)
            assert state['mainTop'] == ('28px' if mobile else '38px'), (label, state)
            assert state['hero'] == ('16px' if mobile else '18px'), (label, state)
            assert state['card'] == '14px' and state['button'] == '10px', (label, state)
            assert (state['shadow'] == 'none') == dark, (label, state)
            assert state['drawBg'] == 'rgb(255, 255, 255)', (label, state)
            assert not state['drawOverflow'] and not state['overflow'], (label, state)
            assert state['logo']['right'] <= state['connectionRect']['left'] + 1, (label, state)
            assert state['connectionRect']['right'] <= state['settings']['left'] + 1, (label, state)
            assert abs(state['logo']['left'] - (state['main']['left'] + float(state['gutter'][:-2]))) < 1, (label, state)
            expected = {'1':'rgb(205, 146, 52)', '2':'rgb(62, 99, 197)', '3':'rgb(189, 65, 82)',
                        '4':'rgb(140, 140, 140)', '5':'rgb(90, 155, 80)'}
            assert len(state['palette']) == 7
            for ball in state['palette']:
                assert ball['bg'] == expected[ball['band']] and ball['color'] == 'rgb(255, 255, 255)' and ball['image'] == 'none', (label, ball)
            for name in ('home', 'wallet', 'review'):
                await page.locator(f'#tab-{name}').click()
                assert await page.evaluate('el.scrollWidth<=el.clientWidth+1'), (label, name)
            checked += 1
    # A hidden sidebar and kiosk mode remain HA decisions, not component breakpoints.
    await page.evaluate("el.narrow=false;el.hass={...el._hass,dockedSidebar:'always_hidden',kioskMode:false}")
    assert await page.locator('.ha-host-header').is_visible()
    await page.evaluate("el.hass={...el._hass,kioskMode:true}")
    assert not await page.locator('.ha-host-header').is_visible()
    await page.evaluate("""() => {
        el.style.removeProperty('width');el.style.removeProperty('margin-left');el.narrow=false;
        el.hass={...el._hass,themes:{darkMode:false},dockedSidebar:'docked',kioskMode:false};
        el.showScreen('home');el.scrollTop=0;
    }""")
    # Design application, theme/width switches and local tabs must not fetch data.
    assert await page.evaluate('requests.length===designRequestsBefore')
    print(f'PASS: {checked} shared design theme/viewport fixtures, fonts, header/logo/tabs, allocated panel width, palette, card/control radii and unchanged draw balls')
