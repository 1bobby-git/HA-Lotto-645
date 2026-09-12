"""Headless browser smoke using synthetic fixtures; no public/HA network calls."""
from __future__ import annotations
import asyncio
from pathlib import Path
import tempfile

import qrcode
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'custom_components/lotto_645/www'

async def run():
    async with async_playwright() as pw:
            browser=await pw.chromium.launch(**({'executable_path':'/usr/bin/chromium'} if Path('/usr/bin/chromium').exists() else {}),args=['--no-sandbox'])
            page=await browser.new_page()
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('dialog',lambda dialog:dialog.accept())
            await page.set_content('<!DOCTYPE html><html><body></body></html>')
            await page.add_script_tag(content=(WWW/'jsQR.js').read_text())
            await page.add_script_tag(content=(WWW/'lotto-panel.js').read_text().replace("import './jsQR.js';",''))
            await page.evaluate("""async () => {
              window.requests=[];window.saved={};
              window.el=document.createElement('lotto-ticket-panel');document.body.replaceChildren(el);
              el.panel={config:{entries:{test:'테스트 로또'}}};
              el.hass={callWS:async (msg)=>{
                requests.push(msg);
                if(msg.type==='lotto_645/qr_preview'){
                  if(msg.qr!=='https://qr.dhlottery.co.kr/?v=1241q010715243345n000000000000n000000000000n000000000000n000000000000000000000000000000')throw Error('decoded QR differs');
                  return {round:1241,game_count:1,values:{game_a:'1, 7, 15, 24, 33, 45'},revision:'',will_replace:false};
                }
                if(msg.type==='lotto_645/purchases_save'){saved=msg.values;}
                return {round:msg.round||1241,revision:'',values:saved,stored_rounds:Object.keys(saved).length?[1241]:[],purchased:{games:[]},draw:{numbers:[11,13,19,20,31,44],bonus:27},result_round:1240,result_verification:{status:'official_history'},winning:null,recommendation_target:1241};
              }};
            }""")
            await page.get_by_role('heading',name='1240회 추첨번호').wait_for()
            with tempfile.TemporaryDirectory() as tmp:
                file=Path(tmp)/'fixture.png'
                qrcode.make('https://qr.dhlottery.co.kr/?v=1241q010715243345n000000000000n000000000000n000000000000n000000000000000000000000000000').save(file)
                await page.locator('#file').set_input_files(str(file))
                await page.wait_for_function("el.shadowRoot.getElementById('game_a').value === '1, 7, 15, 24, 33, 45'")
            assert not await page.evaluate("requests.some(r=>r.type==='lotto_645/purchases_save')")
            await page.locator('#save').click()
            await page.wait_for_function("requests.some(r=>r.type==='lotto_645/purchases_save')")
            saves=await page.evaluate("requests.filter(r=>r.type==='lotto_645/purchases_save')")
            assert saves[-1]['round']==1241
            assert 'qr' not in saves[-1]
            assert saves[-1]['values']['game_a']=='1, 7, 15, 24, 33, 45'
            # Current review/fast results continue to update while purchase edits stay intact.
            await page.evaluate("""async()=>{
                const base=el._hass.callWS;
                el._hass.callWS=async msg=>({...await base(msg),
                    result_round:1241,draw:{numbers:[7,13,16,23,24,43],bonus:9},
                    result_verification:{status:'provisional'},
                    reviews:[{method_id:'test',display_name:'★4.5 · 90.0점 | 시험',reviewed_rounds:2}],
                    review_round:{round:1241,status:'provisional',peer_count:1,methods:[{method_id:'test',review_score:85,exact_match_count:5,near_match_count:1,rank_this_round:1}]}});
                el.node('game_a').value='2, 3, 4, 5, 6, 7';el._editing=true;
                await el.refreshStatus();
            }""")
            await page.get_by_role('heading',name='1241회 추첨번호').wait_for()
            assert await page.locator('#game_a').input_value()=='2, 3, 4, 5, 6, 7'
            assert '★4.5' in await page.locator('#reviews').inner_text()
            assert '잠정' in await page.locator('#reviews').inner_text()
            assert not errors, errors
            await browser.close()
            print('PASS: browser loads local jsQR, decodes photo locally, previews without save, confirms explicit A-E save')

if __name__=='__main__':asyncio.run(run())
