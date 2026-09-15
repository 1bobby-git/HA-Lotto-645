"""Full-width disclosures and exact server-generated historical hit fixtures."""
from __future__ import annotations
import importlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]


def fixture():
    for name,path in [('custom_components',ROOT/'custom_components'),('custom_components.lotto_645',ROOT/'custom_components/lotto_645')]:
        m=ModuleType(name);m.__path__=[str(path)];sys.modules.setdefault(name,m)
    scores=importlib.import_module('custom_components.lotto_645.historical_validation_scores')
    models=importlib.import_module('custom_components.lotto_645.models')
    evaluator=importlib.import_module('custom_components.lotto_645.result_evaluator').evaluate_ticket
    draw=models.LottoDraw(1200,'2025-11-29',(7,24,30,31,32,42),9)
    labels={'weighted_frequency':'공개 공식 · 가중 빈도','uniform_floyd':'균등 공식 · Floyd',
            'uniform_rejection':'균등 공식 · 중복거부','uniform_sequential':'균등 공식 · 순차 포함'}
    tickets={'three':[7,13,15,24,38,42],'four':[7,13,24,30,38,42],
             'bonus':[7,9,13,24,38,42],'second':[7,9,24,30,31,32],
             'third':[7,24,30,31,32,38],'first':[7,24,30,31,32,42],'zero':[1,2,3,4,5,6]}
    def result(pairs):
        rows=[{'method_id':method,'sensor_name':labels[method],'generation_status':'generated',
               'formula_version':1,'recommended_numbers':tickets[kind],**evaluator(tuple(tickets[kind]),draw)} for method,kind in pairs]
        winners=[r for r in rows if r['prize_rank'] is not None]
        return {'mode':'historical_validation','counts_toward_reviews':False,'persisted':False,
                'target_round':1200,'based_on_round':1199,'training_last_round':1199,'training_draw_count':1199,
                'generated_at':'2026-09-15T01:00:00Z','training_sha256':'a'*64,'component_version':'1.17.1',
                'results':rows,'draw':draw.to_storage(),'checked_game_count':len(rows),'unavailable_game_count':0,
                'winning_game_count':len(winners),'highest_prize':min(winners,key=lambda r:r['prize_rank'])['prize'] if winners else None}
    p=scores.rotate(scores._empty(),1241)
    runs=[('weighted_frequency','three'),('uniform_floyd','second'),('weighted_frequency','zero'),
          ('uniform_rejection','zero'),('weighted_frequency','four'),('uniform_floyd','third'),
          ('uniform_floyd','first'),('weighted_frequency','bonus')]+[('weighted_frequency','three')]*12
    for pair in runs:p=scores.apply_result(p,result([pair]))
    latest=result([(key,'zero') for key in labels]);p=scores.apply_result(p,latest)
    return {**latest,'validation_cycle':p['cycle_id'],'validation_scoreboard':scores.summary(p)}


