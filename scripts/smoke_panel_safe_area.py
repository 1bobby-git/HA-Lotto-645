"""Safe-area and Home Assistant narrow-header regression on the real panel."""
from __future__ import annotations

from playwright.async_api import Page

# width, height, top, right, bottom, left, sidebar-absorbed left
CASES = (
    (320, 740, 0, 0, 0, 0, None),
    (350, 800, 47, 0, 34, 0, None),
    (390, 844, 59, 0, 34, 0, None),
    (393, 852, 59, 0, 34, 0, None),
    (402, 874, 62, 0, 34, 0, None),
    (430, 932, 62, 0, 34, 0, None),
    (560, 900, 0, 0, 0, 0, None),
    (768, 1024, 24, 0, 20, 0, None),
    (852, 393, 0, 59, 21, 59, None),
    (852, 393, 0, 59, 21, 59, 0),
    (870, 900, 0, 0, 0, 0, None),
    (871, 900, 0, 0, 0, 0, None),
    (1100, 850, 0, 0, 0, 0, None),
    (1440, 1000, 0, 0, 0, 0, None),
)


async def verify_safe_area(page: Page) -> None:
    """Exercise HA-supplied narrow state, insets, component header, dialog and notices."""
    await page.evaluate("""() => {
        if (el.node('editor').open) el.node('editor').close();
        el._editing=false;el.removeAttribute('data-editor-open');el.showScreen('home');
        el.node('message').textContent='';
    }""")
    for dark in (False, True):
        for width, height, top, right, bottom, left, content_left in CASES:
            narrow = width <= 870
            await page.set_viewport_size({'width': width, 'height': height})
            await page.evaluate("""p => {
                const root=document.documentElement.style;
                ['top','right','bottom','left'].forEach(side => root.setProperty('--safe-area-inset-'+side,p[side]+'px'));
                root.removeProperty('--safe-area-content-inset-left');root.removeProperty('--safe-area-content-inset-right');
                if(p.contentLeft!==null)root.setProperty('--safe-area-content-inset-left',p.contentLeft+'px');
                el.narrow=p.narrow;
                el.hass={...el._hass,themes:{darkMode:p.dark}};el.scrollTop=0;
            }""", {'top':top,'right':right,'bottom':bottom,'left':left,'contentLeft':content_left,'dark':dark,'narrow':narrow})
            result = await page.evaluate("""() => {
                const s=el.shadowRoot;
                const box=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
                const hostHeader=s.querySelector('.ha-host-header');
                return {host:box(el),hostHeader:box(hostHeader),hostDisplay:getComputedStyle(hostHeader).display,
                  menu:box(el.node('menu')),title:box(s.querySelector('.ha-host-title')),
                  brand:box(el.node('brand-home')),settings:box(s.querySelector('.settings')),tabs:box(s.querySelector('.main-tabs')),
                  appTop:parseFloat(getComputedStyle(s.querySelector('.app-header')).paddingTop),
                  left:parseFloat(getComputedStyle(s.querySelector('.wrap')).paddingLeft),
                  right:parseFloat(getComputedStyle(s.querySelector('.wrap')).paddingRight),
                  pageBottom:parseFloat(getComputedStyle(s.querySelector('.shell')).paddingBottom),
                  overflow:el.scrollWidth>el.clientWidth+1};
            }""")
            label = (width,height,dark,top,right,bottom,left,content_left)
            assert not result['overflow'], (label,result)
            safe_left = left if content_left is None else content_left
            for key in ('brand','settings','tabs'):
                assert result[key]['right'] <= result['host']['right']-right+1, (label,key,result)
                assert result[key]['x'] >= result['host']['x']+safe_left-1, (label,key,result)

            if narrow:
                assert result['hostDisplay'] == 'flex', (label,result)
                assert result['appTop'] == 0, (label,result)
                assert result['hostHeader']['height'] >= 40 + top - 1, (label,result)
                assert result['menu']['x'] >= result['host']['x'] + left - 1, (label,result)
                assert result['menu']['right'] <= result['title']['x'] + 1, (label,result)
                assert result['menu']['y'] >= result['host']['y'] + top - 1, (label,result)
                assert result['brand']['y'] >= result['hostHeader']['bottom'] - 1, (label,result)
                assert result['settings']['y'] >= result['hostHeader']['bottom'] - 1, (label,result)
            else:
                assert result['hostDisplay'] == 'none', (label,result)
                assert result['appTop'] == top, (label,result)
                assert result['brand']['y'] >= result['host']['y'] + top - 1, (label,result)
                assert result['settings']['y'] >= result['host']['y'] + top - 1, (label,result)

            assert result['tabs']['y'] >= max(result['brand']['bottom'], result['settings']['bottom'])-1, (label,result)
            assert result['pageBottom'] >= bottom, (label,result)
            if content_left == 0:
                assert result['left'] == 28, (label,result)

            await page.evaluate("""() => {
                el.node('entry-field').hidden=false;
                const option=document.createElement('option');option.value='layout-fixture';
                option.textContent='여러 통합이 연결된 경우의 긴 이름';el.node('entry').append(option);
            }""")
            if width <= 560:
                assert await page.evaluate("el.node('entry-field').getBoundingClientRect().top>=el.node('brand-home').getBoundingClientRect().bottom"), label
                assert await page.evaluate('el.scrollWidth<=el.clientWidth+1'), label
            await page.evaluate("""() => {
                el.node('entry').querySelector('[value="layout-fixture"]').remove();
                el.node('entry-field').hidden=el.node('entry').options.length<=1;
                el.message('안전 영역 알림 확인');
            }""")
            notice = await page.locator('#message').bounding_box()
            assert notice and notice['y']+notice['height'] <= height-bottom+1, (label,notice)
            assert notice['x'] >= left and notice['x']+notice['width'] <= width-right+1, (label,notice)
            await page.evaluate("el.node('message').textContent=''")
            await page.locator('[data-register]').first.click()
            dialog = await page.locator('#editor').evaluate("""n=>({top:parseFloat(getComputedStyle(n).paddingTop),left:parseFloat(getComputedStyle(n).paddingLeft),right:parseFloat(getComputedStyle(n).paddingRight),overflow:n.scrollWidth>n.clientWidth+1})""")
            assert dialog == {'top':top,'left':left,'right':right,'overflow':False}, (label,dialog)
            close = await page.locator('#close-editor').bounding_box()
            assert close and close['y'] >= top and close['x']+close['width'] <= width-right+1, (label,close)
            await page.locator('#manual').click();await page.wait_for_function('!el._busy')
            save = await page.locator('#save').bounding_box()
            assert save and save['y']+save['height'] <= height-bottom+1, (label,save)
            assert await page.locator('.sheet-scroll').evaluate('n=>n.clientHeight>0'), label
            await page.keyboard.press('Escape')
            assert not await page.locator('#editor').evaluate('n=>n.open'), label
            assert await page.evaluate("el.shadowRoot.activeElement?.hasAttribute('data-register')"), label
    await page.evaluate("""() => {
        const root=document.documentElement.style;
        ['top','right','bottom','left'].forEach(side=>{root.removeProperty('--safe-area-inset-'+side);root.removeProperty('--safe-area-content-inset-'+side);});
        el.narrow=false;el.hass={...el._hass,themes:{darkMode:false}};el.scrollTop=0;
    }""")
    await page.set_viewport_size({'width':1440,'height':1000})
    assert await page.locator('.ha-host-header').evaluate("n=>getComputedStyle(n).display==='none'")
    assert await page.locator('.app-header').evaluate("n=>getComputedStyle(n).paddingTop==='0px'")
    print(f'PASS: HA narrow-state header + safe-area layout {len(CASES)*2} theme/viewport/inset fixtures')
