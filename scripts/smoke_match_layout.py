"""Exact match semantics and no visual intrusion at narrow widths."""
from pathlib import Path
import os

async def verify_match_layout(page):
    await page.evaluate("""async () => {
        const {renderPredictionRows,ticketRows}=await import('/lotto_645_static/lotto-panel-view.js?v=1.15.0');
        window.matchRows=[
          {main_match_count:1,matched_main_numbers:[7],bonus_match:false,prize_rank:null,prize:'미당첨'},
          {main_match_count:2,matched_main_numbers:[7,13],bonus_match:false,prize_rank:null,prize:'미당첨'},
          {main_match_count:0,matched_main_numbers:[],bonus_match:true,matched_bonus_number:42,prize_rank:null,prize:'미당첨'},
          {main_match_count:0,matched_main_numbers:[],bonus_match:false,prize_rank:null,prize:'미당첨'},
          {prize:'추첨 대기'}
        ].map((r,i)=>({...r,method_id:'fixture_'+i,sensor_name:'일치 표시 검증',recommended_numbers:[7,13,15,24,38,42],slot:String(i)}));
        renderPredictionRows(el.node('predictions'),matchRows,[]);
        ticketRows(el.node('wallet-games'),matchRows);
        el._clearSmartSync();el.showScreen('review');
    }""")
    rows=page.locator('#predictions tr')
    assert await rows.nth(0).locator('[data-hit="main"]').count()==1
    assert await rows.nth(1).locator('[data-hit="main"]').count()==2
    assert await rows.nth(2).locator('[data-hit="bonus"]').count()==1
    assert await rows.nth(3).locator('[data-hit="main"]').count()==0
    assert await rows.nth(4).locator('[data-hit]').count()==0
    assert await page.locator('#predictions .prize[data-winning="true"]').count()==0
    assert '미당첨' in await rows.nth(0).text_content()
    assert '일치 2개' in await rows.nth(1).locator('.result-detail').text_content()
    assert '보너스 일치 42' in await rows.nth(2).locator('.result-balls').get_attribute('aria-label')
    assert await rows.nth(3).locator('.ball').first.evaluate("n=>getComputedStyle(n).opacity==='1'")
    for screen,root in [('review','#predictions'),('wallet','#wallet-games')]:
        await page.evaluate('(screen)=>el.showScreen(screen)',screen)
        for dark in (False,True):
            await page.evaluate('(dark)=>{el.hass={...el._hass,themes:{darkMode:dark}};el._clearSmartSync()}',dark)
            for width in (320,390,430,768,1366):
                await page.set_viewport_size({'width':width,'height':1000})
                checks=await page.locator(root+' .result-balls').evaluate_all("""groups=>groups.map(g=>{
                    const box=g.getBoundingClientRect(), balls=[...g.querySelectorAll('.ball')];
                    const rects=balls.map(b=>b.getBoundingClientRect());
                    return {fits:rects.every(r=>r.left>=box.left-0.5 && r.right<=box.right+0.5),
                        separate:rects.every((a,i)=>rects.every((b,j)=>i===j || a.right<=b.left || b.right<=a.left || a.bottom<=b.top || b.bottom<=a.top)),
                        marks:balls.filter(b=>['main','bonus'].includes(b.dataset.hit)).every(b=>{
                          const s=getComputedStyle(b);return parseFloat(s.outlineOffset)+parseFloat(s.outlineWidth)<=0 && s.transform==='none';
                        })};})""")
                assert all(c['fits'] and c['separate'] and c['marks'] for c in checks),(screen,dark,width,checks)
    await page.evaluate("el.showScreen('review');el.hass={...el._hass,themes:{darkMode:false}};el._clearSmartSync()")
    await page.set_viewport_size({'width':390,'height':1000})
    await rows.nth(0).scroll_into_view_if_needed()
    if directory:=os.environ.get('LOTTO_SCREENSHOT_DIR'):
        Path(directory).mkdir(parents=True,exist_ok=True)
        await page.screenshot(path=str(Path(directory)/'partial-matches-mobile.png'))
    print('PASS: 1/2/bonus-only/zero/waiting match states, losing prize semantics, 20 responsive/theme table+wallet layouts, inward outlines')
