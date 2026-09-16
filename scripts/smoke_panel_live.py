"""Exercise live recommendations in the actual first-party ES modules."""
import asyncio

async def verify_live_sync(page):
    await page.evaluate('''() => {
      el._editing=false;if(el.node('editor').open)el.node('editor').close();el.showScreen('home');
      window.liveHandlers=new Map();window.readyHandlers=new Set();window.unsubscribed=0;window.liveReads=0;
      window.liveRows=[{method_id:'uniform_fisher_yates',label:'균등 공식',numbers:[1,8,16,23,34,44]}];
      window.liveResponse=msg=>({entry_id:msg.entry_id,round:1241,revision:'server-revision',values:{game_a:'6, 7, 8, 9, 10, 11'},stored_rounds:[1241],
        purchased:{games:[]},result_round:1240,result_verification:{status:'official_history'},draw:{numbers:[4,10,20,30,40,43],bonus:9},
        recommendation_target:1241,recommendations:structuredClone(msg.entry_id==='other'?[{method_id:'uniform_floyd',label:'다른 통합',numbers:[5,12,18,27,35,45]}]:liveRows),
        winning:{round:1240,status:'evaluated',winning_game_count:0,results:[{method_id:'uniform_fisher_yates',sensor_name:'이전 추천',recommended_numbers:[3,11,19,28,36,42],source:'local',prize:'미당첨',main_match_count:0,prize_rank:null}]},reviews:[]});
      window.liveConnection={
        subscribeMessage:async(fn,msg)=>{const token=Symbol();liveHandlers.set(token,{fn,msg});return()=>{unsubscribed++;liveHandlers.delete(token);};},
        addEventListener:(type,fn)=>{if(type==='ready')readyHandlers.add(fn);},
        removeEventListener:(type,fn)=>readyHandlers.delete(fn)
      };
      window.liveWS=async msg=>{liveReads++;return liveResponse(msg);};
      el.hass={...el._hass,connection:liveConnection,callWS:msg=>liveWS(msg)};
      window.invalidate=id=>{for(const {fn} of liveHandlers.values())fn({entry_id:id});};
    }''')
    await page.wait_for_function("!el._busy && el.node('current-recommendations').querySelectorAll('.ball').length===6")
    assert '1241' in await page.locator('#current-title').text_content()
    assert '이전 추천' in await page.locator('#predictions').text_content()
    assert '이전 추천' not in await page.locator('#current-recommendations').text_content()
    reads=await page.evaluate('liveReads')
    await page.evaluate("invalidate('unrelated')")
    await page.wait_for_timeout(60)
    assert await page.evaluate('liveReads')==reads
    await page.evaluate("liveRows[0].numbers=[2,9,17,24,33,41];invalidate('test')")
    await page.wait_for_function("!el._busy && el.node('current-recommendations').querySelector('.ball').textContent==='2'")
    await page.evaluate("liveRows.push({method_id:'constraint_uniform',label:'조건 지정 균등 생성',numbers:[7,15,22,26,38,43]});invalidate('test')")
    await page.wait_for_function("el.node('current-count').textContent==='2개 공식'")
    await page.evaluate("liveRows.pop();invalidate('test')")
    await page.wait_for_function("!el._busy && el.node('current-count').textContent==='1개 공식'")
    # Network invalidations cannot overwrite the editor or its concurrency revision.
    await page.evaluate("el._editing=true;el.node('game_a').value='1, 2, 3, 4, 5, 6';el._revision='draft-revision';invalidate('test')")
    await page.wait_for_timeout(100)
    assert await page.evaluate("el.node('game_a').value==='1, 2, 3, 4, 5, 6' && el._revision==='draft-revision'")
    await page.evaluate('''() => {
      el._editing=false;window.releaseLive=null;window.holdLive=true;
      window.liveWS=async msg=>{liveReads++;const answer=liveResponse(msg);if(holdLive){holdLive=false;await new Promise(resolve=>releaseLive=resolve);}return answer;};
      invalidate('test');
    }''')
    await page.wait_for_function('Boolean(releaseLive) && el._busy')
    reads=await page.evaluate('liveReads')
    await page.evaluate("liveRows[0].numbers=[3,8,17,26,37,42];for(let n=0;n<20;n++)invalidate('test');releaseLive()")
    await page.wait_for_function("!el._busy && el.node('current-recommendations').querySelector('.ball').textContent==='3'")
    assert await page.evaluate('liveReads')==reads+1
    # Entry changes discard in-flight old responses and load the selected entry.
    await page.evaluate('''() => {
      el.panel={config:{entries:{test:'원래 통합',other:'다른 통합'}}};
      holdLive=true;releaseLive=null;invalidate('test');
    }''')
    await page.wait_for_function('Boolean(releaseLive) && el._busy')
    await page.evaluate("el.node('entry').value='other';el.node('entry').dispatchEvent(new Event('change'));releaseLive()")
    await page.wait_for_function("!el._busy && el.node('current-recommendations').textContent.includes('다른 통합')")
    assert await page.evaluate("el.node('entry').value==='other' && !el.node('current-recommendations').textContent.includes('균등 공식')")
    reads=await page.evaluate('liveReads')
    await page.evaluate('for(const fn of readyHandlers)fn()')
    await page.wait_for_function(f'liveReads>{reads} && !el._busy')
    for width in (320,360,1280):
        await page.set_viewport_size({'width':width,'height':900})
        await page.evaluate('(value)=>el.narrow=value',width<870)
        assert await page.evaluate('el.scrollWidth<=el.clientWidth+1'),width
        assert await page.locator('#current-recommendations .ball').count()==6
    assert await page.locator('#tab-validation').count()==0
    # Unsubscribe and restore after navigation; no detached DOM updates.
    before=await page.evaluate('unsubscribed')
    await page.evaluate('el.remove()')
    await page.wait_for_function(f'unsubscribed>{before} && liveHandlers.size===0')
    await page.evaluate('document.body.append(el)')
    await page.wait_for_function("liveHandlers.size===1 && !el._busy")
    await page.evaluate("el.panel={config:{entries:{other:'다른 통합',newentry:'추가 통합'}}}")
    assert await page.evaluate("el.node('entry').value==='other' && el.node('entry').options.length===2")
    print('PASS: live recommendation/source separation, addition/removal, draft preservation, coalescing, stale entry response, reconnect, unsubscribe and 320/360/1280px layouts')
