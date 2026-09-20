"""Real HA ES modules + real Python client/service/Core via a synthetic local harness."""
import json,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];WWW=ROOT/'custom_components/lotto_645/www'
platform=Path(os.environ.get('FORMULAB_CHECKOUT','D:/Workspace/formulab.kr'))
fixture=json.loads((platform/'.local/finalizer-fixture.json').read_text());checks=[]
def check(name,value=True):assert value,name;checks.append(name);print(name,'PASS',flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
 context.request.post(fixture['control']+'/reset',data={})
 def serve(route):
  url=urlparse(route.request.url)
  assert url.hostname=='127.0.0.1','External request is not allowed in this fixture'
  if url.path=='/':route.fulfill(content_type='text/html',body='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{height:100%;margin:0}</style><script type="module" src="/lotto_645_static/lotto-panel-shell.js"></script></head><body></body></html>')
  elif url.path=='/fixture-finalization':
   response=context.request.post(fixture['control']+'/bridge',data=route.request.post_data_json)
   route.fulfill(response=response)
  elif url.path.startswith('/lotto_645_static/'):
   file=WWW/Path(url.path).name
   assert file.is_file() and file.suffix in ('.js','.css')
   route.fulfill(path=str(file),content_type='text/css' if file.suffix=='.css' else 'text/javascript')
  elif url.path=='/lotto_645_brand/logo.png':route.fulfill(path=str(ROOT/'custom_components/lotto_645/brand/logo.png'),content_type='image/png')
  else:route.fulfill(status=404,body='Not found')
 context.route('**/*',serve);page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto('http://127.0.0.1:8765/',wait_until='domcontentloaded')
 page.wait_for_function("Boolean(customElements.get('lotto-ticket-panel'))")
 page.evaluate("""()=>{
  window.requests=[];window.el=document.createElement('lotto-ticket-panel');document.body.append(el);
  el.panel={config:{entries:{test:'합성 테스트 통합'}}};
  el.hass={themes:{darkMode:false},user:{is_admin:true},callWS:async msg=>{
   requests.push(structuredClone(msg));
   if(msg.type==='lotto_645/finalization'){
    const response=await fetch('/fixture-finalization',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(msg)});
    if(!response.ok)throw Error('합성 최종 산출 계약 오류');return response.json();
   }
   return {round:2500,revision:'',ticket_id:null,values:{},stored_rounds:[],tickets:[],ticket_previews:[],upcoming_ticket_previews:[],upcoming_purchased:{status:'not_registered',games:[]},purchased:{status:'not_registered',games:[]},draw:{numbers:[1,2,3,4,5,6],bonus:7},result_round:2499,result_verification:{status:'official_history'},winning:null,recommendation_target:2500,recommendations:[],generation_matches:[],reviews:[]};
  }};
 }""")
 page.wait_for_function('el._walletData && !el._busy')
 page.locator('#tab-review').click();panel=page.locator('lotto-finalization-panel')
 expect(panel.locator('[role=status]')).to_contain_text('2/2',timeout=20000)
 check('HA readiness does not start a finalizer',context.request.get(fixture['control']+'/stats').json()['finalizations']==0)
 panel.get_by_role('button',name='최종 번호 산출',exact=True).click()
 expect(panel.locator('.finalization-results')).to_contain_text('2게임',timeout=20000)
 check('HA manual click creates one server job',context.request.get(fixture['control']+'/stats').json()['finalizations']==1)
 result=context.request.post(fixture['control']+'/bridge',data={'action':'refresh'}).json()['state']['last_result']
 visible=panel.locator('.finalization-results > .finalization-game').evaluate_all("nodes=>nodes.map(n=>[...n.querySelectorAll('.final-ball')].map(x=>Number(x.textContent)))")
 check('HA games and order match the service',visible==[row['numbers'] for row in result['games']])
 check('HA does not register purchased tickets',context.request.get(fixture['control']+'/stats').json()['tickets']==0)
 bootstrap=context.request.get(fixture['control']+'/bootstrap').json()
 same=context.request.get(fixture['backend']+'/api/v1/finalizations/'+result['finalization_run_id'],headers={'Cookie':'__Host-lottolab='+bootstrap['cookie']}).json()
 check('Web and HA share bundle/game IDs',same['games']==result['games'] and same['bundle_generation_id']==result['bundle_generation_id'])
 selected=panel.get_by_role('combobox',name='선택한 입력 묶음').input_value()
 context.request.post(fixture['control']+'/advance',data={'pending':True})
 panel.get_by_role('button',name='상태 확인',exact=True).click()
 expect(panel.get_by_role('combobox',name='선택한 입력 묶음')).to_have_value(selected)
 check('HA preserves selected input during source regeneration')
 for width in (1440,390,320):
  page.set_viewport_size({'width':width,'height':950});page.evaluate('(width)=>el.narrow=width<870',width)
  expect(panel.locator('.finalization-results')).to_contain_text('2게임')
  check('HA finalizer fits viewport '+str(width),page.evaluate('el.scrollWidth<=el.clientWidth+1'))
 page.evaluate("window.finalWidget=el.shadowRoot.querySelector('lotto-finalization-panel');finalWidget.remove();el.shadowRoot.querySelector('#screen-review').append(finalWidget)")
 expect(panel.locator('[role=status]')).to_contain_text('2/2')
 page.wait_for_timeout(5500)
 check('HA reconnect and periodic refresh do not regenerate',context.request.get(fixture['control']+'/stats').json()['finalizations']==1)
 check('No uncaught HA JavaScript errors',not errors)
 page.screenshot(path=str(platform/'.local/finalizer-ha-mobile.png'),full_page=True)
 browser.close()
(platform/'.local/finalizer-ha-browser-results.json').write_text(json.dumps({'passed':len(checks),'checks':checks},indent=2),encoding='utf-8')
print(json.dumps({'passed':len(checks)}))
