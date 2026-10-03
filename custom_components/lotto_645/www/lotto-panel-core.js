/* Authenticated HA websocket data; QR images are decoded locally with bundled jsQR. */
import './jsQR.js';
import { panelTemplate, parseGame, numberBalls, ticketRows, renderRows, lastReviewPresentation, currentRecommendations, renderCurrentRecommendationRows, renderReviewResultRows, formulaLinkLabels } from './lotto-panel-view.js?v=2.4.23';
import { ticketRowsFromOcr, ticketLinesFromRows, ticketExpectedGames, singleGameTokens, retryDisagrees } from './lotto-ticket-ocr.js?v=2.4.23';

// The exact repository logo selected by the user. Served by the existing HA route.
export const PANEL_TAG = 'lotto-ticket-panel-v2-4-23';
const FALLBACK_LOGO = '/lotto_645_brand/logo.png?v=55ac9df7';
const labels = {
  waiting: '발표 대기', provisional: '속보 · 공식 확인 전',
  cross_checked: '복수 출처 일치 · 공식 확인 전', conflict: '출처 불일치 · 판정 보류',
  official_history: '공식 이력 기준', official_confirmed: '공식 이력 대조 완료',
  official_corrected: '공식 이력으로 정정',
};
const slots = [...'abcde'];
const formatRound = n => Number.isInteger(Number(n)) && Number(n)>0 ? `제 ${Number(n).toLocaleString('ko-KR')}회` : '보관한 복권';
const KST_RECEIPT_TIME=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',weekday:'short',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
const formatReceiptTime = value => {
  const time=Date.parse(value||'');
  if(!Number.isFinite(time))return '—';
  const part=Object.fromEntries(KST_RECEIPT_TIME.formatToParts(new Date(time)).map(p=>[p.type,p.value]));
  return `${part.year}/${part.month}/${part.day} (${part.weekday}) ${part.hour}:${part.minute}:${part.second}`;
};
// Same rule as published_results.draw_date: round 1 was drawn on 2002-12-07, then weekly.
const FIRST_DRAW_UTC=Date.UTC(2002,11,7);
const formatDrawDate = round => {
  if(!Number.isInteger(round)||round<1||round>10000)return '—';
  const date=new Date(FIRST_DRAW_UTC+(round-1)*7*86400000);
  return `${date.getUTCFullYear()}/${String(date.getUTCMonth()+1).padStart(2,'0')}/${String(date.getUTCDate()).padStart(2,'0')} (${'일월화수목금토'[date.getUTCDay()]})`;
};
/* Decorative slip art only: deterministic per local ticket, never a real or scannable ticket code. */
const SVG_NS='http://www.w3.org/2000/svg';
const receiptSeed = text => {let hash=2166136261;for(const ch of String(text)){hash^=ch.codePointAt(0);hash=Math.imul(hash,16777619);}return hash>>>0;};
const receiptRandom = seed => () => {seed=(seed+0x6D2B79F5)|0;let t=Math.imul(seed^(seed>>>15),1|seed);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
const receiptSvg = (viewBox,d,aspect) => {
  const svg=document.createElementNS(SVG_NS,'svg');svg.setAttribute('viewBox',viewBox);svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');svg.setAttribute('shape-rendering','crispEdges');
  if(aspect)svg.setAttribute('preserveAspectRatio',aspect);
  const path=document.createElementNS(SVG_NS,'path');path.setAttribute('d',d);path.setAttribute('fill','currentColor');svg.append(path);return svg;
};
const receiptQr = seed => {
  const size=25,next=receiptRandom(seed);let d='';
  const finder=(x,y)=>{
    for(const [fx,fy] of [[0,0],[size-7,0],[0,size-7]]){
      const dx=x-fx,dy=y-fy;
      if(dx<-1||dx>7||dy<-1||dy>7)continue;
      if(dx<0||dy<0||dx>6||dy>6)return false;
      return dx===0||dy===0||dx===6||dy===6||(dx>=2&&dx<=4&&dy>=2&&dy<=4);
    }
    return null;
  };
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    let on=finder(x,y);
    if(on===null){
      const ax=x-16,ay=y-16;
      if(ax>=0&&ax<=4&&ay>=0&&ay<=4)on=ax===0||ay===0||ax===4||ay===4||(ax===2&&ay===2);
      else if(y===6)on=x%2===0;
      else if(x===6)on=y%2===0;
      else on=next()<.5;
    }
    if(on)d+=`M${x} ${y}h1v1h-1z`;
  }
  return receiptSvg(`-1 -1 ${size+2} ${size+2}`,d);
};
const receiptBarcode = seed => {
  const next=receiptRandom(seed^0x9E3779B9);let x=0,d='';
  const bar=w=>{d+=`M${x} 0h${w}v1h-${w}z`;x+=w;},gap=w=>{x+=w;};
  bar(1);gap(1);bar(1);
  for(let i=0;i<88;i++){const w=1+Math.floor(next()*3);if(i%2===0)gap(w);else bar(w);}
  gap(1);bar(1);gap(1);bar(1);
  return receiptSvg(`0 0 ${x} 1`,d,'none');
};
const receiptWatermark = at => {
  const mark=document.createElement('span');mark.className='receipt-watermark';mark.dataset.at=at;mark.setAttribute('aria-hidden','true');
  const word=document.createElement('span');word.textContent='LOTTO';const game=document.createElement('small');game.textContent='6/45';
  mark.append(word,game);return mark;
};
const receiptInfoLine = (label,value) => {
  const line=document.createElement('span');const term=document.createElement('b');term.textContent=label;
  line.append(term,` : ${value}`);return line;
};
const createReceiptHeader = (card,round,ticket,index,total) => {
  card.classList.add('ticket-receipt');
  const top=document.createElement('div');top.className='paper-top receipt-top';
  const head=document.createElement('div');head.className='receipt-head';
  const brand=document.createElement('div');brand.className='receipt-brand';
  const word=document.createElement('strong');word.className='receipt-word';word.textContent='LOTTO';
  const game=document.createElement('span');game.className='receipt-game';game.textContent='6/45';brand.append(receiptWatermark('head'),word,game);
  const mark=document.createElement('span');mark.className='receipt-qr';mark.setAttribute('aria-hidden','true');mark.append(receiptQr(receiptSeed(`${round}:${ticket.ticket_id||index}`)));
  head.append(brand,mark);
  const roundText=document.createElement('div');roundText.className='receipt-round';roundText.textContent=Number.isInteger(round)?`제 ${round.toLocaleString('ko-KR')} 회`:formatRound(round);
  const info=document.createElement('div');info.className='receipt-info';
  const count=Math.max(0,Number(ticket.game_count)||0);
  info.append(
    receiptInfoLine('등록일',formatReceiptTime(ticket.saved_at)),
    receiptInfoLine('추첨일',formatDrawDate(round)),
    receiptInfoLine('게임수',`${count}게임 · ${index+1}/${total}장`),
    receiptWatermark('info'),
  );
  top.append(head,roundText,info);return top;
};
const createReceiptTotal = (round,ticket,index) => {
  const foot=document.createElement('div');foot.className='receipt-total';
  const amount=document.createElement('div');amount.className='receipt-amount';
  const label=document.createElement('span');label.textContent='금액';
  const strong=document.createElement('strong');const count=Math.max(0,Number(ticket.game_count)||0);strong.textContent=`₩ ${(count*1000).toLocaleString('ko-KR')}`;amount.append(label,strong);
  const code=document.createElement('small');code.className='receipt-serial';code.textContent=`HOME ASSISTANT · ${String(round||0).padStart(4,'0')}-${String(index+1).padStart(2,'0')} · 보관용 표시`;
  const barcode=document.createElement('span');barcode.className='receipt-barcode';barcode.setAttribute('aria-hidden','true');barcode.append(receiptBarcode(receiptSeed(`${ticket.ticket_id||index}:${round}`)));
  foot.append(receiptWatermark('total'),amount,code,barcode);return foot;
};
// Printed-slip presentation of the shared ticket rows: two-digit numbers and a short waiting label.
const decorateReceiptRows = list => {
  list.querySelectorAll('.ticket-balls .ball').forEach(ball=>{const n=Number(ball.textContent);if(Number.isInteger(n)&&n>=1&&n<=45)ball.textContent=String(n).padStart(2,'0');});
  list.querySelectorAll('.ticket-row').forEach(row=>{
    const prize=row.querySelector('.prize');
    if(prize&&row.querySelector('.ticket-balls')?.dataset.evaluated!=='true'&&prize.textContent==='복권 추첨 대기')prize.textContent='추첨 대기';
  });
};
const receiptLegend = list => {
  const kinds=[['main','당첨번호 일치'],['bonus','보너스 일치']].filter(([kind])=>list.querySelector(`.ball[data-hit="${kind}"]`));
  if(!kinds.length)return null;
  const legend=document.createElement('p');legend.className='receipt-legend';
  for(const [kind,text] of kinds){const item=document.createElement('span');item.dataset.kind=kind;item.textContent=text;legend.append(item);}
  return legend;
};
const createReceiptSheet = (...parts) => {
  const sheet=document.createElement('div');sheet.className='receipt-sheet';
  const ribbon=document.createElement('span');ribbon.className='receipt-ribbon';ribbon.setAttribute('aria-hidden','true');
  for(let i=0;i<2;i++){const text=document.createElement('span');text.textContent='LOTTO 6/45';ribbon.append(text);}
  sheet.append(ribbon,...parts.filter(Boolean));return sheet;
};

