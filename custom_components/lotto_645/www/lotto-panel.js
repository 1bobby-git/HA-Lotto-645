/* Local-only QR camera/photo decoding. Purchases use authenticated HA websocket. */
import './jsQR.js';

const label = {
  waiting: '새 회차 결과 발표 대기', provisional: '속보 기준 · 공식 미대조',
  cross_checked: '복수 언론 일치 · 공식 미대조', conflict: '출처 불일치 · 판정 대기',
  official_history: '공식 이력 기준', official_confirmed: '공식 이력 대조 완료',
  official_corrected: '공식 이력으로 정정됨'
};

class LottoTicketPanel extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); this._revision=''; this._editing=false; }
  set hass(value) { this._hass=value; this._start(); }
  set panel(value) { this._panel=value; this._start(); }
  connectedCallback() { this._visibility=()=>{if(document.hidden)this.stopCamera();};document.addEventListener('visibilitychange',this._visibility);this._start(); }
  disconnectedCallback() { document.removeEventListener('visibilitychange',this._visibility); this.stopCamera(); clearInterval(this._poll); this._poll=null; }
  _start() {
    if (!this._hass || !this._panel || !this.isConnected) return;
    if (!this.shadowRoot.firstChild) this.render();
    if (!this._poll) this._poll=setInterval(() => { if (!this._busy && !document.hidden) this.operation(()=>this.refreshStatus()); },30000);
  }
  node(id) { return this.shadowRoot.getElementById(id); }
  message(text, error=false) { const n=this.node('message'); n.textContent=text; n.setAttribute('role',error?'alert':'status'); }
  async request(type,extra={}) { return this._hass.callWS({type:`lotto_645/${type}`,entry_id:this.node('entry').value,...extra}); }
  async operation(action) {
    if (this._busy) return;
    this._busy=true;
    for (const n of this.shadowRoot.querySelectorAll('button')) n.disabled=true;
    try { await action(); } catch(e) { this.message(e.message || '작업을 완료하지 못했습니다.',true); }
    finally { this._busy=false; for (const n of this.shadowRoot.querySelectorAll('button')) n.disabled=false; }
  }
  render() {
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100%;font-family:var(--paper-font-body1_-_font-family,system-ui)}
      main{max-width:780px;margin:0 auto;padding:24px 16px 60px}h1{font-size:24px}h2{font-size:19px;margin-top:0}.box{background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:14px;padding:20px;margin:16px 0}
      label{display:block;margin:14px 0 6px;font-weight:600}input,textarea,select{box-sizing:border-box;width:100%;padding:13px;border-radius:8px;border:1px solid var(--divider-color);background:var(--primary-background-color);color:inherit;font:inherit}input{font-variant-numeric:tabular-nums}textarea{min-height:76px}
      .row{display:flex;flex-wrap:wrap;gap:10px}button{font:inherit;padding:11px 15px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer}button.primary{background:var(--primary-color);color:var(--text-primary-color,#fff)}button:disabled{opacity:.6;cursor:wait}
      :focus-visible{outline:3px solid var(--primary-color);outline-offset:3px}small,.note{line-height:1.65;opacity:.85}.numbers{font-size:22px;line-height:1.8;font-weight:700;overflow-wrap:anywhere}#message{padding:12px 0;min-height:22px;white-space:pre-line}video{width:100%;max-height:380px;object-fit:contain}table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:9px 5px;border-bottom:1px solid var(--divider-color)}.scroll{overflow-x:auto}#camera[hidden]{display:none}
    </style><main><h1>로또 복권</h1><p class="note">구매번호 5게임과 추천 결과를 회차별로 대조합니다. QR 사진은 브라우저 안에서만 읽습니다. 실제 구매·지급을 인증하는 기능은 아닙니다.</p>
      <label for="entry">로또 통합</label><select id="entry"></select><div id="message" role="status" aria-live="polite"></div>
      <section class="box"><h2 id="drawtitle">추첨번호</h2><div class="numbers" id="numbers">확인 중</div><p id="verification"></p><p id="result"></p><div id="sources"></div><button id="check">추첨 결과 지금 확인</button><p class="note">공개 결과를 찾으면 자동 반영합니다. 속보 판정은 공식 이력 수신 후 다시 대조됩니다. 사이트 게시 지연·접근 제한에 따라 수신이 늦어질 수 있습니다.</p></section>
      <section class="box"><h2>복권 QR로 입력</h2><div class="row"><button id="scan">카메라로 QR 스캔</button><button id="photo">QR 사진 선택</button><input id="file" type="file" accept="image/png,image/jpeg,image/webp" hidden></div>
      <div id="camera" hidden><video id="video" autoplay muted playsinline></video><button id="stop">카메라 종료</button></div>
      <label for="qr">또는 휴대폰 카메라로 읽은 QR 주소 붙여넣기</label><textarea id="qr" maxlength="2048" placeholder="https://qr.dhlottery.co.kr/?v=..."></textarea><button id="preview">QR 번호 미리보기</button><p class="note">QR은 주소를 방문하지 않고 회차·번호만 읽습니다. 아래 A~E를 확인한 뒤 저장하세요.</p></section>
      <section class="box"><h2>직접 구매번호 A~E</h2><label for="round">복권에 적힌 회차</label><input id="round" inputmode="numeric" type="text" maxlength="6"><button id="load">해당 회차 불러오기</button><p id="savedrounds" class="note"></p><div id="games"></div>
      <p class="note">예: 1, 7, 15, 24, 33, 45 / 1 7 15 24 33 45 / 010715243345. 게임당 중복 없는 6개 번호, 최대 5게임입니다. 빈 줄은 저장하지 않습니다. 같은 회차의 A~E는 저장할 때 교체됩니다.</p>
      <div class="row"><button id="save" class="primary">확인한 번호 저장</button><button id="clear">이 회차 구매번호 삭제</button></div><div class="scroll"><table><caption>저장한 구매번호의 회차별 판정</caption><thead><tr><th>게임</th><th>번호</th><th>결과</th></tr></thead><tbody id="outcomes"></tbody></table></div></section>
      <section class="box"><h2>추천 센서별 판정</h2><div class="scroll"><table><thead><tr><th>추천 방식</th><th>번호</th><th>결과</th></tr></thead><tbody id="predictions"></tbody></table></div></section><section class="box"><h2>방식별 누적 리뷰</h2><p class="note">추첨 전 저장한 실제 추천만 평가합니다. 공식 확인 회차의 평균점수 ÷ 20이 별점입니다. ±1은 유사도일 뿐 당첨이 아닙니다. 속보 점수는 잠정이며 누적평균과 분리합니다. 표본이 적은 별점은 미래 예측력을 뜻하지 않습니다.</p><p id="reviewstatus"></p><div class="scroll"><table><thead><tr><th>추천 방식 / 누적 별점</th><th>평가 회차</th><th>이번 회차</th><th>정확 / ±1</th><th>순위</th></tr></thead><tbody id="reviews"></tbody></table></div></section></main>`;
    const config=this._panel.config || {};
    for (const [id,name] of Object.entries(config.entries || {})) {const n=document.createElement('option');n.value=id;n.textContent=name;this.node('entry').append(n);}
    for (const s of 'abcde') {
      const l=document.createElement('label'); l.htmlFor=`game_${s}`; l.textContent=`${s.toUpperCase()} · 번호 6개`;
      const n=document.createElement('input'); n.id=`game_${s}`; n.inputMode='numeric'; n.maxLength=100;
      n.addEventListener('input',()=>this._editing=true);this.node('games').append(l,n);
    }
    this.node('round').addEventListener('input',()=>{this._editing=true;this._loadedRound=null;});
    this.node('load').onclick=()=>this.operation(()=>this.load(true));
    this.node('entry').onchange=()=>this.operation(async()=>{this._editing=false;this._loadedRound=null;this.node('round').value='';await this.load(true);});
    this.node('save').onclick=()=>this.operation(()=>this.save(false));
    this.node('clear').onclick=()=>this.operation(()=>this.save(true));
    this.node('check').onclick=()=>this.operation(async()=>{this.message('공개된 추첨 결과를 확인하고 있습니다.');this.updateResults(await this.request('result_check'));this.message('확인 완료. 새 결과가 아직 없으면 자동 확인을 계속합니다.');});
    this.node('preview').onclick=()=>this.operation(()=>this.preview(this.node('qr').value));
    this.node('scan').onclick=()=>this.operation(()=>this.startCamera());
    this.node('stop').onclick=()=>this.stopCamera();
    this.node('photo').onclick=()=>this.node('file').click();
    this.node('file').onchange=()=>this.operation(()=>this.readPhoto());
    this.operation(()=>this.load(true));
  }
  selectedRound() {const raw=this.node('round').value.trim();if(!/^[0-9]{1,6}$/.test(raw)||+raw<1)throw new Error('회차를 숫자로 입력하세요.');return +raw;}
  async load(explicit=false) {
    const raw=this.node('round').value.trim();
    const data=await this.request('purchases_get',raw?{round:this.selectedRound()}:{});
    this.updateResults(data);
    if (!this._editing || explicit) {
      this.node('round').value=data.round || data.recommendation_target || '';
      this._loadedRound=Number(this.node('round').value);this._revision=data.revision;
      for (const s of 'abcde') this.node(`game_${s}`).value=data.values[`game_${s}`] || '';
      this._editing=false;
    }
    this.node('savedrounds').textContent='저장된 회차: '+(data.stored_rounds.join(', ')||'없음');
    this.rows('outcomes',(data.purchased.games||[]).map(g=>[g.slot,(g.numbers||g.recommended_numbers||[]).join(', '),g.prize||'추첨 대기']));
    if(data.storage_error)this.message('구매번호 저장소를 확인해야 합니다. 기존 파일은 덮어쓰지 않습니다.',true);
  }
  async refreshStatus() {
    // Result/review updates never replace an unfinished purchase form or revision.
    const data=await this.request('purchases_get',this._loadedRound?{round:this._loadedRound}:{});
    this.updateResults(data);
  }
  rows(id,rows) {const root=this.node(id);root.replaceChildren();for(const row of rows){const tr=document.createElement('tr');for(const v of row){const td=document.createElement('td');td.textContent=String(v??'');tr.append(td);}root.append(tr);}}
  updateResults(data) {
    const d=data.draw, meta=data.result_verification||{};
    this.node('drawtitle').textContent=(data.result_round ? data.result_round+'회 ' : '')+'추첨번호';
    this.node('numbers').textContent=meta.status==='conflict'?'출처 불일치 · 확인 대기':d ? d.numbers.join(', ')+' + 보너스 '+d.bonus:'결과 대기';
    this.node('verification').textContent=label[meta.status]||'발표 대기';
    const w=data.winning;this.node('result').textContent=w?.status==='evaluated'?`${w.round}회 당첨 여부: ${w.winning_game_count}개 당첨 · 최고 ${w.highest_prize}`:w?.status==='conflict'?'당첨 판정 보류':'대조할 추첨 전 추천 또는 구매번호가 아직 없습니다.';
    this.rows('predictions',(w?.results||[]).filter(g=>g.source!=='purchased').map(g=>[g.sensor_name,g.recommended_numbers.join(', '),g.prize]));
    const roundReview=data.review_round||{};
    const current=new Map((roundReview.methods||[]).map(r=>[r.method_id,r]));
    this.rows('reviews',(data.reviews||[]).map(r=>{
      const now=current.get(r.method_id);
      return [r.display_name,r.reviewed_rounds||0,now?`${roundReview.status==='provisional'?'잠정 ':''}${now.review_score.toFixed(1)}점`:'평가 대기',now?`${now.exact_match_count}개 / ${now.near_match_count}개`:'—',now?`${now.rank_this_round}/${roundReview.peer_count}`:'—'];
    }));
    this.node('reviewstatus').textContent=data.review_storage_error?'리뷰 저장소 오류: 기존 파일을 보존하며 새 점수를 누적하지 않습니다.':data.review_save_pending?'리뷰 저장 재시도 대기 중입니다. 현재 점수는 아직 저장되지 않았을 수 있습니다.':(roundReview.round?`${roundReview.round}회 결과 대조. 누적 별점에는 공식 확인된 회차만 포함합니다.`:'리뷰할 추첨 전 추천이 아직 없습니다.');
    const sourceRoot=this.node('sources');sourceRoot.replaceChildren();for(const s of meta.sources||[]){const a=document.createElement('a');a.textContent=s.publisher+' 발표 ';a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';sourceRoot.append(a);}
  }
  async preview(qr) {
    const result=await this.request('qr_preview',{qr});
    this.node('round').value=result.round;this._loadedRound=result.round;this._revision=result.revision;
    for(const s of 'abcde')this.node(`game_${s}`).value=result.values[`game_${s}`]||'';
    this.node('qr').value='';this._editing=true;
    this.message(`${result.round}회 ${result.game_count}게임을 읽었습니다. 아직 저장하지 않았습니다. 번호를 확인하고 저장하세요.`+(result.will_replace?' 이 회차에 저장된 번호가 있어 교체됩니다.':''));
    this.node('game_a').focus();
  }
  async save(clear) {
    const round=this.selectedRound();
    if(this._loadedRound!==round)throw new Error('먼저 해당 회차 불러오기를 누르세요. 다른 회차의 번호가 의도치 않게 덮어써지는 것을 막습니다.');
    if(!window.confirm(clear?`${round}회 구매번호만 삭제할까요?`:`${round}회 A~E 구매번호를 확인한 내용으로 저장할까요?`))return;
    const values={};for(const s of 'abcde')values[`game_${s}`]=this.node(`game_${s}`).value;
    await this.request('purchases_save',{round,values,revision:this._revision,clear});
    this._editing=false;await this.load(true);this.message(clear?'해당 회차만 삭제했습니다.':'구매번호를 HA에 저장했습니다. 추첨 결과가 확인되면 자동 대조합니다.');
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
    this.stopCamera();
    if(!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)throw new Error('이 환경에서 카메라를 열 수 없습니다. HTTPS로 접속하거나 QR 사진/주소 입력을 이용하세요.');
    this._stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});
    if(!this.isConnected){this.stopCamera();return;}
    this.node('camera').hidden=false;const video=this.node('video');video.srcObject=this._stream;await video.play();
    this.message('복권 오른쪽 위 QR을 카메라에 비춰주세요.');
    const tick=async()=>{
      if(!this._stream)return;
      try {if(video.readyState>=2){const value=this.decode(video,video.videoWidth,video.videoHeight);if(value){this.stopCamera();await this.operation(()=>this.preview(value));return;}}}
      catch(e){this.stopCamera();this.message(e.message,true);return;}
      this._scanTimer=setTimeout(tick,500);
    };
    this._scanTimer=setTimeout(tick,500);
  }
  stopCamera(){clearTimeout(this._scanTimer);if(this._stream){this._stream.getTracks().forEach(t=>t.stop());this._stream=null;}if(this.node('camera'))this.node('camera').hidden=true;}
}
if(!customElements.get('lotto-ticket-panel')) customElements.define('lotto-ticket-panel',LottoTicketPanel);
