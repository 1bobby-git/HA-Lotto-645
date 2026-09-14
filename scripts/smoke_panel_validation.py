"""Production modules: on-demand historical UI, isolation and stale replies."""
from __future__ import annotations
import os
from pathlib import Path
from smoke_panel_tools import guide_catalog

async def verify_panel_validation(page):
    await page.evaluate('''catalog => {
      if(!el.isConnected)(document.querySelector('#allocated ha-panel-custom')||document.body).append(el);
      window.validationCalls=[];const oldWS=el._hass.callWS;
      window.validationBase={...el._latestToolsData,method_catalog:catalog,
        historical_validation:{min_round:31,max_round:1241,saju_profile_ready:false,
        default_method_ids:['weighted_frequency','uniform_floyd','selected_median_consensus']}};
      window.validationResponse={mode:'historical_validation',simulation:true,counts_toward_reviews:false,persisted:false,
        target_round:1200,based_on_round:1199,training_last_round:1199,training_draw_count:1199,
        component_version:'1.15.0',generated_at:'2026-09-14T10:00:00Z',training_sha256:'a'.repeat(64),
        checked_game_count:3,unavailable_game_count:0,winning_game_count:2,highest_prize:'2등',
        draw:{round:1200,draw_date:'2025-11-29',numbers:[7,24,30,31,32,42],bonus:9},
        results:[
          {method_id:'weighted_frequency',sensor_name:'공개 공식 · 가중 빈도',source:'historical_validation',generation_status:'generated',recommended_numbers:[7,13,15,24,38,42],prize:'5등',prize_rank:5,main_match_count:3,matched_main_numbers:[7,24,42],bonus_match:false,matched_bonus_number:null},
          {method_id:'uniform_floyd',sensor_name:'균등 공식 · Floyd',source:'historical_validation',generation_status:'generated',recommended_numbers:[7,9,24,30,31,32],prize:'2등',prize_rank:2,main_match_count:5,matched_main_numbers:[7,24,30,31,32],bonus_match:true,matched_bonus_number:9},
          {method_id:'selected_median_consensus',sensor_name:'합의 추천 · 선택 공식 중앙값',source:'historical_validation',generation_status:'generated',recommended_numbers:[8,11,19,27,34,43],prize:'미당첨',prize_rank:null,main_match_count:0,matched_main_numbers:[],bonus_match:false,matched_bonus_number:null}],
        notice:'검증용 시뮬레이션 · 실제 추천번호·당첨 기록·리뷰 점수에 반영하지 않습니다.'};
      el._hass.callWS=async msg=>{
        if(msg.type!=='lotto_645/historical_validate')return oldWS(msg);
        validationCalls.push(structuredClone(msg));
        if(window.delayValidation)return new Promise((resolve,reject)=>{window.resolveValidation=resolve;window.rejectValidation=reject;});
        return structuredClone(validationResponse);
      };
      el.updateResults(validationBase);el._clearSmartSync();el.showScreen('home');
      window.liveBeforeValidation=['predictions','reviews','wallet-games'].map(id=>el.node(id).innerHTML);
    }''',guide_catalog())
    await page.set_viewport_size({'width':1000,'height':900})
    await page.locator('#tab-validation').click()
    assert await page.locator('#screen-validation').is_visible()
    assert await page.evaluate('validationCalls.length')==0
    assert await page.locator('#validation-round').input_value()=='1241'
    assert await page.locator('#validation-seed').count()==0
    assert '3개' in await page.locator('#validation-method-count').text_content()
    await page.locator('#validation-round').fill('1200')
    assert '1~1199회' in await page.locator('#validation-cutoff').text_content()
    await page.locator('#validation-run').click()
    await page.wait_for_function("el.node('validation-output').hidden===false")
    assert await page.evaluate('validationCalls.length')==1
    req=await page.evaluate('validationCalls[0]')
    assert req['round']==1200 and 'seed' not in req and len(req['method_ids'])==3
    assert await page.locator('#validation-results tr').count()==3
    assert '실제 추천과 별도' in await page.locator('#validation-title').text_content()
    assert '1~1199회' in await page.locator('#validation-meta').text_content()
    assert await page.locator('#validation-results .ball[data-hit="main"]').count()==8
    assert await page.locator('#validation-results .ball[data-hit="bonus"]').count()==1
    assert await page.evaluate("JSON.stringify(liveBeforeValidation)===JSON.stringify(['predictions','reviews','wallet-games'].map(id=>el.node(id).innerHTML))")
    assert await page.locator('#validation-run').is_enabled()
    await page.locator('#validation-results [data-method-id="weighted_frequency"]').click()
    await page.wait_for_function("tools.dialog.open && !tools.shadowRoot.querySelector('.method-body').hasAttribute('aria-busy')")
    await page.keyboard.press('Escape')
    assert await page.evaluate('validationCalls.length')==1
    await page.locator('#validation-run').click()
    await page.wait_for_function('validationCalls.length===2 && !el._historicalValidation.busy')
    assert 'seed' not in await page.evaluate('validationCalls[1]')
    await page.evaluate('el.updateResults(validationBase);el._clearSmartSync()')
    assert not await page.locator('#validation-output').evaluate('n=>n.hidden')
    for dark in (False,True):
        await page.evaluate('(dark)=>{el.hass={...el._hass,themes:{darkMode:dark}};el._clearSmartSync()}',dark)
        for width in (320,390,768,1366):
            await page.set_viewport_size({'width':width,'height':1000})
            await page.evaluate('el.showScreen("validation");el.scrollTop=0')
            assert await page.evaluate('el.scrollWidth<=el.clientWidth+1'), (dark,width)
            for selector in ['#validation-form','#validation-output']:
                fits=await page.locator(selector).evaluate('n=>n.scrollWidth<=n.clientWidth+1')
                if not fits:
                    print('OVERFLOW',dark,width,selector,await page.locator(selector).evaluate("n=>({outer:n.getBoundingClientRect().toJSON(),scroll:n.scrollWidth,children:[...n.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>n.getBoundingClientRect().right).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,50),rect:e.getBoundingClientRect().toJSON()}))})"),flush=True)
                    if directory:=os.environ.get('LOTTO_SCREENSHOT_DIR'):
                        Path(directory).mkdir(parents=True,exist_ok=True)
                        await page.screenshot(path=str(Path(directory)/'historical-overflow.png'))
                assert fits, (dark,width,selector)
    await page.emulate_media(forced_colors='active')
    assert await page.locator('#validation-results .ball[data-hit="miss"]').first.evaluate("n=>getComputedStyle(n).opacity==='1'")
    await page.emulate_media(forced_colors='none')
    if directory:=os.environ.get('LOTTO_SCREENSHOT_DIR'):
        Path(directory).mkdir(parents=True,exist_ok=True)
        await page.set_viewport_size({'width':430,'height':1150})
        await page.evaluate('el.hass={...el._hass,themes:{darkMode:false}};el._clearSmartSync();el.scrollTop=0')
        await page.screenshot(path=str(Path(directory)/'historical-validation-mobile.png'))
        await page.locator('#validation-output').scroll_into_view_if_needed()
        await page.screenshot(path=str(Path(directory)/'historical-validation-results.png'))
    await page.set_viewport_size({'width':1000,'height':900})
    await page.locator('#validation-round').fill('1199')
    assert await page.locator('#validation-output').evaluate('n=>n.hidden')
    await page.evaluate('window.delayValidation=true')
    await page.locator('#validation-run').click()
    await page.wait_for_function('Boolean(window.resolveValidation)')
    assert await page.locator('#validation-run').is_disabled()
    await page.evaluate('''() => {
      const o=document.createElement('option');o.value='validation-second';o.textContent='Second';el.node('entry').append(o);el.node('entry').value=o.value;
      el.updateResults({...validationBase,historical_validation:{...validationBase.historical_validation,max_round:1100}});
      resolveValidation(structuredClone(validationResponse));el._clearSmartSync();
    }''')
    await page.wait_for_timeout(30)
    assert await page.locator('#validation-output').evaluate('n=>n.hidden')
    assert await page.locator('#validation-round').input_value()=='1100'
    assert await page.locator('#validation-run').is_enabled()
    await page.locator('#validation-run').click()
    await page.wait_for_function('el._historicalValidation.busy')
    await page.evaluate("rejectValidation(new Error('검증 테스트 오류'))")
    await page.wait_for_function('!el._historicalValidation.busy')
    assert '검증 테스트 오류' in await page.locator('#validation-status').text_content()
    assert await page.locator('#validation-output').evaluate('n=>n.hidden')
    await page.evaluate('el._clearSmartSync()')
    print('PASS: historical tab, explicit-only requests, holdout metadata, match visuals, repeat, no live review/wallet mutation, responsive themes, forced colors, stale-entry response rejection and error recovery')
