/* Compact historical comparison. Live pre-draw scores retain their provenance. */
import { numberBalls } from './lotto-panel-view.js?v=1.15.0';
import { attachValidationDetails, DETAIL_STYLE } from './lotto-panel-validation-details.js?v=1.19.0';
const SAJU = 'myungri_hetu_day_pillar';
const AI = 'home_assistant_ai';
const VALIDATION_UI_VERSION = '1.19.0';
const RESET = '새 당첨회차가 공식 이력 또는 교차확인 결과로 확인되면 검증 횟수·점수·결과를 초기화합니다. 이미 리뷰에 반영한 과거검증 성과와 실제 추천 리뷰는 유지됩니다.';
const el = (tag, text, cls) => { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; };
const fmt = n => Number(n||0).toLocaleString('ko-KR');
const STYLE = `
.main-tabs{overflow-x:auto;scrollbar-width:none;max-width:100%}
#screen-validation{min-width:0}
#screen-validation .page-heading{margin-bottom:12px}
.validation-form,.validation-output{padding:16px;border:1px solid var(--line);border-radius:14px;background:var(--surface);min-width:0}
.validation-output{margin-top:12px}
.validation-notice{margin:0 0 12px;padding:10px 12px;background:var(--blue-soft);color:var(--ink);border-radius:10px;font-size:12px;line-height:1.6}
.validation-notice strong{display:block}
.validation-fields input{max-width:200px;min-height:44px;font-size:16px}
.validation-help,.validation-audit,.validation-status{color:var(--muted);font-size:12px;line-height:1.6;margin:6px 0;overflow-wrap:anywhere}
.validation-settings{margin:8px 0;border-block:1px solid var(--line);padding:2px 0}
.validation-settings summary,.validation-audit summary{min-height:44px;align-content:center;font-size:13px;font-weight:600;cursor:pointer}
.validation-settings button{font-size:12px;min-height:44px}
.validation-choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2px 12px;margin:6px 0;max-height:360px;overflow:auto}
.validation-advanced{grid-column:1/-1}
.validation-choice{display:flex;gap:8px;align-items:center;min-height:44px;margin:0;font-size:12px;line-height:1.5;overflow-wrap:anywhere}
.validation-choice input{width:20px;height:20px;min-height:20px;margin:0;flex:none;accent-color:var(--blue)}
.validation-status[data-error="true"]{color:var(--danger)}
.validation-status:empty{display:none}
.validation-draw{margin:6px 0 12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.validation-draw .draw-numbers{--ball-size:28px;gap:6px;min-height:48px;justify-content:flex-start}
.validation-draw .draw-numbers .ball{font-size:12px}
.validation-draw .bonus-group{gap:6px}
.validation-draw .bonus-caption{top:calc(100% + 3px);font-size:11px}
.validation-output h2{font-size:19px;margin:0}
.validation-toolbar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:8px 0}
.validation-toolbar label{margin:0;font-size:12px}
.validation-toolbar select{width:auto;max-width:100%;font-size:12px;min-height:44px;padding:7px 24px 7px 8px}
.validation-toolbar button{font-size:12px;min-height:44px;padding:7px 10px}
.validation-total{font-size:13px;font-weight:700;margin:6px 0}
#validation-summary{margin:6px 0;font-size:12px}
.validation-output table th:first-child{width:37%}
.validation-output table th:nth-child(2){width:34%}
.validation-output table th:last-child{width:29%}
#validation-results td{padding:9px 8px;vertical-align:top;color:var(--ink)}
#validation-results .method-info-trigger{color:inherit;min-height:32px;font-size:13px;padding:0}
.validation-rank{font-size:12px;font-weight:800;display:inline-block;margin-right:6px;white-space:nowrap}
#validation-results tr{--rank-ink:var(--ink);--rank-wash:var(--surface)}
#validation-results tr[data-rank="1"][data-scored="true"]{--rank-ink:#805500;--rank-wash:#fff8e8}
#validation-results tr[data-rank="2"][data-scored="true"]{--rank-ink:#425a72;--rank-wash:#f0f5fa}
#validation-results tr[data-rank="3"][data-scored="true"]{--rank-ink:#884b31;--rank-wash:#fff3ec}
#validation-results tr td{background:var(--rank-wash)}
#validation-results tr td:first-child,#validation-results .validation-points{color:var(--rank-ink)}
:host([data-theme="dark"]) #validation-results tr[data-rank="1"][data-scored="true"]{--rank-ink:#f4cd77;--rank-wash:#352b19}
:host([data-theme="dark"]) #validation-results tr[data-rank="2"][data-scored="true"]{--rank-ink:#b9cddd;--rank-wash:#22303d}
:host([data-theme="dark"]) #validation-results tr[data-rank="3"][data-scored="true"]{--rank-ink:#efb799;--rank-wash:#382820}
.validation-points{display:inline-block;margin-right:6px;font-size:17px;line-height:1.4;font-weight:800}
.validation-metric{display:inline;font-size:12px;line-height:1.6;color:var(--muted)}
#validation-results .ticket-balls{--ball-size:26px;gap:5px;flex-wrap:nowrap;max-width:100%}
#validation-results .ticket-balls .ball{font-size:12px}
#validation-results .result-detail{display:block;margin:5px 0 0;font-size:12px;line-height:1.5;color:var(--muted)}
.validation-prize{display:inline-block;font-size:12px;font-weight:650;color:var(--muted);margin-right:5px}
#validation-results [data-prize="1"] .validation-prize{color:#7040a0}
#validation-results [data-prize="2"] .validation-prize{color:#245ba5}
#validation-results [data-prize="3"] .validation-prize{color:#17635e}
#validation-results [data-prize="4"] .validation-prize{color:#85551b}
#validation-results [data-prize="5"] .validation-prize{color:#286236}
:host([data-theme="dark"]) #validation-results [data-prize="1"] .validation-prize{color:#d6b3ff}
:host([data-theme="dark"]) #validation-results [data-prize="2"] .validation-prize{color:#a4c9ff}
:host([data-theme="dark"]) #validation-results [data-prize="3"] .validation-prize{color:#99d8d0}
:host([data-theme="dark"]) #validation-results [data-prize="4"] .validation-prize{color:#eed096}
:host([data-theme="dark"]) #validation-results [data-prize="5"] .validation-prize{color:#aad9b1}
.validation-audit code{font:11px/1.6 ui-monospace,monospace;white-space:normal;overflow-wrap:anywhere}
.validation-import-note{display:block;margin-top:5px;color:var(--muted);font-size:12px;line-height:1.6;font-weight:400}
.validation-assessment{font-size:12px;color:var(--muted);margin:6px 0}
@container wallet (max-width:560px){
 .validation-form,.validation-output{padding:12px;border-radius:12px}
 .validation-fields input{width:100%;max-width:none}
 .validation-form .primary{width:100%;min-height:44px}
 .validation-choices{grid-template-columns:1fr}
 .validation-output .mobile-table tr{display:grid;grid-template-columns:minmax(0,1fr);gap:0;padding:0;margin:0;border-bottom:1px solid var(--line)}
 #validation-results td{display:block;padding:4px 8px;border:0}
 #validation-results td:first-child{padding-top:6px}
 #validation-results td:last-child{padding-bottom:8px;display:flex;align-items:baseline;gap:4px 10px;flex-wrap:wrap}
 #validation-results td::before{display:none}
 .validation-toolbar button{flex:1 1 auto}
 .validation-toolbar label{flex:1 1 100%}
 .validation-draw .draw-numbers{--ball-size:24px;gap:4px;min-height:45px}
 .validation-draw .bonus-group{gap:4px}
}
@media(forced-colors:active){
 #validation-results tr{--rank-ink:CanvasText!important;--rank-wash:Canvas!important}
 #validation-results .validation-rank{border:1px solid CanvasText}
}
${DETAIL_STYLE}
`;

