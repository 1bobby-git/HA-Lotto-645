"""Temporary final verification migration, applied after phases 1 and 2."""
from pathlib import Path
R=Path(__file__).resolve().parents[1];C=R/'custom_components/lotto_645'
p=R/'tests/test_analysis_engine.py';s=p.read_text().replace('''        methods.METHOD_WEIGHTED_FREQUENCY,
        methods.METHOD_WEIGHTED_FREQUENCY,''','''        methods.METHOD_BALANCE,
        methods.METHOD_WEIGHTED_FREQUENCY,''')
a=s.index('def test_selected_median_requires_two_other_methods():');b=s.index('\ndef test_selected_median_uses',a)
s=s[:a]+'''def test_selected_median_waits_when_retirement_leaves_one_source():
    history = _history(120)
    result = analysis.build_analysis(history, (methods.METHOD_WEIGHTED_FREQUENCY, methods.METHOD_SELECTED_MEDIAN))
    assert len(result.recommendations) == 1
    assert result.summary['selected_median_consensus']['status'] == 'waiting_for_sources'

''' + s[b:]
s=s.replace('(*methods.DEFAULT_METHOD_IDS, methods.METHOD_SELECTED_MEDIAN)', '(methods.METHOD_UNIFORM_FISHER_YATES, methods.METHOD_UNIFORM_FLOYD, methods.METHOD_SELECTED_MEDIAN)').replace('consensus.details["consensus_source_count"] == len(methods.DEFAULT_METHOD_IDS)', 'consensus.details["consensus_source_count"] == 2');p.write_text(s)
p=C/'config_flow.py';s=p.read_text().replace('normalize_method_ids(options.get(CONF_SELECTED_METHODS, DEFAULT_METHOD_IDS))', 'normalize_method_ids(list(options.get(CONF_SELECTED_METHODS, DEFAULT_METHOD_IDS)) + list(options.get("advanced_methods", [])))');p.write_text(s)
p=R/'docs/methods/public_ensemble.md';s=p.read_text().replace('분류: 추천 공개 분석식','분류: 공개 분석식').replace('‘추천 공개 분석식’은 기본 구성에 넣은 제품상 권장안이라는 뜻이지, 다른 공식보다 실제 당첨 성능이 높다고 검증했다는 뜻이 아닙니다.', '여러 지표를 조합하는 선호 공식이며, 다른 공식보다 성능이 우월한 권장안으로 표시하지 않습니다.');p.write_text(s);(C/'www/methods/public_ensemble.md').write_text(s)
(R/'scripts/smoke_match_layout.py').write_text('''"""Exact match semantics and no visual intrusion at narrow widths."""
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
''')
p=R/'scripts/smoke_ticket_panel.py';s=p.read_text().replace('from smoke_panel_validation import verify_panel_validation', 'from smoke_panel_validation import verify_panel_validation\nfrom smoke_match_layout import verify_match_layout').replace('        await verify_panel_tools(page)','        await verify_match_layout(page)\n        await verify_panel_tools(page)');p.write_text(s)
p=R/'scripts/smoke_ha_options.py';s=p.read_text();needle="        result=await flow.async_step_recommendations({const.CONF_SELECTED_METHODS:['weighted_frequency']})";assert needle in s
s=s.replace(needle,'''        advanced_result=await flow.async_step_recommendations({const.CONF_SELECTED_METHODS:['weighted_frequency'], 'advanced_methods':['uniform_floyd']})
        assert advanced_result['data'][const.CONF_SELECTED_METHODS]==['weighted_frequency','uniform_floyd']
        assert 'advanced_methods' not in advanced_result['data']
''' +needle);p.write_text(s)