async def verify_validation_details(page):
    data=fixture()
    await page.evaluate('''data=>{
      window.detailFixture=data;
      const old=el._hass.callWS;window.detailOldWS=old;
      el._hass.callWS=async msg=>msg.type==='lotto_645/historical_validation_state'
        ?{status:'completed',round:data.target_round,method_ids:data.results.map(r=>r.method_id),result:structuredClone(data)}:old(msg);
      const base={...el._latestToolsData,result_round:1241,result_verification:{status:'official_history'},
        historical_validation:{min_round:31,max_round:1241,saju_profile_ready:false,default_method_ids:['weighted_frequency','uniform_floyd']},
        method_catalog:data.results.map(r=>({method_id:r.method_id,name:r.sensor_name}))};
      el.updateResults(base);el._historicalValidation.render(data);el.showScreen('validation');el._clearSmartSync();
    }''',data)
    await page.set_viewport_size({'width':1366,'height':1000})
    primary=page.locator('#validation-results > .prediction-row[data-method-id="weighted_frequency"]')
    toggle=primary.locator('.validation-detail-toggle')
    detail=page.locator('#validation-results > .validation-detail-row[data-details-for="weighted_frequency"]')
    assert await toggle.get_attribute('aria-expanded')=='false'
    assert await detail.is_hidden() and await detail.locator('.validation-hit').count()==0
    height=await primary.evaluate('n=>n.getBoundingClientRect().height')
    await toggle.focus();await page.keyboard.press('Enter')
    assert await toggle.get_attribute('aria-expanded')=='true'
    assert await detail.is_visible()
    assert await detail.locator('td').get_attribute('colspan')=='3'
    assert await detail.locator('.validation-detail-body').get_attribute('id')==await toggle.get_attribute('aria-controls')
    assert await primary.evaluate('n=>n.getBoundingClientRect().height')==height
    assert await detail.locator('.validation-hit').count()==10
    await detail.locator('.validation-hit-more').click()
    assert await detail.locator('.validation-hit').count()==15
    hit=detail.locator('.validation-hit[data-run="5"]')
    assert '5번째 검증' in await hit.text_content() and '1,200회' in await hit.text_content()
    assert await hit.locator('.ball[data-hit="main"]').all_text_contents()==['7','24','30','42']
    assert await hit.locator('.ball[data-hit="miss"]').all_text_contents()==['13','38']
    assert '4등' in await hit.locator('.validation-hit-match').text_content()
    bonus=detail.locator('.validation-hit[data-run="8"]')
    assert await bonus.locator('.ball[data-hit="bonus"]').all_text_contents()==['9']
    assert '보너스 9' in await bonus.text_content()
    # Sorting and rebuilding must keep the disclosure attached to its own formula.
    await page.locator('#validation-sort').select_option('current')
    assert await toggle.get_attribute('aria-expanded')=='true'
    assert await detail.locator('.validation-hit[data-run="5"]').count()==1
    assert await detail.evaluate("n=>n.previousElementSibling.dataset.methodId==='weighted_frequency'")
    for dark in (False,True):
        await page.evaluate('(dark)=>{el.hass={...el._hass,themes:{darkMode:dark}};el._clearSmartSync()}',dark)
        for width in (320,360,390,768,1366):
            await page.set_viewport_size({'width':width,'height':1000})
            assert await detail.evaluate('''n=>{
              const t=n.closest('table').getBoundingClientRect(),r=n.getBoundingClientRect();
              return Math.abs(r.width-t.width)<2&&Math.abs(r.left-t.left)<2&&n.scrollWidth<=n.clientWidth+1;
            }'''),(dark,width)
            assert await page.locator('#validation-output').evaluate('n=>n.scrollWidth<=n.clientWidth+1'),(dark,width)
            assert await primary.evaluate('n=>n.getBoundingClientRect().height<220'),(dark,width)
            assert await page.locator('#validation-results > .prediction-row[data-scored="false"] td').evaluate_all('''nodes=>nodes.every(n=>{
              const probe=document.createElement('span');probe.style.backgroundColor='var(--surface)';n.append(probe);
              const bg=getComputedStyle(probe).backgroundColor;probe.remove();return getComputedStyle(n).backgroundColor===bg;
            })'''),(dark,width)
            if not dark:
                assert await page.locator('#validation-results > .prediction-row[data-scored="false"] td').first.evaluate("n=>getComputedStyle(n).backgroundColor==='rgb(255, 255, 255)'")
    await page.set_viewport_size({'width':1366,'height':1000})
    await toggle.focus();await page.keyboard.press('Space')
    assert await detail.is_hidden() and await toggle.get_attribute('aria-expanded')=='false'
    assert await toggle.evaluate("n=>n.getRootNode().activeElement===n")
    await toggle.click()
    await page.emulate_media(forced_colors='active')
    assert await toggle.get_attribute('aria-expanded')=='true'
    assert '5번째 검증' in await hit.text_content()
    await page.emulate_media(forced_colors='none')
    # Fresh load of all-zero results must not paint 'joint first place' gold.
    await page.evaluate('''()=>{
      const d=structuredClone(detailFixture);d.validation_scoreboard.methods.forEach(s=>{s.points=0;s.three_plus_hits=0;s.best_match=0;s.hit_history=[]});
      el._historicalValidation.render(d);
    }''')
    assert await page.locator('#validation-results > .prediction-row[data-scored="true"]').count()==0
    # Numberless migration is honest and does not synthesize another game's balls.
    await page.evaluate('''()=>{
      const d=structuredClone(detailFixture),s=d.validation_scoreboard.methods.find(s=>s.method_id==='weighted_frequency');
      s.hit_history=[{run:1,round:1200,main_match_count:3,generated_at:'2026-09-15',details_available:false}];
      s.hit_history_omitted=14;el._historicalValidation.render(d);
    }''')
    assert '번호 기록 없음' in await detail.text_content()
    assert '14회는 상세 이력이 남아 있지 않습니다' in await detail.text_content()
    assert await detail.locator('.ball').count()==0
    # Capture representative, compact full-width layout with the real computed fixture.
    await page.evaluate('''()=>{
      el._historicalValidation.expandedMethods.clear();el._historicalValidation.detailLimits.clear();
      el.hass={...el._hass,themes:{darkMode:false}};el._clearSmartSync();el._historicalValidation.render(detailFixture);
    }''')
    await page.locator('#validation-results > .prediction-row[data-method-id="uniform_floyd"] .validation-detail-toggle').click()
    if directory:=os.environ.get('LOTTO_SCREENSHOT_DIR'):
        Path(directory).mkdir(parents=True,exist_ok=True)
        for width,name in ((390,'mobile'),(1366,'desktop')):
            await page.set_viewport_size({'width':width,'height':1000})
            await page.locator('#validation-results').evaluate("n=>n.closest('table').scrollIntoView({block:'start'})")
            await page.screenshot(path=str(Path(directory)/f'validation-full-width-{name}.png'))
    await page.evaluate('''()=>{
      el._historicalValidation.result=null;
      el._historicalValidation.score={cycle_id:'next-cycle',total_runs:0,methods:[]};
      el._historicalValidation.renderEmptyCycle();el._hass.callWS=detailOldWS;el._clearSmartSync();
    }''')
    assert await page.locator('#validation-results .validation-hit,.validation-detail-row').count()==0
    assert await page.evaluate('el._historicalValidation.expandedMethods.size')==0
    print('PASS: full-width colspan disclosure; keyboard/focus; actual persisted hit numbers and global run indices; 10 responsive/theme combinations; zero-score flat backgrounds; pagination; truthful legacy details; cycle reset')