export function verifyHistoricalMatches(data) {
  const fail = () => { throw new Error('검증번호와 당첨번호의 일치 정보가 맞지 않습니다. 다시 검증해 주세요.'); };
  const isNumber = n => Number.isInteger(n) && n >= 1 && n <= 45;
  const isTicket = ns => Array.isArray(ns) && ns.length === 6 && ns.every(isNumber) && new Set(ns).size === 6;
  const draw = data?.draw;
  if (!draw || draw.round !== data.target_round || !isTicket(draw.numbers)
      || !isNumber(draw.bonus) || draw.numbers.includes(draw.bonus) || !Array.isArray(data.results)) fail();
  const winning = new Set(draw.numbers);
  let checked = 0, won = 0, unavailable = 0, highest = null;
  for (const row of data.results) {
    if (row?.generation_status === 'unavailable') {
      if (!Array.isArray(row.recommended_numbers) || row.recommended_numbers.length || row.prize_rank != null) fail();
      unavailable++; continue;
    }
    if (row?.generation_status !== 'generated' || !isTicket(row.recommended_numbers)) fail();
    const main = row.recommended_numbers.filter(n => winning.has(n)).sort((a,b) => a-b);
    const bonus = row.recommended_numbers.includes(draw.bonus);
    const reported = row.matched_main_numbers;
    const rank = main.length === 6 ? 1 : main.length === 5 ? (bonus ? 2 : 3) : main.length === 4 ? 4 : main.length === 3 ? 5 : null;
    if (!Array.isArray(reported) || reported.length !== main.length || !reported.every(isNumber)
        || [...reported].sort((a,b) => a-b).some((n,i) => n !== main[i])
        || row.main_match_count !== main.length || row.bonus_match !== bonus
        || row.matched_bonus_number !== (bonus ? draw.bonus : null)
        || row.prize_rank !== rank || row.prize !== (rank === null ? '미당첨' : `${rank}등`)) fail();
    checked++;
    if (rank !== null) { won++; highest = highest === null ? rank : Math.min(highest, rank); }
  }
  if (data.checked_game_count !== checked || data.winning_game_count !== won
      || data.unavailable_game_count !== unavailable || data.highest_prize !== (highest === null ? null : `${highest}등`)) fail();
}