class LottoTicketPanel extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:'open'});
    this._revision=''; this._editing=false; this._touched=new Set(); this._screen='home';
    this._ticketId=null;this._newTicket=false;this._newTicketId=null;this._visibleGames=1; this._walletData=null; this._cameraGeneration=0;
    this._homeTicketId=null;this._miniSwiperFrame=0;this._walletSlideId=null;this._walletSwiperFrame=0;
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
    if(this._miniSwiperFrame)cancelAnimationFrame(this._miniSwiperFrame);this._miniSwiperFrame=0;
    if(this._walletSwiperFrame)cancelAnimationFrame(this._walletSwiperFrame);this._walletSwiperFrame=0;
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
      if(background){this.node('connection').dataset.online='false';this.node('connection').textContent='연결 확인 필요';this.node('sync-status').textContent='확인 실패 · 다시 확인해 주세요';}
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
    this.node('mini-prev').onclick=()=>this.moveMiniSwiper(-1);
    this.node('mini-next').onclick=()=>this.moveMiniSwiper(1);
    this.node('wallet-prev').onclick=()=>this.moveWalletSwiper(-1);
    this.node('wallet-next').onclick=()=>this.moveWalletSwiper(1);
    this.node('mini-swiper').onkeydown=e=>{if(e.target!==e.currentTarget)return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();this.moveMiniSwiper(e.key==='ArrowLeft'?-1:1);}};
    this.node('wallet-swiper').onkeydown=e=>{if(e.target!==e.currentTarget)return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();this.moveWalletSwiper(e.key==='ArrowLeft'?-1:1);}};
    this.node('review-filter').onchange=()=>this.renderReviewSummary(this._reviewData||{});
    this.node('review-sort').onchange=()=>this.renderReviewSummary(this._reviewData||{});
    for(const button of this.shadowRoot.querySelectorAll('[data-register]'))button.onclick=()=>this.openEditor('import');
    this.node('entry').onchange=()=>{
      if(this._editing&&!window.confirm('저장하지 않은 번호를 버리고 로또 통합을 변경할까요?')){this.node('entry').value=this._activeEntry;return;}
      this._activeEntry=this.node('entry').value;this._requestEpoch=(this._requestEpoch||0)+1;this.stopCamera();this._ensureLiveSubscription?.();this._resetFinalizationContext?.();
      this._editing=false;this._walletData=null;this._walletRound=null;this._loadedRound=null;this._homeTicketId=null;this._walletSlideId=null;
      this._queueLiveRefresh?.(true);
    };
    this.node('check').onclick=()=>this.operation(async()=>{
      this.message('새 추첨 결과를 확인하고 있어요.');this.updateResults(await this.request('result_check'));
      // result_check may return the server's selected round, not the visible wallet round.
      await this.refreshStatus();this.message('확인했어요. 화면 자동 갱신은 꺼져 있습니다.');
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
    this.node('edit-wallet').onclick=async()=>{if(this._walletSlideId&&this._walletSlideId!==this._ticketId)await this.operation(()=>this.load(this._walletRound,this._walletSlideId));this.openEditor('edit');};
    this.node('delete-wallet').onclick=async()=>{if(this._walletSlideId&&this._walletSlideId!==this._ticketId)await this.operation(()=>this.load(this._walletRound,this._walletSlideId));await this.operation(()=>this.deleteWallet());};
    this.node('close-editor').onclick=()=>this.closeEditor();
    // The generated-number table re-renders on every live update, so one
    // delegated listener registers whichever row's button was pressed.
    this.node('current-recommendations').addEventListener('click',e=>{
      const button=e.target.closest?.('[data-register-generated]');
      if(!button||button.disabled)return;
      e.preventDefault();
      this.operation(()=>this.registerGenerated(button.dataset.methodId,Number(button.dataset.gameNo)||1));
    });
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
    else{this.message('사용할 로또 통합이 없어요. 상단 설정에서 통합을 추가해 주세요.',true);this.node('drawtitle').textContent='통합 설정 필요';this.node('numbers').textContent='연결된 로또 통합이 없어요.';this.node('connection').textContent='통합 설정 필요';this.renderMiniWallet({ticket_previews:[],purchased:{games:[]},generation_matches:[]});ticketRows(this.node('wallet-games'),[]);}
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
    this._photoExpectedGames=null;
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
  miniSwiperSlides() {
    return [...(this.node('mini-swiper-track')?.querySelectorAll('.ticket-slide')||[])];
  }
  updateMiniSwiperState() {
    const track=this.node('mini-swiper-track'),slides=this.miniSwiperSlides();
    if(!track||!slides.length)return;
    let index=0,distance=Infinity;
    slides.forEach((slide,i)=>{const d=Math.abs(slide.offsetLeft-track.scrollLeft);if(d<distance){distance=d;index=i;}});
    this._homeTicketId=slides[index].dataset.ticketId||null;
    const dots=[...(this.node('mini-swiper-dots')?.children||[])];
    dots.forEach((dot,i)=>{dot.dataset.active=String(i===index);dot.setAttribute('aria-current',i===index?'true':'false');});
    const status=this.node('mini-swiper-status');if(status)status.textContent=`${index+1} / ${slides.length}`;
    const prev=this.node('mini-prev'),next=this.node('mini-next');
    if(prev)prev.disabled=index===0;if(next)next.disabled=index===slides.length-1;
  }
  moveMiniSwiper(delta) {
    const track=this.node('mini-swiper-track'),slides=this.miniSwiperSlides();
    if(!track||slides.length<2)return;
    let index=slides.findIndex(slide=>slide.dataset.ticketId===this._homeTicketId);
    if(index<0)index=0;index=Math.max(0,Math.min(slides.length-1,index+delta));
    const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    track.scrollTo({left:slides[index].offsetLeft,behavior:reduce?'auto':'smooth'});
  }
  renderMiniWallet(data) {
    const track=this.node('mini-swiper-track'),nav=this.node('mini-swiper-nav'),dots=this.node('mini-swiper-dots');
    if(!track||!nav||!dots)return;
    const round=Number(data.draw_schedule?.round||data.recommendation_target);
    const detailed=Array.isArray(data.upcoming_ticket_previews)?data.upcoming_ticket_previews:[];
    const fallback=data.upcoming_purchased?.games?.length?[{
      ticket_id:'',ticket_number:1,game_count:data.upcoming_purchased.games.length,
      status:data.upcoming_purchased.status,highest_prize:data.upcoming_purchased.highest_prize,games:data.upcoming_purchased.games,
    }]:[];
    const tickets=detailed.length?detailed:fallback;
    const matches=Array.isArray(data.generation_matches)?data.generation_matches:[];
    track.replaceChildren();dots.replaceChildren();
    this.node('mini-swiper')?.setAttribute('aria-label',tickets.length?`등록한 복권 ${tickets.length}장`:'등록한 복권 없음');
    if(!tickets.length){
      const card=document.createElement('article');card.className='ticket-paper ticket-slide';
      const top=document.createElement('div');top.className='paper-top';
      const label=document.createElement('span');label.className='paper-label';label.textContent=formatRound(round);
      const meta=document.createElement('span');meta.className='paper-meta';meta.textContent='0장 · 0게임';
      const list=document.createElement('div');list.className='empty';const strong=document.createElement('strong');strong.textContent=`${formatRound(round)}에 등록한 구매 복권이 없습니다.`;const p=document.createElement('p');p.textContent='등록한 복권은 추첨 후 자동 대조됩니다.';list.append(strong,p);
      top.append(label,meta);card.append(top,list);track.append(card);nav.hidden=true;this._homeTicketId=null;return;
    }
    const active=tickets.some(ticket=>ticket.ticket_id===this._homeTicketId)
      ?this._homeTicketId
      :tickets[0].ticket_id;
    tickets.forEach((ticket,index)=>{
      const card=document.createElement('article');card.className='ticket-paper ticket-slide';card.dataset.ticketId=ticket.ticket_id||'';
      card.setAttribute('role','group');card.setAttribute('aria-roledescription','slide');
      card.setAttribute('aria-label',`복권 ${index+1} / ${tickets.length}`);
      const top=document.createElement('div');top.className='paper-top';
      const label=document.createElement('span');label.className='paper-label';label.textContent=`${formatRound(round)} · 복권 ${index+1}`;
      const meta=document.createElement('span');meta.className='paper-meta';meta.textContent=`${ticket.game_count||0}게임 · ${index+1}/${tickets.length}장`;
      top.append(label,meta);
      const list=document.createElement('div');list.className='ticket-list';
      ticketRows(list,ticket.games||[],Infinity,matches);
      const bottom=document.createElement('div');bottom.className='paper-bottom';
      const note=document.createElement('span');note.textContent=`${formatRound(round)} 추첨 후 자동 대조됩니다.`;
      const manage=document.createElement('button');manage.type='button';manage.textContent='전체 보기 ›';
      manage.onclick=()=>this.operation(async()=>{this._homeTicketId=ticket.ticket_id;await this.load(round,ticket.ticket_id);this.showScreen('wallet',true);});
      bottom.append(note,manage);card.append(top,list,bottom);track.append(card);
      const dot=document.createElement('button');dot.type='button';dot.className='swiper-dot';
      dot.setAttribute('aria-label',`복권 ${index+1} 보기`);dot.dataset.active=String(ticket.ticket_id===active);
      dot.onclick=()=>{const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;track.scrollTo({left:card.offsetLeft,behavior:reduce?'auto':'smooth'});};
      dots.append(dot);
    });
    nav.hidden=tickets.length<=1;this._homeTicketId=active;
    track.onscroll=()=>{if(this._miniSwiperFrame)cancelAnimationFrame(this._miniSwiperFrame);this._miniSwiperFrame=requestAnimationFrame(()=>{this._miniSwiperFrame=0;this.updateMiniSwiperState();});};
    requestAnimationFrame(()=>{const target=this.miniSwiperSlides().find(slide=>slide.dataset.ticketId===active)||this.miniSwiperSlides()[0];if(target)track.scrollLeft=target.offsetLeft;this.updateMiniSwiperState();});
  }
  walletSwiperSlides() {
    return [...(this.node('wallet-swiper-track')?.querySelectorAll('.wallet-ticket-card')||[])];
  }
  updateWalletSwiperState() {
    const track=this.node('wallet-swiper-track'),slides=this.walletSwiperSlides();
    if(!track||!slides.length)return;
    let index=0,distance=Infinity;
    slides.forEach((slide,i)=>{const d=Math.abs(slide.offsetLeft-track.scrollLeft);if(d<distance){distance=d;index=i;}});
    this._walletSlideId=slides[index].dataset.ticketId||null;
    const dots=[...(this.node('wallet-swiper-dots')?.children||[])];
    dots.forEach((dot,i)=>{dot.dataset.active=String(i===index);dot.setAttribute('aria-current',i===index?'true':'false');});
    const status=this.node('wallet-swiper-status');if(status)status.textContent=`${index+1} / ${slides.length}`;
    const prev=this.node('wallet-prev'),next=this.node('wallet-next');
    if(prev)prev.disabled=index===0;if(next)next.disabled=index===slides.length-1;
    const select=this.node('wallet-ticket');if(select&&this._walletSlideId&&[...select.options].some(o=>o.value===this._walletSlideId))select.value=this._walletSlideId;
  }
  moveWalletSwiper(delta) {
    const track=this.node('wallet-swiper-track'),slides=this.walletSwiperSlides();
    if(!track||slides.length<2)return;
    let index=slides.findIndex(slide=>slide.dataset.ticketId===this._walletSlideId);
    if(index<0)index=0;index=Math.max(0,Math.min(slides.length-1,index+delta));
    const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    track.scrollTo({left:slides[index].offsetLeft,behavior:reduce?'auto':'smooth'});
  }
  renderWalletCards(data) {
    const track=this.node('wallet-swiper-track'),nav=this.node('wallet-swiper-nav'),dots=this.node('wallet-swiper-dots');
    if(!track||!nav||!dots)return;
    const tickets=Array.isArray(data.ticket_previews)?data.ticket_previews:[];
    const round=Number(data.round);
    const matches=round===Number(data.recommendation_target)&&Array.isArray(data.generation_matches)?data.generation_matches:[];
    track.replaceChildren();dots.replaceChildren();
    this.node('wallet-swiper')?.setAttribute('aria-label',Number.isInteger(round)?`${formatRound(round)} 구매 복권`:'구매 복권');
    if(!tickets.length){
      const card=document.createElement('article');card.className='ticket-paper wallet-ticket-card ticket-slide';
      const top=document.createElement('div');top.className='paper-top';
      const label=document.createElement('span');label.className='paper-label';label.textContent=formatRound(round);
      const meta=document.createElement('span');meta.className='paper-meta';meta.textContent='0장 · 0게임';
      const empty=document.createElement('div');empty.className='empty';
      const strong=document.createElement('strong');strong.textContent=Number.isInteger(round)?`${formatRound(round)}에 등록한 구매 복권이 없습니다.`:'등록한 구매 복권이 없습니다.';
      const p=document.createElement('p');p.textContent='복권 등록을 눌러 QR·사진·직접 입력으로 추가할 수 있습니다.';
      empty.append(strong,p);top.append(label,meta);card.append(top,empty);track.append(card);
      nav.hidden=true;this._walletSlideId=null;return;
    }
    const active=tickets.some(ticket=>ticket.ticket_id===this._walletSlideId)
      ?this._walletSlideId
      :(tickets.some(ticket=>ticket.ticket_id===data.ticket_id)?data.ticket_id:tickets[0].ticket_id);
    tickets.forEach((ticket,index)=>{
      const card=document.createElement('article');card.className='ticket-paper wallet-ticket-card ticket-slide';card.dataset.ticketId=ticket.ticket_id||'';
      card.setAttribute('role','group');card.setAttribute('aria-roledescription','slide');card.setAttribute('aria-label',`복권 ${index+1} / ${tickets.length}`);
      const top=createReceiptHeader(card,round,ticket,index,tickets.length);
      const list=document.createElement('div');list.className='ticket-list receipt-lines';ticketRows(list,ticket.games||[],Infinity,matches,true);decorateReceiptRows(list);
      card.append(createReceiptSheet(top,list,receiptLegend(list),createReceiptTotal(round,ticket,index)));
      if(ticket.status==='evaluated'){
        const details=document.createElement('details');details.className='ticket-review';
        const totalMatches=(ticket.games||[]).reduce((sum,g)=>sum+(Number.isFinite(Number(g.main_match_count))?Number(g.main_match_count):0),0);
        const winners=(ticket.games||[]).filter(g=>Number.isInteger(g.prize_rank)&&g.prize_rank>=1&&g.prize_rank<=5).length;
        const summary=document.createElement('summary');summary.textContent=`${ticket.game_count||0}게임 중 당첨 ${winners}게임 · 최고 ${ticket.highest_prize||'미당첨'} · 본번호 총 일치 ${totalMatches}개`;
        const body=document.createElement('div');body.className='ticket-review-body';
        for(const game of ticket.games||[]){
          const line=document.createElement('div');line.className='ticket-review-line';
          const slot=document.createElement('strong');slot.textContent=game.slot||'';
          const outcome=document.createElement('span');outcome.textContent=game.prize||'미당첨';
          const links=formulaLinkLabels(game.formula_links);
          const info=document.createElement('small');info.textContent=`본번호 ${Number(game.main_match_count)||0}개 일치${game.bonus_match?' · 보너스 일치':''}${links.length?` · 구매 당시 생성 공식: ${links.join(', ')}`:''}`;
          line.append(slot,outcome,info);body.append(line);
        }
        details.append(summary,body);card.append(details);
      }
      const actions=document.createElement('div');actions.className='ticket-card-actions';
      const edit=document.createElement('button');edit.type='button';edit.className='soft-blue';edit.textContent='번호 수정';
      edit.onclick=async()=>{if(ticket.ticket_id!==this._ticketId)await this.operation(()=>this.load(round,ticket.ticket_id));this.openEditor('edit');};
      const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent=`${formatRound(round)} · 복권 ${index+1} 삭제`;
      remove.onclick=async()=>{if(ticket.ticket_id!==this._ticketId)await this.operation(()=>this.load(round,ticket.ticket_id));await this.operation(()=>this.deleteWallet());};
      actions.append(edit,remove);card.append(actions);track.append(card);
      const dot=document.createElement('button');dot.type='button';dot.className='swiper-dot';dot.setAttribute('aria-label',`복권 ${index+1} 보기`);dot.dataset.active=String(ticket.ticket_id===active);
      dot.onclick=()=>{const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;track.scrollTo({left:card.offsetLeft,behavior:reduce?'auto':'smooth'});};dots.append(dot);
    });
    nav.hidden=tickets.length<=1;this._walletSlideId=active;
    track.onscroll=()=>{if(this._walletSwiperFrame)cancelAnimationFrame(this._walletSwiperFrame);this._walletSwiperFrame=requestAnimationFrame(()=>{this._walletSwiperFrame=0;this.updateWalletSwiperState();});};
    requestAnimationFrame(()=>{const target=this.walletSwiperSlides().find(slide=>slide.dataset.ticketId===active)||this.walletSwiperSlides()[0];if(target)track.scrollLeft=target.offsetLeft;this.updateWalletSwiperState();});
  }

  applyWallet(data) {
    this._walletData=data;this._walletRound=Number(data.round)||null;this._ticketId=data.ticket_id||null;
    const slips=this.node('wallet-ticket');slips.replaceChildren();
    (data.tickets||[]).forEach((ticket,index)=>{const o=document.createElement('option');o.value=ticket.ticket_id;o.textContent=`복권 ${index+1} · ${ticket.game_count}게임`;slips.append(o);});
    if(this._ticketId)slips.value=this._ticketId;
    this.node('export-wallet').disabled=!(data.stored_rounds||[]).length;
    this.node('ticket-round').textContent=formatRound(data.round);
    this.node('wallet-count').textContent=`${data.purchased?.games?.length||0}게임 · ${data.tickets?.length||0}장`;
    this.renderWalletCards(data);
    const select=this.node('wallet-round');const rounds=[...new Set([data.round,data.recommendation_target,...(data.stored_rounds||[])].map(Number).filter(n=>Number.isInteger(n)&&n>0))].sort((a,b)=>b-a);
    const signature=rounds.join(',');
    if(this._roundSignature!==signature){select.replaceChildren();for(const n of rounds){const option=document.createElement('option');option.value=String(n);option.textContent=formatRound(n);select.append(option);}this._roundSignature=signature;}
    select.value=String(data.round||'');this.syncAvailability();
  }
  renderReviewSummary(data) {
    this._reviewData=data;
    const reviews=Array.isArray(data.reviews)?data.reviews:[];
    const filter=this.node('review-filter')?.value||'all',sort=this.node('review-sort')?.value||'total';
    const recentAverage=row=>{const items=(row.history_preview||[]).slice(-5).map(item=>Number(item.review_score)).filter(Number.isFinite);return items.length?items.reduce((a,b)=>a+b,0)/items.length:null;};
    const bestExact=row=>Math.max(-1,...(row.history_preview||[]).map(item=>Number(item.exact_match_count)).filter(Number.isFinite));
    const scoreOf=row=>Number.isFinite(Number(row.total_score))?Number(row.total_score):0;
    const rated=reviews.filter(row=>(Number(row.reviewed_rounds)||0)>0);
    const rankMap=new Map(rated.map(row=>[row.method_id,1+rated.filter(other=>scoreOf(other)>scoreOf(row)).length]));
    let visible=reviews.filter(row=>filter==='all'||row.tier===filter);
    visible=[...visible].sort((a,b)=>{
      if(sort==='recent')return (recentAverage(b)??-1)-(recentAverage(a)??-1)||String(a.label).localeCompare(String(b.label),'ko');
      if(sort==='count')return (Number(b.reviewed_rounds)||0)-(Number(a.reviewed_rounds)||0)||String(a.label).localeCompare(String(b.label),'ko');
      if(sort==='name')return String(a.label).localeCompare(String(b.label),'ko');
      return scoreOf(b)-scoreOf(a)||(Number(b.mean_score)||0)-(Number(a.mean_score)||0)||String(a.label).localeCompare(String(b.label),'ko');
    });
    this._visibleReviewRows=visible;
    const rows=visible.map(row=>{
      const recent=recentAverage(row),best=bestExact(row),reviewed=Number(row.reviewed_rounds)||0;
      return [
        reviewed?rankMap.get(row.method_id)||'—':'—',
        row.label||row.method_id,
        reviewed,
        row.mean_score!==null&&row.mean_score!==undefined&&Number.isFinite(Number(row.mean_score))?`${Number(row.mean_score).toFixed(1)}점`:'—',
        best>=0?`${best}개`:'—',
        recent===null?'—':`${recent.toFixed(1)}점`,
        row.stars!==null&&row.stars!==undefined&&Number.isFinite(Number(row.stars))?`★${Number(row.stars).toFixed(1)}`:'—'
      ];
    });
    renderRows(this.node('reviews'),rows,['누적 순위','공식명','평가 회차 수','평균 점수','최고 일치 기록','최근 5회 평균','누적 별점'],['아직 누적된 공식 리뷰가 없습니다.','공식 확인된 회차부터 누적 평가합니다.']);
    this.node('method-count').textContent=`${reviews.length}개 공식`;
    let status=data.review_storage_error?'리뷰 기록을 불러오지 못했습니다. 기존 기록은 보존됩니다.':data.review_save_pending?'추천번호 저장을 다시 시도하고 있습니다.':'공식 확인이 끝난 회차만 누적 평점에 반영합니다.';
    if(reviews.some(row=>row.unrated_result))status+=' 추첨 전 생성 여부가 확인되지 않은 과거 기록은 누적평가에서 제외합니다.';
    this.node('reviewstatus').textContent=status;
    this._panelTools?.decorate?.('reviews',visible);
  }
  updateResults(data) {
    const draw=data.draw,meta=data.result_verification||{};
    const lastPresentation=lastReviewPresentation(data);
    const currentRows=currentRecommendations(data);
    renderCurrentRecommendationRows(this.node('current-recommendations'),currentRows,['현재 생성번호가 없습니다.','공식 선택과 서비스 연결을 확인하세요. 기존 리뷰 기록은 보존됩니다.']);
    this.node('current-recommendations-heading').textContent=`${formatRound(data.recommendation_target)} · 현재 생성번호`;
    const serviceStatus=data.service_status;
    this.node('current-recommendations-note').textContent=(serviceStatus==='generating'?'새 번호를 생성 중입니다. 이전 생성번호를 유지합니다. ':serviceStatus&&serviceStatus!=='ready'?`서비스 상태: ${serviceStatus} · 저장된 생성번호를 표시합니다. `:'')+'이번 회차를 위해 현재 선택된 공식이 생성한 번호입니다. 추첨 발표 후 자동으로 평가됩니다.';
    this._targetRound=Number(data.recommendation_target||data.draw_schedule?.round)||this._targetRound;
    const upcomingRound=Number(data.draw_schedule?.round||data.recommendation_target);
    this.node('upcoming-round').textContent=Number.isInteger(upcomingRound)?`다가오는 ${formatRound(upcomingRound)}`:'다가오는 회차 확인 중';
    const upcomingTickets=Array.isArray(data.upcoming_ticket_previews)?data.upcoming_ticket_previews:[];
    const upcomingGames=upcomingTickets.reduce((sum,ticket)=>sum+(Number(ticket.game_count)||0),0);
    const heroTicketSummary=this.node('hero-ticket-summary');
    const heroTicketTotal=this.node('hero-ticket-total');
    const heroTicketItems=this.node('hero-ticket-items');
    heroTicketItems.replaceChildren();
    if(upcomingTickets.length){
      heroTicketSummary.hidden=false;
      heroTicketTotal.textContent=`등록 복권 ${upcomingTickets.length}장 · ${upcomingGames}게임`;
      upcomingTickets.slice(0,4).forEach((ticket,index)=>{
        const chip=document.createElement('span');chip.className='hero-ticket-chip';
        chip.textContent=`복권 ${ticket.ticket_number||index+1} · ${Number(ticket.game_count)||0}게임`;
        heroTicketItems.append(chip);
      });
      if(upcomingTickets.length>4){
        const more=document.createElement('span');more.className='hero-ticket-chip';more.textContent=`+${upcomingTickets.length-4}장`;heroTicketItems.append(more);
      }
    }else{
      heroTicketSummary.hidden=true;
      heroTicketTotal.textContent='';
    }
    this.node('home-formula-status').textContent=currentRows.length
      ? `${currentRows.length}개 · 평가 대기`
      : '생성 없음';
    this.renderMiniWallet(data);
    this.node('drawtitle').textContent=data.result_round?formatRound(data.result_round):'지난 회차 확인 중';
    const numbers=this.node('numbers');numbers.removeAttribute('role');numbers.removeAttribute('aria-label');
    if(meta.status!=='conflict'&&draw)numberBalls(numbers,draw.numbers,draw.bonus);
    else numbers.textContent=meta.status==='conflict'?'출처를 확인 중입니다. 판정을 잠시 보류합니다.':'아직 확인된 지난 회차 당첨번호가 없습니다.';
    this.node('verification').textContent=labels[meta.status]||'발표 대기';
    this.node('verification').dataset.state=meta.status==='conflict'?'conflict':meta.status?.startsWith('official')?'verified':'pending';
    this.node('result').textContent=meta.status==='conflict'
      ? '출처가 일치하지 않아 결과 판정을 보류하고 있습니다.'
      : draw&&data.result_round?`${formatRound(data.result_round)} 당첨번호 확인 완료`:'지난 회차 공식 결과를 확인하고 있습니다.';
    const lastRows=lastPresentation.evaluated?lastPresentation.rows:[];
    renderReviewResultRows(this.node('predictions'),lastRows,['평가가 완료된 공식 결과가 없습니다.','추첨 전에 저장된 공식 생성번호만 결과 발표 후 평가합니다.']);
    this.node('predictions-heading').textContent=Number.isInteger(lastPresentation.round)?`${formatRound(lastPresentation.round)} · 공식 리뷰 결과`:'지난 회차 공식 리뷰 결과';
    this.node('predictions-note').textContent=lastPresentation.evaluated
      ? '추첨 전에 저장된 공식 생성번호를 실제 당첨번호와 비교한 결과입니다. 등록한 구매 복권은 포함하지 않습니다.'
      : '지난 회차 공식 결과가 확정되면 점수와 순위를 표시합니다.';
    const scored=lastRows.filter(row=>Number.isFinite(Number(row.review_score)));
    const top=[...scored].sort((a,b)=>(Number(b.review_score)||0)-(Number(a.review_score)||0)||(Number(b.exact_match_count)||0)-(Number(a.exact_match_count)||0)||String(a.sensor_name||'').localeCompare(String(b.sensor_name||''),'ko'))[0];
    const bestScore=scored.length?Math.max(...scored.map(row=>Number(row.review_score))):null;
    const avgExact=scored.length?scored.reduce((sum,row)=>sum+(Number(row.exact_match_count)||0),0)/scored.length:null;
    this.node('review-kpi-count').textContent=lastPresentation.evaluated?`${scored.length}개`:'—';
    this.node('review-kpi-score').textContent=bestScore===null?'—':`${bestScore.toFixed(1)}점`;
    this.node('review-kpi-exact').textContent=avgExact===null?'—':`${avgExact.toFixed(2)}개`;
    this.node('review-kpi-top').textContent=top?(top.sensor_name||top.method_id||'—'):'—';
    if(lastPresentation.evaluated){
      this.node('home-review-summary').textContent=`${formatRound(lastPresentation.round)} 공식 ${scored.length}개 평가 완료`;
      this.node('home-review-top').textContent=top?`1위 공식 · ${top.sensor_name||top.method_id}`:'평가 결과를 확인하세요.';
    }else{
      this.node('home-review-summary').textContent=Number.isInteger(lastPresentation.round)?`${formatRound(lastPresentation.round)} 공식 평가 확인 중`:'지난 회차 공식 평가를 기다리고 있습니다.';
      this.node('home-review-top').textContent='';
    }
    this.renderReviewSummary(data);
    const sources=this.node('sources');sources.replaceChildren();
    for(const source of meta.sources||[]){let url;try{url=new URL(source.url);}catch{continue;}if(!['https:','http:'].includes(url.protocol))continue;const a=document.createElement('a');a.textContent=`${source.publisher||'출처'} 발표 ↗`;a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';sources.append(a);}
    this.node('connection').dataset.online='true';this.node('connection').textContent='HA 연결됨';
    const now=new Intl.DateTimeFormat('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date());
    this.node('sync-status').textContent=`최근 확인 ${now} · 화면 자동 갱신 꺼짐`;
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
    this._photoExpectedGames=null;
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
    if(this._photoExpectedGames&&filled!==this._photoExpectedGames&&!window.confirm(`사진 금액은 ${this._photoExpectedGames}게임인데 현재 ${filled}게임만 입력되어 있어요. 원본을 확인했으며 이 번호만 저장할까요?`))return;
    // An explicit save is enough for a new record. Replacements require a second confirmation.
    if(this._revision&&!window.confirm(`${round}회에 저장된 A~E를 지금 확인한 번호로 교체할까요?`))return;
    const values={};slots.forEach(s=>values[`game_${s}`]=this.node(`game_${s}`).value);
    const data=await this.request('purchases_save',{round,values,revision:this._newTicket?'':this._revision,clear:false,new_ticket:this._newTicket,...((this._newTicket?this._newTicketId:this._ticketId)?{ticket_id:this._newTicket?this._newTicketId:this._ticketId}:{})});
    this._editing=false;this._newTicket=false;this.updateResults(data);this.applyWallet(data);this.restoreForm(data);this.finishClose(false);
    this.showScreen('wallet',true);this.message(`${round}회 ${filled}게임을 저장했어요. 추첨 결과가 확인되면 자동으로 대조합니다.`);
  }
  async registerGenerated(methodId, gameNo) {
    if(!methodId)throw new Error('생성 번호의 공식을 확인할 수 없습니다. 목록을 새로 고쳐 주세요.');
    const data=await this.request('register_generated',{method_id:methodId,game_no:gameNo});
    this.updateResults(data);this.applyWallet(data);this.renderMiniWallet(data);
    const registration=data.registration||{};
    const rows=registration.registered||[];
    if(rows.length){
      const slots=rows.map(row=>`${row.slot}번`).join(', ');
      const extra=registration.created_tickets?` 새 복권 ${registration.created_tickets}장도 만들었습니다.`:'';
      const skipped=registration.skipped?.length?` 이미 등록된 ${registration.skipped.length}개 게임은 건너뛰었습니다.`:'';
      this.message(`${data.round}회 ${slots} 줄에 등록했어요.${extra}${skipped}`);
    }else if(registration.skipped?.length){
      this.message('이미 등록된 번호라 건너뛰었어요.');
    }else{
      this.message('등록할 번호가 없습니다.');
    }
  }
  async deleteWallet() {
    const data=this._walletData;if(!data?.revision)return;
    const round=Number(data.round),index=Math.max(0,(data.tickets||[]).findIndex(ticket=>ticket.ticket_id===data.ticket_id));
    const label=`${formatRound(round)} · 복권 ${index+1}`;
    if(!window.confirm(`${label} 삭제할까요? 같은 회차의 다른 복권과 추천 기록은 유지됩니다.`))return;
    const result=await this.request('purchases_save',{round,values:data.values||{},revision:data.revision,clear:true,...(data.ticket_id?{ticket_id:data.ticket_id}:{})});
    this.updateResults(result);this.applyWallet(result);this.restoreForm(result);this.message(`${label}을 삭제했습니다.`);
  }
  decode(image,width,height) {
    if(!globalThis.jsQR)throw new Error('QR 판독기를 불러오지 못했습니다. QR 주소 붙여넣기를 이용하세요.');
    const canvas=document.createElement('canvas'),scale=Math.min(1,1600/Math.max(width,height));
    canvas.width=Math.max(1,Math.round(width*scale));canvas.height=Math.max(1,Math.round(height*scale));
    const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,canvas.width,canvas.height);
    const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
    return globalThis.jsQR(pixels.data,pixels.width,pixels.height,{inversionAttempts:'attemptBoth'})?.data;
  }
  // Online purchases have no QR code, so the bundled offline OCR reads the
  // printed numbers instead. The engine is fetched on first use only.
  ocrAssetBase() {
    const version=String(this._panel?.config?.version||'').trim();
    return `/lotto_645_frontend/${version||'latest'}/ocr`;
  }
  loadOcrEngine() {
    if(globalThis.Tesseract)return Promise.resolve(globalThis.Tesseract);
    if(this._ocrEngine)return this._ocrEngine;
    const base=this.ocrAssetBase();
    this._ocrEngine=new Promise((resolve,reject)=>{
      const script=document.createElement('script');
      script.src=`${base}/tesseract.min.js`;
      script.onload=()=>resolve(globalThis.Tesseract);
      script.onerror=()=>reject(new Error('번호 인식기를 불러오지 못했습니다. A~E로 직접 입력해 주세요.'));
      document.head.append(script);
    });
    return this._ocrEngine;
  }
  async ocrLines(image) {
    const Tesseract=await this.loadOcrEngine();
    const base=this.ocrAssetBase();
    if(!this._ocrWorker){
      // The LSTM-only core is bundled, so point at the exact file and keep the
      // traineddata beside it: no external request, no CDN dependency.
      this._ocrWorker=await Tesseract.createWorker('eng',1,{
        workerPath:`${base}/worker.min.js`,
        corePath:`${base}/tesseract-core-lstm.wasm.js`,
        langPath:base,
        logger:()=>{},
      });
    }
    const longest=Math.max(image.width||image.videoWidth,image.height||image.videoHeight)||1;
    const scale=Math.max(1,Math.min(2.5,1800/longest));
    const canvas=document.createElement('canvas');
    canvas.width=Math.max(1,Math.round((image.width||image.videoWidth)*scale));
    canvas.height=Math.max(1,Math.round((image.height||image.videoHeight)*scale));
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    ctx.imageSmoothingQuality='high';ctx.drawImage(image,0,0,canvas.width,canvas.height);
    await this._ocrWorker.setParameters({tessedit_pageseg_mode:'6'});
    const result=await this._ocrWorker.recognize(canvas);
    const rows=ticketRowsFromOcr(result?.data);
    if(rows.length>5)throw new Error('복권 게임 줄이 5줄보다 많아 구분하기 어렵습니다. 복권 한 장의 A~E 부분만 보이게 다시 선택하세요.');
    const complete=rows.filter(row=>row.valid);
    // A missing first/last number must stay inside the retry crop: use the
    // neighbouring complete rows' numeric column span as well.
    for(const row of rows.filter(row=>!row.valid)) {
      const aligned=complete.filter(other=>Math.abs(other.box.x1-row.box.x1)<canvas.width*.15||Math.abs(other.box.x0-row.box.x0)<canvas.width*.15);
      if(aligned.length){row.columns=aligned[0].columns;row.box.x0=Math.min(row.box.x0,...aligned.map(r=>r.box.x0));row.box.x1=Math.max(row.box.x1,...aligned.map(r=>r.box.x1));}
    }
    // Reread only incomplete physical rows. Isolating the numeric columns
    // avoids Korean labels and price/serial text, without guessing digits.
    try {
      for(const row of rows.filter(row=>!row.valid)) {
        const pad=Math.max(8,(row.box.y1-row.box.y0)*.4);
        const x=Math.max(0,Math.floor(row.box.x0-pad));
        const y=Math.max(0,Math.floor(row.box.y0-pad));
        const width=Math.min(canvas.width-x,Math.ceil(row.box.x1+pad-x));
        const height=Math.min(canvas.height-y,Math.ceil(row.box.y1+pad-y));
        const crop=document.createElement('canvas');crop.width=width*2;crop.height=height*2;
        const cropContext=crop.getContext('2d');cropContext.fillStyle='white';cropContext.fillRect(0,0,crop.width,crop.height);
        cropContext.drawImage(canvas,x,y,width,height,0,0,crop.width,crop.height);
        await this._ocrWorker.setParameters({tessedit_pageseg_mode:'7'});
        const reread=await this._ocrWorker.recognize(crop);
        let tokens=singleGameTokens(reread?.data);
        // Adjacent numbers such as 11 and 17 can merge into one OCR word.
        // If a neighbouring row gives six reliable columns, read those six
        // image regions independently. Never split a merged string by guess.
        if(!tokens&&row.columns.length===6) {
          const centers=row.columns.map(c=>(c.x0+c.x1)/2),cells=[];
          for(let index=0;index<6;index++) {
            const left=Math.max(0,Math.floor(index?(centers[index-1]+centers[index])/2:x));
            const right=Math.min(canvas.width,Math.ceil(index<5?(centers[index]+centers[index+1])/2:x+width));
            const cell=document.createElement('canvas');cell.width=(right-left)*3;cell.height=height*3;
            const cellContext=cell.getContext('2d');cellContext.fillStyle='white';cellContext.fillRect(0,0,cell.width,cell.height);
            cellContext.drawImage(canvas,left,y,right-left,height,0,0,cell.width,cell.height);
            const reading=await this._ocrWorker.recognize(cell);
            cells.push(String(reading?.data?.text||'').trim());
          }
          tokens=singleGameTokens({text:cells.join(' ')});
        }
        if(tokens){row.conflict=retryDisagrees(row.tokens,tokens);row.tokens=tokens;row.valid=true;}
      }
    } finally {
      await this._ocrWorker.setParameters({tessedit_pageseg_mode:'6'});
    }
    return {lines:ticketLinesFromRows(rows),expected_games:ticketExpectedGames(result?.data)};
  }
  async readPhoto() {
    const file=this.node('file').files[0];this.node('file').value='';if(!file)return;
    if(file.size>10*1024*1024 || !['image/png','image/jpeg','image/webp'].includes(file.type))throw new Error('10MB 이하의 PNG/JPEG/WebP 사진을 선택하세요.');
    const url=URL.createObjectURL(file);
    try {const im=new Image();im.src=url;await im.decode();if(im.width*im.height>40000000)throw new Error('사진이 너무 큽니다. 복권 부분만 잘라 선택하세요.');
      const value=this.decode(im,im.width,im.height);
      if(value){await this.preview(value);return;}
      // No QR code (online purchases): read the printed A-E numbers offline.
      this.message('사진에서 번호를 읽는 중이에요. 잠시만 기다려 주세요.');
      const reading=await this.ocrLines(im);
      const {lines}=reading;
      if(!lines.length)throw new Error('사진에서 복권 번호를 찾지 못했습니다. 선명한 사진으로 다시 찍거나 A~E로 직접 입력하세요.');
      await this.importOcrLines(lines,reading.expected_games);
    }
    finally{URL.revokeObjectURL(url);}
  }
  async importOcrLines(lines,expectedGames=null) {
    const round=this.selectedRound();
    const data=await this.request('purchases_import_ocr',{round,lines,preview:true,expected_games:expectedGames,revision:this._newTicket?'':this._revision,new_ticket:this._newTicket,...((this._newTicket?this._newTicketId:this._ticketId)?{ticket_id:this._newTicket?this._newTicketId:this._ticketId}:{})});
    const imported=data.imported||{};
    if(this._editing&&!window.confirm('저장하지 않은 입력을 사진에서 읽은 번호로 바꿀까요?'))return;
    // Keep the current ticket/revision and do not touch stored purchases until
    // the user checks the photo draft and presses the ordinary atomic Save.
    slots.forEach(s=>this.node(`game_${s}`).value=imported.values?.[`game_${s}`]||'');
    this._photoExpectedGames=expectedGames;
    this._editing=true;this._touched.clear();
    this.showGameSlots(Math.max(expectedGames||0,slots.map(s=>!!this.node(`game_${s}`).value.trim()).lastIndexOf(true)+1));
    this.updateFormStatus();this.showEditorStep('edit');
    const missing=(imported.missing_slots||[]).join(', ');
    const warning=imported.needs_review?` ${missing?`${missing} 줄 등 `:''}일부 번호를 확인하지 못했어요. 원본과 비교해 빠진 줄을 입력하거나 다시 촬영해 주세요.`:'';
    this.message(`${round}회 ${imported.game_count||0}게임을 읽었어요. 아직 저장하지 않았어요.${warning} 회차와 A~E 번호를 확인한 뒤 저장을 눌러 주세요.`,Boolean(imported.needs_review));
    this._focusAfter=missing&&/^[A-E]$/.test(missing)?`game_${missing.toLowerCase()}`:'game_a';
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
