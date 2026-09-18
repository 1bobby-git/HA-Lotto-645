/* Authenticated HA websocket data; QR images are decoded locally with bundled jsQR. */
import './jsQR.js';
import { panelTemplate, parseGame, numberBalls, ticketRows, renderRows, renderPredictionRows, reviewPresentation, currentRecommendations } from './lotto-panel-view.js?v=2.2.2';

// The exact repository logo selected by the user. Served by the existing HA route.
export const PANEL_TAG = 'lotto-ticket-panel-v2-2-2';
const FALLBACK_LOGO = '/lotto_645_brand/logo.png?v=55ac9df7';
const labels = {
  waiting: '발표 대기', provisional: '속보 · 공식 확인 전',
  cross_checked: '복수 출처 일치 · 공식 확인 전', conflict: '출처 불일치 · 판정 보류',
  official_history: '공식 이력 기준', official_confirmed: '공식 이력 대조 완료',
  official_corrected: '공식 이력으로 정정',
};
const slots = [...'abcde'];
const formatRound = n => Number.isInteger(Number(n)) && Number(n)>0 ? `제 ${Number(n).toLocaleString('ko-KR')}회` : '보관한 복권';

class LottoTicketPanel extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:'open'});
    this._revision=''; this._editing=false; this._touched=new Set(); this._screen='home';
    this._ticketId=null;this._newTicket=false;this._newTicketId=null;this._visibleGames=1; this._walletData=null; this._cameraGeneration=0;
  }
  set hass(value) { this._hass=value; this.syncTheme(); this._start(); }
  set panel(value) { this._panel=value; this._start(); this._syncEntryOptions?.(); }
  connectedCallback() {
    this._visibility=()=>{if(document.hidden)this.stopCamera();};
    this._beforeUnload=e=>{if(this._editing&&this.node('editor')?.open){e.preventDefault();e.returnValue='';}};
    document.addEventListener('visibilitychange',this._visibility);
    window.addEventListener('beforeunload',this._beforeUnload);
    this._themeMedia=window.matchMedia('(prefers-color-scheme: dark)');
    this._themeListener=()=>this.syncTheme(); this._themeMedia.addEventListener('change',this._themeListener);
    this.syncTheme(); this._start(); this._onLottoConnected?.();
  }
  disconnectedCallback() {
    this._onLottoDisconnected?.();
    document.removeEventListener('visibilitychange',this._visibility);
    window.removeEventListener('beforeunload',this._beforeUnload);
    this._themeMedia?.removeEventListener('change',this._themeListener);
    this.stopCamera(); clearInterval(this._poll); this._poll=null; this._requestEpoch=(this._requestEpoch||0)+1;
    // Never retain an invisible top-layer dialog after HA navigates elsewhere.
    if(this.node('editor')?.open)this.node('editor').close();
    this.removeAttribute('data-editor-open');
  }
  syncTheme() {
    const dark=this._hass?.themes?.darkMode ?? window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme=dark?'dark':'light'; if(this.getAttribute('data-theme')!==theme)this.setAttribute('data-theme',theme);
  }
  _start() {
    if(!this._hass||!this._panel||!this.isConnected)return;
    if(!this.shadowRoot.firstChild)this.render();
    if(!this._poll)this._poll=setInterval(()=>{
      if(!this._busy&&!document.hidden&&this.node('entry')?.value)this.operation(()=>this.refreshStatus(),true);
    },30000);
  }
  node(id) { return this.shadowRoot.getElementById(id); }
  message(text,error=false) {
    const active=this.node('editor')?.open?'editor-message':'message';
    const n=this.node(active); if(!n)return;
    n.setAttribute('role',error?'alert':'status');n.setAttribute('aria-live',error?'assertive':'polite');
    n.dataset.error=String(error);n.textContent=text;
  }
  async request(type,extra={}) {
    const entry=this.node('entry').value;
    if(!entry)throw new Error('사용할 로또 통합이 없어요. 통합 설정을 확인해 주세요.');
    const epoch=this._requestEpoch||0;
    const data=await this._hass.callWS({type:`lotto_645/${type}`,entry_id:entry,...extra});
    if(!this.isConnected || epoch!==(this._requestEpoch||0) || entry!==this.node('entry')?.value) {
      const error=new Error('이전 통합의 응답입니다.');error.code='stale_response';throw error;
    }
    return data;
  }
  async operation(action,background=false) {
    if(this._busy)return;
    this._busy=true;
    const local='[data-screen],[data-go],#menu,#brand-home,#close-editor,#stop';
    const controls=background?[]:[...this.shadowRoot.querySelectorAll('button,input,select,textarea')].filter(n=>!n.matches(local));
    const disabled=controls.map(n=>n.disabled);controls.forEach(n=>n.disabled=true);
    if(!background)this.node('editor')?.setAttribute('aria-busy','true');
    try { await action(); }
    catch(error) {
      if(error?.code==='stale_response')return;
      this.message(error?.message||'작업을 완료하지 못했어요. 다시 시도해 주세요.',true);
      if(background){if(error?.code==='unavailable')this._scheduleLiveRetry?.();this.node('connection').dataset.online='false';this.node('connection').textContent='연결 확인 필요';this.node('sync-status').textContent='자동 확인 실패 · 다시 확인해 주세요';}
    } finally {
      this._busy=false;controls.forEach((n,i)=>n.disabled=disabled[i]);
      this.node('editor')?.removeAttribute('aria-busy');this.syncAvailability();
      if(this._focusAfter){const id=this._focusAfter;this._focusAfter=null;this.node(id)?.focus();}
      this._drainLiveRefresh?.();
      if(this._returnFocusPending){this._returnFocusPending=false;this._opener?.focus();}
    }
  }
  render() {
    this.shadowRoot.innerHTML=panelTemplate;
    const config=this._panel.config||{};
    for(const [id,name] of Object.entries(config.entries||{})){const option=document.createElement('option');option.value=id;option.textContent=name;this.node('entry').append(option);}
    this.node('entry-field').hidden=this.node('entry').options.length<=1;this._activeEntry=this.node('entry').value;
    const logo=config.brand_logo_url;
    this.node('brand').src=typeof logo==='string'&&/^\/lotto_645_brand\/logo\.png(?:\?|$)/.test(logo)?logo:FALLBACK_LOGO;
    this.node('brand').onerror=()=>{this.node('brand').hidden=true;this.node('brand-fallback').hidden=false;};
    this.node('menu').onclick=()=>this.dispatchEvent(new Event('hass-toggle-menu',{bubbles:true,composed:true}));
    this.node('brand-home').onclick=()=>this.showScreen('home',true);
    for(const button of this.shadowRoot.querySelectorAll('[data-screen]')) {
      button.onclick=()=>this.showScreen(button.dataset.screen);
      button.onkeydown=e=>this.onTabKey(e);
    }
    for(const button of this.shadowRoot.querySelectorAll('[data-go]'))button.onclick=()=>this.showScreen(button.dataset.go,true);
    for(const button of this.shadowRoot.querySelectorAll('[data-register]'))button.onclick=()=>this.openEditor('import');
    this.node('entry').onchange=()=>{
      if(this._editing&&!window.confirm('저장하지 않은 번호를 버리고 로또 통합을 변경할까요?')){this.node('entry').value=this._activeEntry;return;}
      this._activeEntry=this.node('entry').value;this._requestEpoch=(this._requestEpoch||0)+1;this.stopCamera();this._ensureLiveSubscription?.();
      this._editing=false;this._walletData=null;this._walletRound=null;this._loadedRound=null;
      this._queueLiveRefresh?.(true);
    };
    this.node('check').onclick=()=>this.operation(async()=>{
      this.message('새 추첨 결과를 확인하고 있어요.');this.updateResults(await this.request('result_check'));
      // result_check may return the server's selected round, not the visible wallet round.
      await this.refreshStatus();this.message('확인했어요. 새 결과가 없으면 자동 확인을 계속합니다.');
    });
    this.node('wallet-round').onchange=()=>this.operation(async()=>{
      try{await this.load(Number(this.node('wallet-round').value));}
      catch(error){this.node('wallet-round').value=String(this._walletRound||'');throw error;}
    });
    this.node('wallet-ticket').onchange=()=>this.operation(()=>this.load(this._walletRound,this.node('wallet-ticket').value));
    this.node('export-wallet').onclick=()=>this.operation(async()=>{
      const data=await this.request('purchases_export');
      const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
      const a=document.createElement('a');a.href=url;a.download='lotto-wallet.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    this.node('edit-wallet').onclick=()=>this.openEditor('edit');
    this.node('delete-wallet').onclick=()=>this.operation(()=>this.deleteWallet());
    this.node('close-editor').onclick=()=>this.closeEditor();
    this.node('editor').addEventListener('cancel',e=>{e.preventDefault();this.closeEditor();});
    this.node('editor').addEventListener('keydown',e=>this.onEditorKey(e));
    this.node('editor').addEventListener('click',e=>{
      if(e.target!==this.node('editor'))return;
      const r=this.node('editor').getBoundingClientRect();
      if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)this.closeEditor();
    });
    this.node('manual').onclick=()=>this.operation(async()=>{
      // Returning from number editing must preserve the draft and its revision.
      const target=this._editorMode==='edit'?this._walletRound:(this._targetRound||this._walletRound);
      if(!this._newTicket&&!this._editing&&target&&target!==this._loadedRound)await this.load(target);
      this.showEditorStep('edit');this._focusAfter='game_a';
      if(this._revision)this.message('선택한 복권의 A~E만 수정합니다. 다른 복권은 유지됩니다.');
    });
    this.node('back-editor').onclick=()=>{this.stopCamera();this.showEditorStep('import');this.node('manual').focus();};
    this.node('save').onclick=()=>this.operation(()=>this.save());
    this.node('scan').onclick=()=>this.operation(async()=>{this._cameraStarting=true;try{await this.startCamera();}finally{this._cameraStarting=false;}});
    this.node('stop').onclick=()=>this.stopCamera();
    this.node('photo').onclick=()=>this.node('file').click();
    this.node('file').onchange=()=>this.operation(()=>this.readPhoto());
    this.node('preview').onclick=()=>this.operation(()=>this.preview(this.node('qr').value));
    this.node('round').oninput=()=>{this._editing=true;this._loadedRound=this._newTicket?Number(this.node('round').value):null;this.updateFormStatus();};
    this.node('load').onclick=()=>{
      if(this._editing&&!window.confirm('저장하지 않은 입력을 버리고 해당 회차를 불러올까요?'))return;
      this.operation(async()=>{await this.load(this.selectedRound());this.message('해당 회차를 불러왔어요. 번호를 확인해 주세요.');this._focusAfter='game_a';});
    };
    for(const s of slots){
      const row=document.createElement('div');row.id=`field_${s}`;row.className='game-field';
      const label=document.createElement('label');label.htmlFor=`game_${s}`;
      const tag=document.createElement('span');tag.className='slot-tag';tag.textContent=s.toUpperCase();label.append(tag,document.createTextNode('게임 · 번호 6개'));
      const input=document.createElement('input');input.id=`game_${s}`;input.inputMode='numeric';input.maxLength=100;input.autocomplete='off';input.spellcheck=false;
      input.placeholder='예: 1, 7, 15, 24, 33, 45';input.setAttribute('aria-describedby',`hint_${s}`);
      input.oninput=()=>{this._editing=true;this.updateFormStatus();};input.onblur=()=>{this._touched.add(s);this.updateFormStatus();};
      const hint=document.createElement('p');hint.id=`hint_${s}`;hint.className='game-feedback';row.append(label,input,hint);this.node('games').append(row);
    }
    this.node('add-game').onclick=()=>{if(this._visibleGames>=5)return;this.showGameSlots(this._visibleGames+1);this.node(`game_${slots[this._visibleGames-1]}`).focus();};
    this.showGameSlots(1);this.syncAvailability();
    if(this._activeEntry)this.operation(()=>this.load());
    else{this.message('사용할 로또 통합이 없어요. 상단 설정에서 통합을 추가해 주세요.',true);this.node('drawtitle').textContent='통합 설정 필요';this.node('numbers').textContent='연결된 로또 통합이 없어요.';this.node('connection').textContent='통합 설정 필요';ticketRows(this.node('mini-games'),[]);ticketRows(this.node('wallet-games'),[]);}
  }
  syncAvailability() {
    if(!this.node('entry'))return;
    const available=!!this.node('entry').value;
    for(const n of this.shadowRoot.querySelectorAll('[data-register],#check'))n.disabled=!available||this._busy;
    this.node('edit-wallet').disabled=!this._walletData||this._busy;
    this.node('delete-wallet').disabled=!this._walletData?.revision||this._busy;
    this.node('wallet-round').disabled=!this._walletData||this._busy;
  }
  showScreen(name,focus=false) {
    if(!['home','wallet','review'].includes(name))return;
    for(const key of ['home','wallet','review']){const selected=key===name;const tab=this.node(`tab-${key}`);tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;this.node(`screen-${key}`).hidden=!selected;}
    this._screen=name;this.scrollTop=0;if(focus)this.node(`tab-${name}`).focus();
  }
  onTabKey(e) {
    const keys=['home','wallet','review'],index=keys.indexOf(e.currentTarget.dataset.screen);
    let next;if(e.key==='ArrowRight')next=(index+1)%keys.length;else if(e.key==='ArrowLeft')next=(index+keys.length-1)%keys.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=keys.length-1;else return;
    e.preventDefault();this.showScreen(keys[next],true);
  }
  openEditor(mode='import') {
    if(this.node('editor').open||!this._activeEntry||this._busy)return;
    this._opener=this.shadowRoot.activeElement;this._editorMode=mode;
    if(this._walletData)this.restoreForm(this._walletData);
    this._newTicket=mode!=='edit';this._newTicketId=globalThis.crypto?.randomUUID?.()||`ticket-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    if(this._newTicket){this._revision='';this._loadedRound=this._targetRound||this._walletRound;this.node('round').value=this._loadedRound||'';slots.forEach(s=>this.node(`game_${s}`).value='');this.showGameSlots(1);}
    this.node('editor-title').textContent=mode==='edit'?'구매번호 수정':'복권 등록';
    this.node('editor-message').textContent='';this.node('message').textContent='';this.node('qr').value='';
    this.node('address-import').open=false;this.showEditorStep(mode==='edit'?'edit':'import');
    this.setAttribute('data-editor-open','');this.node('editor').showModal();
    this.node(mode==='edit'?'game_a':'scan').focus();
  }
  onEditorKey(event) {
    if(event.key!=='Tab')return;
    // Keep keyboard traversal in the sheet instead of handing it to browser chrome.
    // The native modal additionally makes the rest of the document inert.
    const nodes=[...this.node('editor').querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary,[tabindex]:not([tabindex="-1"])')]
      .filter(n=>n.getClientRects().length&&!n.closest('[hidden]')&&(!n.closest('details:not([open])')||n.tagName==='SUMMARY'));
    const first=nodes[0],last=nodes.at(-1),active=this.shadowRoot.activeElement;
    if(!first)return;
    if(event.shiftKey&&(active===first||!nodes.includes(active))){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&(active===last||!nodes.includes(active))){event.preventDefault();first.focus();}
  }
  showEditorStep(step) {
    const editing=step==='edit';
    this.node('import-step').hidden=editing;this.node('edit-step').hidden=!editing;
    this.node('save-footer').hidden=!editing;this.node('privacy-footer').hidden=editing;
    for(const [id,active] of [['step-1',!editing],['step-2',editing]]){this.node(id).dataset.current=String(active);if(active)this.node(id).setAttribute('aria-current','step');else this.node(id).removeAttribute('aria-current');}
    this.node('sheet-scroll').scrollTop=0;
  }
  closeEditor() {
    if(this._busy&&!this._cameraStarting){this.message('진행 중인 작업이 끝난 뒤 닫아 주세요.');return;}
    if(this._editing&&!window.confirm('저장하지 않은 번호를 버리고 닫을까요?'))return;
    this._editing=false;if(this._walletData)this.restoreForm(this._walletData);this.finishClose();
  }
  finishClose(restoreFocus=true) {
    this.stopCamera();this.node('editor').close();this.removeAttribute('data-editor-open');
    this._returnFocusPending=restoreFocus&&this._busy;
    if(restoreFocus&&!this._busy)this._opener?.focus();
  }
  showGameSlots(count) {
    this._visibleGames=Math.max(1,Math.min(5,count));
    slots.forEach((s,i)=>this.node(`field_${s}`).hidden=i>=this._visibleGames);
    this.node('add-game').hidden=this._visibleGames>=5;
  }
  restoreForm(data) {
    this.node('round').value=data.round||data.recommendation_target||'';
    this._loadedRound=Number(this.node('round').value)||null;this._revision=data.revision||'';
    slots.forEach(s=>this.node(`game_${s}`).value=data.values?.[`game_${s}`]||'');
    this._editing=false;this._touched.clear();
    const last=slots.map(s=>!!this.node(`game_${s}`).value.trim()).lastIndexOf(true);this.showGameSlots(last+1);
    const rounds=data.stored_rounds||[];this.node('savedrounds').textContent=rounds.length?`저장된 회차: ${rounds.slice(0,12).join(', ')}${rounds.length>12?` 외 ${rounds.length-12}개`:''}`:'아직 저장한 회차가 없어요.';
    this.updateFormStatus();
  }
  updateFormStatus() {
    let filled=0,valid=0;
    for(const s of slots){const input=this.node(`game_${s}`),hint=this.node(`hint_${s}`),value=parseGame(input.value);if(!value.empty)filled++;if(!value.empty&&!value.error)valid++;
      const invalid=!!value.error&&this._touched.has(s);if(invalid)input.setAttribute('aria-invalid','true');else input.removeAttribute('aria-invalid');
      hint.dataset.valid=invalid?'false':!value.empty&&!value.error?'true':'';hint.textContent=value.empty?'빈 게임은 저장하지 않아요.':invalid?value.error:value.error?'번호 6개를 입력해 주세요.':'✓ 중복 없는 번호 6개 확인';
    }
    this.node('ticket-count').textContent=`${filled} / 5게임`;
    const status=this._editing?(this._loadedRound?'아직 저장하지 않았어요. 번호를 확인해 주세요.':'회차를 바꿨어요. 먼저 회차 불러오기를 눌러 주세요.'):(filled?'저장된 번호입니다. 수정 후 다시 저장할 수 있어요.':'입력한 번호를 확인한 뒤 저장해 주세요.');
    if(this.node('draft-status').textContent!==status)this.node('draft-status').textContent=status;
    this.node('save').textContent=filled&&filled===valid?`${valid}게임 내 복권에 저장`:'내 복권에 저장';return {filled,valid};
  }
  selectedRound() {
    const raw=this.node('round').value.trim();if(!/^[0-9]{1,6}$/.test(raw)||Number(raw)<1){this._focusAfter='round';throw new Error('회차를 1~999999 사이의 숫자로 입력해 주세요.');}return Number(raw);
  }
  async load(round=null,ticket_id=null) {
    const data=await this.request('purchases_get',{...(round?{round}:{}),...(ticket_id?{ticket_id}:{})});
    this._newTicket=false;
    this.updateResults(data);this.applyWallet(data);this.restoreForm(data);
    if(data.storage_error)this.message('구매번호 저장소를 확인해야 해요. 기존 파일은 덮어쓰지 않습니다.',true);
  }
  async refreshStatus() {
    const data=await this.request('purchases_get',this._walletRound?{round:this._walletRound,...(this._ticketId?{ticket_id:this._ticketId}:{})}:{});
    this.updateResults(data);
    // Update saved records, never the editor's draft or optimistic concurrency revision.
    if(Number(data.round)===this._walletRound||!this._walletRound)this.applyWallet(data);
    if(data.storage_error)this.message('구매번호 저장소 오류가 있어요. 기존 파일은 보존됩니다.',true);
  }
  applyWallet(data) {
    this._walletData=data;this._walletRound=Number(data.round)||null;this._ticketId=data.ticket_id||null;
    const slips=this.node('wallet-ticket');slips.replaceChildren();
    (data.tickets||[]).forEach((ticket,index)=>{const o=document.createElement('option');o.value=ticket.ticket_id;o.textContent=`복권 ${index+1} · ${ticket.game_count}게임`;slips.append(o);});
    slips.value=this._ticketId||'';
    this.node('export-wallet').disabled=!(data.stored_rounds||[]).length;
    const games=data.purchased?.games||[];
    this.node('mini-round').textContent=formatRound(data.round);this.node('ticket-round').textContent=formatRound(data.round);
    this.node('mini-count').textContent=games.length>3?`${games.length}게임 중 3게임 표시`:`${games.length}게임 보관`;this.node('wallet-count').textContent=`${games.length}게임 · 이번 회차 ${data.tickets?.length||0}장`;
    const matches=data.generation_matches||[];
    ticketRows(this.node('mini-games'),games,3,matches);ticketRows(this.node('wallet-games'),games,Infinity,matches);
    const select=this.node('wallet-round');const rounds=[...new Set([data.round,data.recommendation_target,...(data.stored_rounds||[])].map(Number).filter(n=>Number.isInteger(n)&&n>0))].sort((a,b)=>b-a);
    const signature=rounds.join(',');
    if(this._roundSignature!==signature){select.replaceChildren();for(const n of rounds){const option=document.createElement('option');option.value=String(n);option.textContent=formatRound(n);select.append(option);}this._roundSignature=signature;}
    select.value=String(data.round||'');this.syncAvailability();
  }
  updateResults(data) {
    const draw=data.draw,meta=data.result_verification||{};
    const presentation=reviewPresentation(data),rr=presentation.report;
    const currentRows=currentRecommendations(data);
    renderPredictionRows(this.node('current-recommendations'),currentRows,['현재 생성번호가 없습니다.','공식 선택과 서비스 연결을 확인하세요. 기존 복권·리뷰 기록은 보존됩니다.']);
    this.node('current-recommendations-heading').textContent=`${formatRound(data.recommendation_target)} · 현재 생성번호`;
    const serviceStatus=data.service_status;
    const matchedFormulaCount=new Set((data.generation_matches||[]).map(row=>row.formula_id).filter(Boolean)).size;
    const matchNote=matchedFormulaCount
      ? `저장한 구매번호와 ${matchedFormulaCount}개 공식의 번호가 정확히 일치합니다. 같은 회차의 6개 번호가 모두 같은 경우만 표시합니다.`
      : '현재 센서의 번호이며 과거 검증 성적이나 실제 구매 내역이 아닙니다.';
    this.node('current-recommendations-note').textContent=(serviceStatus==='generating'?'새 번호를 생성 중입니다. 이전 저장번호를 유지합니다. ':serviceStatus&&serviceStatus!=='ready'?'서비스 상태: '+serviceStatus+' · 저장번호를 표시합니다. ':'')+matchNote;
    const awaiting=!presentation.evaluated;
    this._targetRound=Number(data.recommendation_target)||this._targetRound;
    this.node('drawtitle').textContent=data.result_round?formatRound(data.result_round):'결과 발표 대기';
    const numbers=this.node('numbers');numbers.removeAttribute('role');numbers.removeAttribute('aria-label');
    if(meta.status!=='conflict'&&draw)numberBalls(numbers,draw.numbers,draw.bonus);
    else numbers.textContent=meta.status==='conflict'?'출처를 확인 중이에요. 판정을 잠시 보류합니다.':'아직 당첨번호가 발표되지 않았어요.';
    this.node('verification').textContent=labels[meta.status]||'발표 대기';
    this.node('verification').dataset.state=meta.status==='conflict'?'conflict':meta.status?.startsWith('official')?'verified':'pending';
    const w=data.winning;
    this.node('result').textContent=w?.status==='evaluated'?`${w.round}회 · 당첨 ${w.winning_game_count}게임${Number(w.winning_game_count)>0?` · 최고 ${w.highest_prize}`:' · 당첨 없음'}`:w?.status==='conflict'?'출처 확인 후 다시 대조해요.':'대조할 추첨 전 추천 또는 구매번호가 아직 없어요.';
    renderPredictionRows(this.node('predictions'),presentation.rows,['아직 이번 회차에 저장된 추천번호가 없어요.','공식을 선택해 번호를 생성하면 추첨 대기 상태로 여기에 등록됩니다.']);
    const current=new Map((rr.methods||[]).map(r=>[r.method_id,r]));
    this.node('predictions-heading').textContent=`${formatRound(presentation.round)} · ${awaiting?'추첨 대기':'추천번호 결과'}`;
    this.node('predictions-note').textContent=awaiting?'추첨 전에 저장한 번호입니다. 같은 회차의 당첨번호가 발표되면 자동으로 대조합니다. 결과 발표 전에는 점수·등수·당첨 여부를 매기지 않습니다.':'추첨 전에 저장된 번호와 같은 회차의 당첨번호를 비교합니다. 본번호 일치는 실선, 보너스 일치는 점선으로 표시합니다.';
    this.rows('reviews',(data.reviews||[]).map(r=>{
      const now=current.get(r.method_id),rated=presentation.evaluated&&now&&Number.isFinite(now.review_score);
      const score=rated?`${rr.status==='provisional'?'잠정 ':''}${now.review_score.toFixed(1)}점`:now?'추첨 대기':'이번 회차 기록 없음';
      return [r.display_name||r.label,r.reviewed_rounds||0,score,rated?`${now.exact_match_count}개 / ${now.near_match_count}개`:'—',rated?`${now.rank_this_round} / ${rr.peer_count}`:'—'];
    }));
    this.node('method-count').textContent=`${(data.reviews||[]).length}개 공식`;
    let status=data.review_storage_error?'리뷰 기록을 불러오지 못했어요. 기존 기록은 보존됩니다.':data.review_save_pending?'추천번호 저장을 다시 시도하고 있어요.':awaiting?`${formatRound(presentation.round)} 추첨 대기 · 저장된 ${presentation.rows.length}개 공식의 번호는 결과 발표 후 평가해요.`:`${formatRound(presentation.round)} 결과 기준 · 누적 별점에는 공식 확인된 회차만 포함해요.`;
    if((data.reviews||[]).some(r=>r.unrated_result))status+=' 추첨 전 생성 여부가 확인되지 않은 과거 기록은 누적평가에서 제외합니다.';
    this.node('reviewstatus').textContent=status;
    const sources=this.node('sources');sources.replaceChildren();
    for(const source of meta.sources||[]){let url;try{url=new URL(source.url);}catch{continue;}if(!['https:','http:'].includes(url.protocol))continue;const a=document.createElement('a');a.textContent=`${source.publisher||'출처'} 발표 ↗`;a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';sources.append(a);}
    this.node('connection').dataset.online='true';this.node('connection').textContent='HA 연결됨';
    const now=new Intl.DateTimeFormat('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date());
    this.node('sync-status').textContent=`최근 확인 ${now} · 30초마다 자동 확인`;
  }
  rows(id,rows) {
    const headers=id==='reviews'?['추첨 공식 / 별점','평가 회차','이번 점수','정확 / ±1','순위']:['추첨 공식','번호','결과'];
    const empty=id==='reviews'?['아직 누적된 리뷰가 없어요.','공식 확인된 회차부터 실제 추천 결과를 평가합니다.']:['대조할 추천번호를 기다리고 있어요.','추첨 전에 저장한 추천이 있으면 결과 발표 후 표시됩니다.'];
    renderRows(this.node(id),rows,headers,empty);
  }
  async preview(qr) {
    if(!String(qr||'').trim()){this._focusAfter='qr';throw new Error('복권 QR 주소를 붙여 넣어 주세요.');}
    const result=await this.request('qr_preview',{qr});
    if(this._editing&&!window.confirm('저장하지 않은 입력을 QR 번호로 바꿀까요?'))return;
    this.node('round').value=result.round;this._loadedRound=Number(result.round);this._revision='';this._newTicket=true;this._newTicketId=globalThis.crypto?.randomUUID?.()||`ticket-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    slots.forEach(s=>this.node(`game_${s}`).value=result.values?.[`game_${s}`]||'');
    this.node('qr').value='';this._editing=true;this._touched.clear();
    this.showGameSlots(slots.map(s=>!!this.node(`game_${s}`).value.trim()).lastIndexOf(true)+1);this.updateFormStatus();this.showEditorStep('edit');
    this.message(`${result.round}회 ${result.game_count}게임을 읽었어요. 아직 저장하지 않았어요.`+(result.duplicate_candidate?' 같은 번호의 복권이 이미 있습니다. 별도 구매한 복권인지 확인하세요.':' 새 복권으로 추가됩니다.'));this._focusAfter='game_a';
    if(!this._busy){this._focusAfter=null;this.node('game_a').focus();}
  }
  async save() {
    const round=this.selectedRound();
    if(this._loadedRound!==round){this._focusAfter='load';throw new Error('먼저 회차 불러오기를 눌러 주세요. 다른 회차의 번호를 덮어쓰지 않도록 확인이 필요해요.');}
    this._touched=new Set(slots);const {filled,valid}=this.updateFormStatus();
    if(!filled){this._focusAfter='game_a';throw new Error('최소 한 게임의 번호 6개를 입력해 주세요.');}
    if(valid!==filled){const first=slots.find(s=>parseGame(this.node(`game_${s}`).value).error);this.showGameSlots(Math.max(this._visibleGames,slots.indexOf(first)+1));this._focusAfter=`game_${first}`;throw new Error(`${first.toUpperCase()} 게임의 번호를 확인해 주세요.`);}
    // An explicit save is enough for a new record. Replacements require a second confirmation.
    if(this._revision&&!window.confirm(`${round}회에 저장된 A~E를 지금 확인한 번호로 교체할까요?`))return;
    const values={};slots.forEach(s=>values[`game_${s}`]=this.node(`game_${s}`).value);
    const data=await this.request('purchases_save',{round,values,revision:this._newTicket?'':this._revision,clear:false,new_ticket:this._newTicket,...((this._newTicket?this._newTicketId:this._ticketId)?{ticket_id:this._newTicket?this._newTicketId:this._ticketId}:{})});
    this._editing=false;this._newTicket=false;this.updateResults(data);this.applyWallet(data);this.restoreForm(data);this.finishClose(false);
    this.showScreen('wallet',true);this.message(`${round}회 ${filled}게임을 저장했어요. 추첨 결과가 확인되면 자동으로 대조합니다.`);
  }
  async deleteWallet() {
    const data=this._walletData;if(!data?.revision)return;
    const round=Number(data.round);if(!window.confirm(`${round}회에서 선택한 복권 한 장만 삭제할까요? 다른 복권과 추천 기록은 유지됩니다.`))return;
    const result=await this.request('purchases_save',{round,values:data.values||{},revision:data.revision,clear:true,...(data.ticket_id?{ticket_id:data.ticket_id}:{})});
    this.updateResults(result);this.applyWallet(result);this.restoreForm(result);this.message(`${round}회 구매번호를 삭제했어요.`);
  }
  decode(image,width,height) {
    if(!globalThis.jsQR)throw new Error('QR 판독기를 불러오지 못했습니다. QR 주소 붙여넣기를 이용하세요.');
    const canvas=document.createElement('canvas'),scale=Math.min(1,1600/Math.max(width,height));
    canvas.width=Math.max(1,Math.round(width*scale));canvas.height=Math.max(1,Math.round(height*scale));
    const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,canvas.width,canvas.height);
    const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
    return globalThis.jsQR(pixels.data,pixels.width,pixels.height,{inversionAttempts:'attemptBoth'})?.data;
  }
  async readPhoto() {
    const file=this.node('file').files[0];this.node('file').value='';if(!file)return;
    if(file.size>10*1024*1024 || !['image/png','image/jpeg','image/webp'].includes(file.type))throw new Error('10MB 이하의 PNG/JPEG/WebP QR 사진을 선택하세요.');
    const url=URL.createObjectURL(file);
    try {const im=new Image();im.src=url;await im.decode();if(im.width*im.height>40000000)throw new Error('사진이 너무 큽니다. QR 부분만 잘라 선택하세요.');const value=this.decode(im,im.width,im.height);if(!value)throw new Error('QR을 찾지 못했습니다. 밝고 선명한 QR 사진 또는 QR 주소를 입력하세요.');await this.preview(value);}
    finally{URL.revokeObjectURL(url);}
  }
  async startCamera() {
    this.stopCamera();const generation=this._cameraGeneration;
    if(!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)throw new Error('이 환경에서 카메라를 열 수 없습니다. HTTPS로 접속하거나 QR 사진/주소 입력을 이용하세요.');
    let stream;
    try{stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});}
    catch(error){throw new Error(error.name==='NotAllowedError'?'카메라 권한이 필요해요. 브라우저에서 허용하거나 사진·직접 입력을 이용해 주세요.':error.name==='NotFoundError'?'사용할 카메라가 없어요. 사진이나 직접 입력을 이용해 주세요.':'카메라를 열지 못했어요. 다른 앱에서 사용 중인지 확인해 주세요.');}
    if(!this.isConnected||document.hidden||generation!==this._cameraGeneration){stream.getTracks().forEach(t=>t.stop());return;}
    this._stream=stream;
    this.node('camera').hidden=false;const video=this.node('video');video.srcObject=this._stream;
    try{await video.play();}catch(e){this.stopCamera();throw e;}
    this.message('복권 오른쪽 위 QR을 카메라에 비춰주세요.');
    this.node('camera').scrollIntoView({block:'nearest'});
    const tick=async()=>{
      if(!this._stream)return;
      try {if(!this._busy&&video.readyState>=2){const value=this.decode(video,video.videoWidth,video.videoHeight);if(value){this.stopCamera();await this.operation(()=>this.preview(value));return;}}}
      catch(e){this.stopCamera();this.message(e.message,true);return;}
      this._scanTimer=setTimeout(tick,500);
    };
    this._scanTimer=setTimeout(tick,500);
  }
  stopCamera(){this._cameraGeneration=(this._cameraGeneration||0)+1;clearTimeout(this._scanTimer);if(this._stream){this._stream.getTracks().forEach(t=>t.stop());this._stream=null;}if(this.node('video'))this.node('video').srcObject=null;if(this.node('camera'))this.node('camera').hidden=true;}
}
if(!customElements.get(PANEL_TAG)) customElements.define(PANEL_TAG,LottoTicketPanel);
// Compatibility alias only on fresh pages. HA uses the versioned element.
if(!customElements.get('lotto-ticket-panel')) customElements.define('lotto-ticket-panel', class extends customElements.get(PANEL_TAG) {});