export function rankedRows(results = [], methods = [], mode = 'points') {
  const current = new Map(results.map(r => [r.method_id, r]));
  const scores = new Map(methods.map(r => [r.method_id, r]));
  const ids = new Set([...current.keys(), ...scores.keys()]);
  const rows = [...ids].map(id => ({method_id:id, current:current.get(id), score:scores.get(id)||{},
    label:current.get(id)?.sensor_name || scores.get(id)?.label || id}));
  const key = row => mode === 'current' ? [row.current?.generation_status === 'generated' ? row.current.main_match_count : -1, row.score.points||0]
    : mode === 'efficiency' ? [row.score.points_per_100||0,row.score.three_plus_hits||0]
    : [row.score.points||0,row.score.three_plus_hits||0,row.score.best_match||0];
  rows.sort((a,b) => {const x=key(a),y=key(b);for(let i=0;i<x.length;i++)if(x[i]!==y[i])return y[i]-x[i];return a.label.localeCompare(b.label,'ko');});
  let rank=0,last;
  rows.forEach((row,i) => {const value=JSON.stringify(key(row));if(value!==last)rank=i+1;row.rank=rank;last=value;});
  const counts=new Map();rows.forEach(r=>counts.set(r.rank,(counts.get(r.rank)||0)+1));
  rows.forEach(r=>r.tied=counts.get(r.rank)>1);
  return rows;
}

export function csvCell(value) {
  let text=String(value ?? '');
  if (/^[\s]*[=+@-]/.test(text)) text="'"+text;
  return '"'+text.replaceAll('"','""')+'"';
}

