"""Production UI: unified ranks, contrast, reset, consent and honest review import."""
from __future__ import annotations
import os
from pathlib import Path
from smoke_panel_tools import guide_catalog


async def verify_panel_validation(page):
    await page.evaluate('''catalog => {
      if(!el.isConnected)(document.querySelector('#allocated ha-panel-custom')||document.body).append(el);
      window.validationCalls=[];window.importCalls=[];
      window.validationBase={...el._latestToolsData,result_round:1241,result_verification:{status:'official_history'},method_catalog:catalog,
        reviews:['weighted_frequency','uniform_floyd','selected_median_consensus'].map(id=>({method_id:id,label:id,display_name:id,reviewed_rounds:6})),
        historical_validation:{min_round:31,max_round:1241,saju_profile_ready:false,
          default_method_ids:['weighted_frequency','uniform_floyd','selected_median_consensus']}};
      window.validationResponse={mode:'historical_validation',simulation:true,counts_toward_reviews:false,persisted:false,
        target_round:1200,based_on_round:1199,training_last_round:1199,training_draw_count:1199,
        component_version:'1.19.0',generated_at:'2026-09-15T00:00:00Z',training_sha256:'a'.repeat(64),
        checked_game_count:3,unavailable_game_count:0,winning_game_count:2,highest_prize:'2등',
        draw:{round:1200,draw_date:'2025-11-29',numbers:[7,24,30,31,32,42],bonus:9},
        results:[
          {method_id:'weighted_frequency',sensor_name:'공개 공식 · 가중 빈도',generation_status:'generated',recommended_numbers:[7,13,15,24,38,42],prize:'5등',prize_rank:5,main_match_count:3,matched_main_numbers:[7,24,42],bonus_match:false,matched_bonus_number:null},
          {method_id:'uniform_floyd',sensor_name:'균등 공식 · Floyd',generation_status:'generated',recommended_numbers:[7,9,24,30,31,32],prize:'2등',prize_rank:2,main_match_count:5,matched_main_numbers:[7,24,30,31,32],bonus_match:true,matched_bonus_number:9},
          {method_id:'selected_median_consensus',sensor_name:'합의 추천 · 선택 공식 중앙값',generation_status:'generated',recommended_numbers:[8,11,19,27,34,43],prize:'미당첨',prize_rank:null,main_match_count:0,matched_main_numbers:[],bonus_match:false,matched_bonus_number:null}]};
      window.score={total_runs:20,unique_rounds:20,unimported_runs:20,cycle_round:1241,cycle_id:'cycle-1',revision:'a'.repeat(64),baseline_hit_rate:2.38341,comparable_rounds:false,
        methods:validationResponse.results.map((r,i)=>({method_id:r.method_id,label:r.sensor_name,generated:20,attempts:20,unavailable:0,three_plus_hits:1,
          points:[3,10,1][i],points_per_100:[15,50,5][i],best_match:[4,5,3][i],match_3:i===2?1:0,match_4:i===0?1:0,match_5:i===1?1:0,match_6:0,
          hit_rate:5,unique_rounds:20,interval_99:[.5,25],sample_notice:'표본 부족',formula_versions:['v1']}))};
      window.validationState={status:'idle',validation_scoreboard:structuredClone(score)};
      const oldWS=el._hass.callWS;
      el._hass.callWS=async msg=>{
        if(msg.type==='lotto_645/historical_validation_state')return structuredClone(validationState);
        if(msg.type==='lotto_645/historical_validation_import'){
          importCalls.push(structuredClone(msg));if(msg.revision!==score.revision)throw Error('validation_revision_conflict');
          validationBase.reviews=validationBase.reviews.map(r=>({...r,historical_review:structuredClone(score.methods.find(m=>m.method_id===r.method_id))}));
          score.unimported_runs=0;validationState.validation_scoreboard=structuredClone(score);
          return {...structuredClone(validationBase),validation_scoreboard:structuredClone(score)};
        }
        if(msg.type!=='lotto_645/historical_validate')return oldWS(msg);
        validationCalls.push(structuredClone(msg));
        if(window.delayValidation)return new Promise((resolve,reject)=>{window.resolveValidation=resolve;window.rejectValidation=reject;});
        score.total_runs++;score.unimported_runs++;score.revision=String(score.total_runs).padStart(64,'0');
        const response={...structuredClone(validationResponse),validation_cycle:score.cycle_id,validation_scoreboard:structuredClone(score)};
        validationState={status:'completed',round:1200,method_ids:msg.method_ids,result:response,validation_scoreboard:structuredClone(score)};
        return response;
      };
      el.updateResults(validationBase);el._clearSmartSync();el.showScreen('home');
      window.liveBeforeValidation=['predictions','reviews','wallet-games'].map(id=>el.node(id).innerHTML);
    }''', guide_catalog())
    await page.set_viewport_size({'width':1000,'height':900})
    await page.locator('#tab-validation').click()
    await page.wait_for_timeout(20)
    assert await page.evaluate('validationCalls.length') == 0
    assert await page.locator('#validation-seed').count() == 0
    await page.locator('#validation-round').fill('1200')
    assert '1~1199회' in await page.locator('#validation-cutoff').text_content()
    await page.locator('#validation-run').click()
    await page.wait_for_function('!el._historicalValidation.busy && !el.node("validation-output").hidden')
    assert await page.evaluate('validationCalls.length') == 1
    assert 'seed' not in await page.evaluate('validationCalls[0]')
    assert await page.locator('#validation-results > .prediction-row').count() == 3
    assert await page.locator('#validation-scoreboard,.validation-score-card').count() == 0
    assert await page.locator('#validation-results .ball[data-hit="main"]').count() == 8
    assert await page.locator('#validation-results .ball[data-hit="bonus"]').count() == 1
    assert '21회' in await page.locator('#validation-total').text_content()
    assert '회차가 달라' in await page.locator('#validation-assessment').text_content()
    assert '초기화' in await page.locator('#validation-reset-notice').text_content()
    assert await page.evaluate("JSON.stringify(liveBeforeValidation)===JSON.stringify(['predictions','reviews','wallet-games'].map(id=>el.node(id).innerHTML))")
    assert await page.locator('#validation-results > .prediction-row').first.get_attribute('data-method-id') == 'uniform_floyd'
    await page.locator('#validation-sort').select_option('current')
    assert await page.locator('#validation-results > .prediction-row').first.get_attribute('data-method-id') == 'uniform_floyd'
    await page.locator('#validation-sort').select_option('efficiency')
    assert await page.locator('#validation-results > .prediction-row').first.get_attribute('data-rank') == '1'
    await page.evaluate('el._historicalValidation.restoreLatest()')
    assert await page.evaluate('validationCalls.length') == 1
    assert await page.locator('#validation-results > .prediction-row').count() == 3
    # Pure ranking ties and spreadsheet-formula escaping execute in the real module.
    assert await page.evaluate('''async()=>{
      const m=await import('/lotto_645_static/lotto-panel-validation.js?v=1.20.0');
      const rows=m.rankedRows([],[{method_id:'a',points:2},{method_id:'b',points:2},{method_id:'c',points:1}]);
      return rows.map(r=>r.rank).join(',')==='1,1,3' && rows[0].tied && m.csvCell('=SUM(1)').startsWith('"\\\'');
    }''')
    for dark in (False, True):
        await page.evaluate('(dark)=>{el.hass={...el._hass,themes:{darkMode:dark}};el._clearSmartSync()}', dark)
        for width in (320,360,390,768,1440):
            await page.set_viewport_size({'width':width,'height':1000})
            await page.evaluate('el.showScreen("validation")')
            for selector in ('#screen-validation','#validation-form','#validation-output'):
                assert await page.locator(selector).evaluate('n=>n.scrollWidth<=n.clientWidth+1'), (dark,width,selector)
            assert await page.locator('#validation-run').evaluate('n=>n.getBoundingClientRect().height>=44')
            contrasts=await page.evaluate('''()=>[...el.node('validation-results').children].map(tr=>{
              const lum=s=>s.match(/[\\d.]+/g).slice(0,3).map(v=>Number(v)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
              const bg=lum(getComputedStyle(tr.cells[0]).backgroundColor);
              return [...tr.querySelectorAll('.validation-rank,.validation-points,.method-info-trigger,.validation-prize')].map(n=>{
                const fg=lum(getComputedStyle(n).color);return (Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05);
              });
            })''')
            assert all(value>=4.5 for row in contrasts for value in row), (dark,width,contrasts)
    await page.emulate_media(forced_colors='active')
    assert await page.locator('#validation-results .ball[data-hit="miss"]').first.evaluate("n=>getComputedStyle(n).opacity==='1'")
    await page.emulate_media(forced_colors='none')
    if directory := os.environ.get('LOTTO_SCREENSHOT_DIR'):
        Path(directory).mkdir(parents=True,exist_ok=True)
        for width,name in ((390,'mobile'),(1440,'desktop')):
            await page.set_viewport_size({'width':width,'height':1100})
            await page.evaluate('el.hass={...el._hass,themes:{darkMode:false}};el._clearSmartSync()')
            await page.locator('#validation-output').scroll_into_view_if_needed()
            await page.screenshot(path=str(Path(directory)/f'validation-unified-{name}.png'))
    await page.evaluate("window.originalConfirm=window.confirm;window.confirm=text=>{window.confirmText=text;return false;}")
    await page.locator('#validation-import').click()
    assert await page.evaluate('importCalls.length') == 0
    assert '미적중·생성 불가' in await page.evaluate('confirmText')
    await page.evaluate('window.confirm=()=>true')
    await page.locator('#validation-import').click()
    await page.wait_for_function('importCalls.length===1 && !el._historicalValidation.importing')
    await page.evaluate('window.confirm=originalConfirm')
    assert (await page.evaluate('importCalls[0]'))['confirmed'] is True
    assert await page.locator('#validation-import').is_disabled()
    assert await page.locator('#reviews .validation-import-note').count() == 3
    assert await page.evaluate('validationBase.reviews.every(r=>r.reviewed_rounds===6)')
    await page.locator('#tab-review').click()
    await page.locator('#validation-review-order select').select_option('historical')
    assert await page.locator('#reviews tr').first.get_attribute('data-review-method') == 'uniform_floyd'
    await page.locator('#tab-validation').click()
    async with page.expect_download() as download_info:
        await page.locator('#validation-export').click()
    download = await download_info.value
    assert download.suggested_filename == 'lotto-validation-1241.csv'
    # Announced new official round invalidates the cycle, not imported evidence.
    await page.evaluate('''()=>{
      score={...score,total_runs:0,unique_rounds:0,unimported_runs:0,cycle_round:1242,cycle_id:'cycle-2',methods:[],reset_at:'2026-09-19T12:00:00Z'};
      validationState={status:'idle',validation_scoreboard:structuredClone(score)};
      validationBase={...validationBase,result_round:1242,historical_validation:{...validationBase.historical_validation,max_round:1242}};
      el.updateResults(validationBase);el._clearSmartSync();
    }''')
    await page.wait_for_function('el._historicalValidation.score?.cycle_round===1242')
    assert '총 0회' in await page.locator('#validation-total').text_content()
    assert await page.locator('#validation-results .ball').count() == 0
    assert await page.locator('#reviews .validation-import-note').count() == 3
    assert await page.locator('#validation-import').is_disabled()
    # Stale asynchronous response cannot populate another entry's validation list.
    await page.locator('#validation-round').fill('1200')
    await page.evaluate('window.delayValidation=true')
    await page.locator('#validation-run').click()
    await page.wait_for_function('Boolean(window.resolveValidation)')
    await page.evaluate('''()=>{
      const o=document.createElement('option');o.value='validation-second';o.textContent='Second';el.node('entry').append(o);el.node('entry').value=o.value;
      el.updateResults({...validationBase,historical_validation:{...validationBase.historical_validation,max_round:1100}});
      resolveValidation(structuredClone(validationResponse));el._clearSmartSync();
    }''')
    await page.wait_for_timeout(30)
    assert await page.locator('#validation-results .ball').count() == 0
    assert await page.locator('#validation-round').input_value() == '1100'
    await page.locator('#validation-run').click()
    await page.wait_for_function('el._historicalValidation.busy')
    await page.evaluate("rejectValidation(new Error('검증 테스트 오류'))")
    await page.wait_for_function('!el._historicalValidation.busy')
    assert '검증 테스트 오류' in await page.locator('#validation-status').text_content()
    await page.evaluate('el._clearSmartSync()')
    assert await page.evaluate('''async()=>{
      const m=await import('/lotto_645_static/lotto-panel-validation.js?v=1.20.0');
      const stale=el._historicalValidation;
      stale.runtimeVersion='1.18.1';
      m.applyHistoricalValidation(el);
      return el._historicalValidation!==stale
        && el._historicalValidation.runtimeVersion==='1.20.0'
        && el._historicalValidation.form===el.node('validation-form')
        && el.shadowRoot.querySelectorAll('#validation-sort').length===1
        && el.shadowRoot.querySelectorAll('#validation-total').length===1
        && el.shadowRoot.querySelectorAll('#validation-import').length===1
        && el.shadowRoot.querySelectorAll('#validation-export').length===1
        && el.shadowRoot.querySelectorAll('#validation-assessment').length===1;
    }''')
    await page.wait_for_timeout(20)
    print('PASS: unified compact ranks, hot-upgrade controller replacement, 10 theme/width combinations, >=4.5 contrast, reset, consent/cancel, review provenance, CSV, stale-entry and error recovery')