class HistoricalValidationView {
  constructor(panel) {
    this.panel=panel;this.form=panel.node('validation-form');this.sequence=0;this.entry=null;
    this.restoreToken=0;this.restoreTimer=null;this.busy=false;this.importing=false;this.importToken=0;this.sort='points';this.expandedMethods=new Set();this.detailLimits=new Map();this.detailCycle=null;this.runtimeVersion=VALIDATION_UI_VERSION;
    this.node('validation-form').onsubmit=e=>{e.preventDefault();void this.run();};
    this.node('validation-round').oninput=()=>this.changed();
    this.node('validation-choices').onchange=()=>this.changed();
    this.node('validation-defaults').onclick=()=>{this.selectDefaults();this.changed();};
    this.panel.shadowRoot.querySelector('.validation-notice').textContent=RESET;
    this.panel.shadowRoot.querySelector('.validation-notice').id='validation-reset-notice';
    const total=el('p','','validation-total');total.id='validation-total';
    const toolbar=el('div',undefined,'validation-toolbar');
    const label=el('label','순위 기준 ');label.htmlFor='validation-sort';
    const select=el('select');select.id='validation-sort';
    for(const [v,t] of [['points','누적 점수'],['current','이번 본번호 일치'],['efficiency','100회당 점수']]){const o=el('option',t);o.value=v;select.append(o);}
    select.onchange=()=>{this.sort=select.value;this.renderList();};label.append(select);
    this.importButton=el('button','리뷰에 반영');this.importButton.type='button';this.importButton.id='validation-import';
    this.importButton.onclick=()=>void this.importReview();
    this.exportButton=el('button','CSV 내보내기');this.exportButton.type='button';this.exportButton.id='validation-export';
    this.exportButton.onclick=()=>this.exportCSV();toolbar.append(label,this.importButton,this.exportButton);
    const assessment=el('p','','validation-assessment');assessment.id='validation-assessment';
    this.node('validation-summary').after(total,toolbar,assessment);
    const table=this.node('validation-results').closest('table');
    ['순위 · 공식','이번 검증번호 · 결과','누적 점수 · 비교'].forEach((t,i)=>table.querySelectorAll('th')[i].textContent=t);
    table.querySelector('caption').textContent='공식별 이번 과거 검증 결과와 누적 점수 통합 순위. 실제 당첨 예측 순위가 아닙니다.';
  }
  node(id){return this.panel.node(id);}
  ids(){return [...this.node('validation-choices').querySelectorAll('input:checked')].filter(n=>n.dataset.profileUnavailable!=='true').map(n=>n.value);}
  message(text,error=false){const n=this.node('validation-status');n.dataset.error=String(error);n.setAttribute('role',error?'alert':'status');n.textContent=text;}
  changed(){this.sequence++;this.restoreToken++;clearTimeout(this.restoreTimer);this.busy=false;this.node('validation-output').hidden=true;this.message('');this.renderConditions();}
  selectDefaults(){const selected=new Set(this.options?.default_method_ids||[]);for(const n of this.node('validation-choices').querySelectorAll('input'))n.checked=!n.disabled&&selected.has(n.value);}
  applyRequestState(state){if(Number.isInteger(state?.round))this.node('validation-round').value=String(state.round);const ids=new Set(state?.method_ids||[]);if(ids.size)for(const n of this.node('validation-choices').querySelectorAll('input'))n.checked=!n.disabled&&ids.has(n.value);}
  scheduleRestore(){clearTimeout(this.restoreTimer);this.restoreTimer=setTimeout(()=>{if(this.panel.isConnected)void this.restoreLatest(true);},1200);}
  async restoreLatest(polling=false){
    const entry=this.entry,token=++this.restoreToken,sequence=this.sequence;
    try{
      const state=await this.panel.request('historical_validation_state');
      if(token!==this.restoreToken||sequence!==this.sequence||entry!==this.node('entry')?.value||!this.panel.isConnected)return;
      if(state.validation_scoreboard)this.score=state.validation_scoreboard;
      if(state.status==='running'){this.busy=true;this.applyRequestState(state);this.message(`${state.round}회 검증 계산 중 · 페이지를 이동해도 계속됩니다.`);this.renderConditions();this.scheduleRestore();return;}
      clearTimeout(this.restoreTimer);this.restoreTimer=null;this.busy=false;
      if(state.status==='completed'&&state.result){this.applyRequestState(state);this.render(state.result);}
      else if(state.validation_scoreboard){this.result=null;this.renderEmptyCycle();}
      if(state.status==='error')this.message(state.error||'검증을 완료하지 못했습니다.',true);
      this.renderConditions();
    }catch(error){if(token!==this.restoreToken||entry!==this.entry)return;if(polling&&this.panel.isConnected)this.scheduleRestore();else{this.busy=false;this.renderConditions();this.message(error?.message||'검증 기록을 복원하지 못했습니다.',true);}}
  }
  setData(data){
    const entry=this.node('entry')?.value,switched=entry!==this.entry;
    const oldMax=Number(this.options?.max_round)||0;
    if(switched){this.entry=entry;this.sequence++;this.restoreToken++;clearTimeout(this.restoreTimer);this.busy=false;this.importing=false;this.importToken++;this.restoredEntry=null;this.score=null;this.result=null;this.expandedMethods.clear();this.detailLimits.clear();this.detailCycle=null;this.initialized=false;this.catalogSignature=null;this.node('validation-output').hidden=true;this.node('validation-round').value='';this.message('');}
    this.options=data.historical_validation||{};
    const ready=this.options.saju_profile_ready===true,catalog=Array.isArray(data.method_catalog)?data.method_catalog:[];
    const signature=JSON.stringify([ready,catalog.map(m=>[m.method_id,m.name])]);
    if(signature!==this.catalogSignature||!this.initialized){
      const prior=this.initialized?new Set(this.ids()):null;this.catalogSignature=signature;
      const root=this.node('validation-choices');root.replaceChildren();
      const advanced=el('details',undefined,'validation-advanced');advanced.append(el('summary','고급 선택 · 균등 알고리즘과 빈도 프리셋'));
      for(const method of catalog){const label=el('label',undefined,'validation-choice'),input=el('input');input.type='checkbox';input.value=method.method_id;
        input.dataset.profileUnavailable=String(method.method_id===SAJU&&!ready);input.disabled=input.dataset.profileUnavailable==='true';
        input.checked=!input.disabled&&(prior||new Set(this.options.default_method_ids||[])).has(method.method_id);
        label.append(input,el('span',method.name+(input.disabled?' · 사주정보 설정 필요':method.method_id===AI?' · CCSS 번호만 검증':'')));
        (method.selection_group==='advanced'?advanced:root).append(label);if(input.checked&&method.selection_group==='advanced')advanced.open=true;
      }
      if(advanced.children.length>1)root.append(advanced);
    }
    const max=Number(this.options.max_round)||0,min=Number(this.options.min_round)||31;
    const input=this.node('validation-round');input.min=String(min);input.max=String(Math.max(min,max));
    if(!input.value&&max>=min)input.value=String(max);
    if(max>=min&&catalog.length)this.initialized=true;
    this.node('validation-range').textContent=max>=min?`${min}~${max}회 선택 가능 · 공식 이력 기준`:'최소 31회 공식 이력이 필요합니다.';
    this.decorateReviews(data);
    if(data.validation_scoreboard){this.score=data.validation_scoreboard;if(!this.node('validation-output').hidden)this.renderList();}
    const published=Number(data.result_round)||max,confirmed=['official_history','official_confirmed','official_corrected','cross_checked'].includes(data.result_verification?.status);
    const cycleChanged=!switched&&((max>oldMax&&oldMax>0)||(confirmed&&this.score?.cycle_round&&published>this.score.cycle_round));
    if(cycleChanged){this.sequence++;this.restoreToken++;this.result=null;this.score=null;this.node('validation-output').hidden=true;this.message('새 당첨회차 확인 · 이전 과거 검증을 초기화합니다.');}
    this.renderConditions();
    if((this.restoredEntry!==entry||cycleChanged)&&this.initialized){this.restoredEntry=entry;void this.restoreLatest();}
  }
  renderConditions(){
    const round=Number(this.node('validation-round').value),ids=this.ids();this.node('validation-method-count').textContent=`${ids.length}개 선택`;
    this.node('validation-cutoff').textContent=Number.isInteger(round)&&round>=31?`${round}회 검증: 1~${round-1}회만 생성에 사용 · ${round}회 당첨번호는 생성 후 대조`:'';
    this.node('validation-run').disabled=this.busy||this.importing||!ids.length||!(Number(this.options?.max_round)>=31);
    this.node('validation-run').textContent=this.busy?'과거 데이터로 계산 중…':'검증번호 생성·당첨 확인';
    this.form.setAttribute('aria-busy',String(this.busy));
    for(const n of this.form.querySelectorAll('input,button:not(#validation-run)'))n.disabled=this.busy||this.importing||n.dataset.profileUnavailable==='true';
    this.importButton.disabled=this.busy||this.importing||!this.score?.unimported_runs||!!this.score?.storage_error;
    this.exportButton.disabled=!this.score?.methods?.length;
  }
  async run(){
    if(this.busy||this.importing||!this.form.reportValidity())return;const round=Number(this.node('validation-round').value),method_ids=this.ids();if(!method_ids.length)return;
    const sequence=++this.sequence,entry=this.entry;this.restoreToken++;clearTimeout(this.restoreTimer);this.busy=true;this.node('validation-output').hidden=true;this.renderConditions();
    this.message(`${round}회 직전 이력으로 새 번호 생성 중 · 실제 추천과 리뷰는 변경하지 않습니다.`);
    try{const result=await this.panel.request('historical_validate',{round,method_ids});
      if(sequence!==this.sequence||entry!==this.node('entry')?.value||!this.panel.isConnected)return;
      if(result.mode!=='historical_validation'||result.counts_toward_reviews!==false||result.persisted!==false||result.target_round!==round||result.based_on_round!==round-1)throw Error('검증 응답의 회차와 데이터 구분을 확인할 수 없습니다.');
      this.render(result);this.message(result.validation_scoreboard?.storage_error?'검증은 완료했지만 점수를 저장하지 못했습니다. 기존 기록은 보존합니다.':`${round}회 검증 완료 · 리뷰 반영은 확인 후에만 수행합니다.`,!!result.validation_scoreboard?.storage_error);
    }catch(error){if(sequence===this.sequence&&entry===this.entry){this.message(error?.message||'과거 검증에 실패했습니다.',true);if(error?.code==='validation_cycle_expired')void this.restoreLatest();}}
    finally{if(sequence===this.sequence&&entry===this.entry){this.busy=false;this.renderConditions();}}
  }
  render(data){
    this.node('validation-output').hidden=true;verifyHistoricalMatches(data);this.result=data;this.score=data.validation_scoreboard||null;
    this.node('validation-title').textContent=`${data.target_round}회 검증 결과 · 누적 비교`;
    this.node('validation-meta').textContent=`사용 이력 1~${data.based_on_round}회 · 현재 공식 v${data.component_version}`;
    const draw=this.node('validation-draw');draw.parentElement.hidden=false;numberBalls(draw,data.draw.numbers,data.draw.bonus);
    this.node('validation-summary').textContent=`이번 ${fmt(data.checked_game_count)}게임 · 3개 이상 ${fmt(data.winning_game_count)}게임 · 생성 불가 ${fmt(data.unavailable_game_count)}개 · 회색은 불일치`;
    this.node('validation-audit-text').textContent=`생성 ${data.generated_at} · 입력 마감 ${data.training_last_round}회 · AI 호출 없음 · 실제 추첨 전 추천 기록은 변경하지 않습니다.`;
    this.node('validation-hash').textContent=data.training_sha256;this.node('validation-notice').textContent='리뷰 미반영 결과는 새 당첨회차 확인 시 초기화됩니다.';
    this.renderList();this.node('validation-output').hidden=false;
  }
  renderEmptyCycle(){
    this.node('validation-title').textContent='과거 검증 · 누적 비교';this.node('validation-meta').textContent='';this.node('validation-draw').parentElement.hidden=true;
    this.node('validation-summary').textContent=this.score?.reset_at?'새 당첨회차가 확인되어 이전 검증을 초기화했습니다.':'이번 집계의 검증을 시작하세요.';
    this.node('validation-audit-text').textContent='';this.node('validation-hash').textContent='';this.node('validation-notice').textContent='리뷰 미반영 결과는 새 당첨회차 확인 시 초기화됩니다.';
    this.renderList();this.node('validation-output').hidden=false;
  }
  renderList(){
    const score=this.score||{},root=this.node('validation-results');root.replaceChildren();
    if(this.detailCycle!==score.cycle_id){this.expandedMethods.clear();this.detailLimits.clear();this.detailCycle=score.cycle_id;}
    this.node('validation-total').textContent=`총 ${fmt(score.total_runs)}회 검증 · ${fmt(score.unique_rounds)}개 회차 · 리뷰 미반영 ${fmt(score.unimported_runs)}회`;
    this.node('validation-assessment').textContent=`본번호 3개 이상 무작위 기준 ${Number(score.baseline_hit_rate||2.38341).toFixed(3)}% · 예측 우위 아님.${score.comparable_rounds===false?' 공식별 검증 회차가 달라 비교에 주의하세요.':''}`;
    const rows=rankedRows(this.result?.results||[],score.methods||[],this.sort);
    if(!rows.length){const tr=el('tr'),td=el('td','누적된 검증이 없습니다. 회차와 공식을 선택해 검증하세요.');td.colSpan=3;tr.append(td);root.append(tr);}
    for(const row of rows){
      const tr=el('tr');tr.dataset.rank=String(row.rank);tr.dataset.scored=String(Number(row.score.points||0)>0);tr.dataset.methodId=row.method_id;tr.className='prediction-row';tr.dataset.prize=String(row.current?.prize_rank||0);tr.setAttribute('role','row');
      const method=el('td',row.label),number=el('td'),metrics=el('td');
      [method,number,metrics].forEach((n,i)=>{n.setAttribute('role','cell');n.dataset.label=['순위 · 공식','검증번호','누적 성과'][i];});
      const r=row.current,s=row.score;
      if(r?.generation_status==='generated'){
        const balls=el('span',undefined,'ticket-balls result-balls');numberBalls(balls,r.recommended_numbers,null,r);number.append(balls);
        const text=el('span',undefined,'result-detail');text.append(el('span',r.prize,'validation-prize'),document.createTextNode(`본번호 ${r.main_match_count}개 일치${r.bonus_match?` · 보너스 ${r.matched_bonus_number}`:''}`));number.append(text);
      }else number.append(el('span',r?'생성 불가':'이번 검증 미참여','validation-metric'));
      metrics.append(el('strong',this.sort==='efficiency'?`${Number(s.points_per_100||0).toFixed(1)}점/100회`:`${fmt(s.points)}점`,'validation-points'),el('span',`3개 이상 ${fmt(s.three_plus_hits)}/${fmt(s.generated)}회 · ${Number(s.hit_rate||0).toFixed(1)}%`,'validation-metric'));
      const more=el('button','상세','validation-detail-toggle');more.type='button';
      metrics.append(more);tr.append(method,number,metrics);root.append(tr);
    }
    this.panel.shadowRoot.querySelector('lotto-panel-tools')?.decorate('validation-results',rows.map(r=>({method_id:r.method_id})));
    rows.forEach((r,i)=>root.children[i]?.cells[0]?.prepend(el('span',`${r.tied?'공동 ':''}${r.rank}위`,'validation-rank')));
    attachValidationDetails(this,rows,score);
    this.renderConditions();
  }
  async importReview(){
    const score=this.score;if(!score?.unimported_runs||this.importing||this.busy)return;
    const entry=this.entry,rev=score.revision,token=++this.importToken;
    if(!window.confirm(`미반영 검증 ${score.unimported_runs}회를 실제 리뷰 화면에 반영할까요?\n\n미적중·생성 불가를 포함한 전체 결과를 '과거검증' 성과로 반영합니다. 실제 추첨 전 추천 별점·당첨 횟수는 바꾸지 않습니다. 이미 반영한 검증은 중복 가산하지 않습니다.`))return;
    this.importing=true;this.renderConditions();
    try{const data=await this.panel.request('historical_validation_import',{confirmed:true,revision:rev});
      if(token!==this.importToken||entry!==this.node('entry')?.value||!this.panel.isConnected)return;
      this.score=data.validation_scoreboard;if(this.result?.validation_cycle&&this.result.validation_cycle!==this.score?.cycle_id)this.result=null;this.panel.updateResults(data);if(this.result)this.renderList();else this.renderEmptyCycle();this.message('리뷰 반영 완료 · 공식별 리뷰에 과거검증 성과가 함께 표시됩니다.');
    }catch(error){if(token===this.importToken&&entry===this.entry){this.message(error?.message||'리뷰에 반영하지 못했습니다.',true);void this.restoreLatest();}}
    finally{if(token===this.importToken){this.importing=false;this.renderConditions();}}
  }
  decorateReviews(data){
    const root=this.panel.node('reviews');if(!root)return;
    this.reviewData=data.reviews||[];
    let label=this.node('validation-review-order');
    if(!label){
      label=el('label','리뷰 정렬 ','validation-toolbar');label.id='validation-review-order';
      const select=el('select');select.setAttribute('aria-label','리뷰 정렬 기준');
      for(const [value,text] of [['live','기존 실전 리뷰 순서'],['historical','반영한 과거검증 · 100회당 점수']]){const option=el('option',text);option.value=value;select.append(option);}
      select.onchange=()=>{this.reviewSort=select.value;this.orderReviews();};label.append(select);this.node('reviewstatus')?.before(label);
    }
    label.hidden=!this.reviewData.some(r=>r.historical_review);
    this.reviewData.forEach((r,i)=>{const tr=root.children[i],cell=tr?.cells?.[0];if(!cell)return;tr.dataset.reviewMethod=r.method_id;
      cell.querySelector('.validation-import-note')?.remove();const h=r.historical_review;if(!h)return;
      cell.append(el('span',`과거검증 반영 ${fmt(h.points)}점 · 본번호 3개 이상 ${fmt(h.three_plus_hits)}/${fmt(h.generated)}회 · ${h.generated?(h.three_plus_hits*100/h.generated).toFixed(1):'0.0'}%`,'validation-import-note'));
    });
    this.orderReviews();
  }
  orderReviews(){
    const root=this.panel.node('reviews');if(!root)return;
    const indices=new Map((this.reviewData||[]).map((r,i)=>[r.method_id,i]));
    const efficiency=new Map((this.reviewData||[]).map(r=>[r.method_id,r.historical_review?.generated?r.historical_review.points*100/r.historical_review.generated:-1]));
    const rows=[...root.children];rows.sort((a,b)=>{
      const x=a.dataset.reviewMethod,y=b.dataset.reviewMethod;
      return (this.reviewSort==='historical'?(efficiency.get(y)??-1)-(efficiency.get(x)??-1):0)||(indices.get(x)??0)-(indices.get(y)??0);
    });root.append(...rows);
  }
  exportCSV(){
    const score=this.score;if(!score?.methods?.length)return;
    const rows=[['출처','집계 기준 회차','공식','검증 생성','생성 불가','3개 이상 적중','점수','100회당 점수','3개','4개','5개','6개','회차별 첫 검증','공식 버전']];
    for(const s of score.methods)rows.push(['과거검증 시뮬레이션',score.cycle_round,s.label,s.generated,s.unavailable,s.three_plus_hits,s.points,s.points_per_100,s.match_3,s.match_4,s.match_5,s.match_6,s.unique_rounds,(s.formula_versions||[]).join(';')]);
    const csv='\uFEFF'+rows.map(r=>r.map(csvCell).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=el('a');a.href=url;a.download=`lotto-validation-${score.cycle_round||'current'}.csv`;this.node('screen-validation').append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
}

export function applyHistoricalValidation(panel){
  if(!panel.node('screen-validation'))return;
  let style=panel.shadowRoot.querySelector('style[data-lotto-validation]');if(!style){style=el('style');panel.shadowRoot.append(style);}style.dataset.lottoValidation=VALIDATION_UI_VERSION;style.textContent=STYLE;
  const current=panel._historicalValidation;
  const needsUpgrade=current&&(current.form!==panel.node('validation-form')||current.runtimeVersion!==VALIDATION_UI_VERSION);
  if(needsUpgrade){
    current.sequence=(current.sequence||0)+1;current.restoreToken=(current.restoreToken||0)+1;clearTimeout(current.restoreTimer);
    if('importToken' in current)current.importToken=(current.importToken||0)+1;
    panel.node('validation-total')?.remove();
    panel.node('validation-assessment')?.remove();
    panel.node('validation-sort')?.closest('.validation-toolbar')?.remove();
    panel.node('validation-review-order')?.remove();
    panel._historicalValidation=null;
  }
  if(!panel._historicalValidation)panel._historicalValidation=new HistoricalValidationView(panel);
  if(panel._latestToolsData)panel._historicalValidation.setData(panel._latestToolsData);
  if(!panel._historicalValidationHook){panel._historicalValidationHook=true;const update=panel.updateResults;panel.updateResults=function(data,...args){const value=update.call(this,data,...args);this._historicalValidation?.setData(data);return value;};}
}
