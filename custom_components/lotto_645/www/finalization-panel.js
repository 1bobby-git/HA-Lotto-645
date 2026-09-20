(()=>{
/* Shared presentation only. All generation/readiness/ownership decisions remain server-side. */
const make=(tag,value='',className='')=>{const el=document.createElement(tag);el.textContent=value;el.className=className;return el;};
const messages={not_configured:'입력 묶음을 선택하세요.',waiting_sources:'원본 생성 중',blocked:'입력 확인 필요',ready:'최종 산출 준비 완료',closed:'대상 회차 마감',queued:'대기 중',running:'계산 중',completed:'산출 완료',failed:'산출 실패',cancelled:'취소됨',not_started:'수동 실행 대기'};
const colors=['#e08f00','#0063cc','#d8314f','#6d7381','#2c9e44'];
class FinalizationPanel extends HTMLElement {
  connectedCallback(){
    if(this.built){if(this.adapter)this.perform('refresh');return;}this.built=true;this.busy=false;this.loaded=false;this.data=null;
    const details=make('details','','finalization-panel');details.open=true;
    const heading=make('summary','2단계 · 최종 번호 산출');details.append(heading);this.append(details);
    this.content=make('div','','finalization-content');details.append(this.content);
    this.content.append(make('p','후보 커버링 재조합 · 선택한 원본 공식이 모두 저장된 뒤 실행합니다.','finalization-note'));
    this.message=make('p','입력 상태 확인 중');this.message.setAttribute('role','status');this.content.append(this.message);
    this.source=make('select');this.source.setAttribute('aria-label','선택한 입력 묶음');this.content.append(this.source);
    this.source.onchange=()=>this.perform('select',{source_batch_id:this.source.value});
    const controls=make('div','','finalization-controls');this.content.append(controls);
    const label=make('label','최종 출력 게임 수 ');this.count=make('input');this.count.type='number';this.count.min='1';this.count.max='20';this.count.step='1';this.count.setAttribute('aria-label','최종 출력 게임 수');label.append(this.count);controls.append(label);
    this.start=this.button('최종 번호 산출',()=>this.submit(false),controls);
    this.additional=this.button('같은 입력으로 다시 산출',()=>this.submit(true),controls);
    this.cancel=this.button('계산 취소',()=>this.perform('cancel'),controls);
    this.useNew=this.button('새 입력 사용',()=>this.perform('select',{source_batch_id:this.data?.latest_source_batch_id}),controls);
    this.refresh=this.button('상태 확인',()=>this.perform('refresh'),controls);
    this.count.oninput=()=>this.availability();this.blocked=make('div','','finalization-blocked');this.content.append(this.blocked);
    this.resultSelect=make('select');this.resultSelect.setAttribute('aria-label','보존된 최종 실행 기록');this.resultSelect.onchange=()=>{this.viewResultId=this.resultSelect.value;this.resultSignature=null;this.render();};this.content.append(this.resultSelect);
    this.results=make('div','','finalization-results');this.content.append(this.results);
    this.content.append(make('p','후보 보존형 실험적 재조합입니다. 당첨 보장·1등 확률 향상이 아니며 내 복권에 자동 등록되지 않습니다.','finalization-note'));
  }
  button(label,handler,parent){const b=make('button',label);b.type='button';b.onclick=handler;parent.append(b);return b;}
  configure(adapter){this.connectedCallback();this.adapter=adapter;this.perform('refresh');}
  disconnectedCallback(){clearTimeout(this.timer);this.timer=null;}
  async perform(action,data={}){
    if(this.busy||!this.adapter)return;clearTimeout(this.timer);this.busy=true;this.availability();
    try{const result=await this.adapter(action,data);if(!this.isConnected)return;this.data=result;this.render();}
    catch(error){if(error.code==='login_required'||error.code==='context_changed'||error.status===401){this.data=null;this.results.replaceChildren();this.source.replaceChildren();this.resultSelect.replaceChildren();this.count.value='';this.resultSignature=null;this.selected=null;this.viewResultId=null;}this.message.textContent=error?.message||'처리하지 못했습니다. 기존 원본과 완료 결과는 유지됩니다.';this.message.setAttribute('role','alert');}
    finally{this.busy=false;this.availability();if(this.isConnected)this.timer=setTimeout(()=>{if(!document.hidden)this.perform('refresh');else this.timer=setTimeout(()=>this.perform('refresh'),5000);},5000);}
  }
  submit(additional){
    const ready=this.data?.readiness;if(!ready)return;
    this.viewResultId=null;this.resultSignature=null;
    this.perform('start',{source_batch_id:ready.source_batch_id,source_selection_revision:ready.source_selection_revision,input_snapshot_hash:ready.input_snapshot_hash,game_count:Number(this.count.value),additional});
  }
  availability(){
    const ready=this.data?.readiness;const pending=Boolean(this.data?.state?.pending);const count=Number(this.count?.value);
    if(!this.start)return;
    const eligible=ready?.input_state==='ready'&&Number.isInteger(count)&&count>=ready.min_game_count&&count<=ready.max_game_count;
    this.start.disabled=this.busy||pending||!eligible;
    const prior=(this.data?.state?.results||[]).some(r=>r.input_snapshot_hash===ready?.input_snapshot_hash&&r.requested_game_count===count&&['completed','failed','cancelled'].includes(r.job_status));
    this.additional.disabled=this.start.disabled||!prior;
    this.cancel.disabled=this.busy||!pending;this.count.disabled=this.busy||pending;this.source.disabled=this.busy||pending;
    this.refresh.disabled=this.busy;this.useNew.disabled=this.busy||pending||!this.data?.latest_source_batch_id||this.data.latest_source_batch_id===ready?.source_batch_id;
  }
  render(){
    const ready=this.data.readiness||{input_state:'not_configured',completed_count:0,expected_count:0};
    const history=this.data.state?.results||[];
    const last=history.find(r=>r.finalization_run_id===this.viewResultId)||this.data.state?.last_result;const pending=this.data.state?.pending;
    this.resultSelect.replaceChildren();for(const row of history){const option=make('option',`${row.target_round}회 · ${row.requested_game_count}게임 · ${messages[row.job_status]} · ${row.finalization_run_id.slice(0,8)}`);option.value=row.finalization_run_id;this.resultSelect.append(option);}
    if(last)this.resultSelect.value=last.finalization_run_id;this.resultSelect.hidden=!history.length;
    this.message.setAttribute('role','status');this.message.textContent=`${messages[ready.input_state]||ready.input_state} · ${ready.completed_count||0}/${ready.expected_count||0} 완료 · 후보 ${ready.candidate_count||0}개${ready.target_round?' · 제 '+ready.target_round+'회':''}${ready.evaluation_mode==='research_replay'?' · 연구 재현(실제 사전 생성 아님)':''}${pending?' · '+(messages[this.data.summary?.job_status]||'계산 상태 확인 중'):''}`;
    const batches=this.data.sources||[];const selected=ready.source_batch_id||'';
    if(this.getRootNode().activeElement!==this.source){
      this.source.replaceChildren(make('option','입력 묶음 선택'));
      const options=batches.length?batches:[{source_batch_id:selected,target_round:ready.target_round,evaluation_mode:ready.evaluation_mode}];
      for(const row of options){if(!row.source_batch_id)continue;const o=make('option',`${row.evaluation_mode==='research_replay'?'연구 재현':'원본'} · 제 ${row.target_round}회 · ${row.source_batch_id.slice(0,16)}`);o.value=row.source_batch_id;this.source.append(o);}
      if(selected&&![...this.source.options].some(o=>o.value===selected)){const o=make('option','선택한 고정 입력 · '+selected.slice(0,16));o.value=selected;this.source.append(o);}
      this.source.value=selected;
    }
    if(this.selected!==selected){this.count.value=ready.default_requires_choice?'':String(ready.default_game_count||'');this.selected=selected;}
    this.count.min=String(ready.min_game_count||1);this.count.max=String(ready.max_game_count??20);
    this.blocked.replaceChildren();
    for(const reason of ready.blocked_sources||[])this.blocked.append(make('p',(reason.formula_id?reason.formula_id+' · ':'')+reason.reason));
    if(ready.default_requires_choice)this.blocked.append(make('p','기본 게임 수가 한도를 넘습니다. 후보 보존이 가능한 출력 수를 직접 선택하세요.'));
    if(ready.newer_input_available)this.blocked.append(make('p','새 원본 결과가 있습니다. 현재 선택한 입력과 이전 최종 결과는 유지됩니다.'));
    const failure=this.data.state?.last_failure;if(failure)this.blocked.append(make('p',`최근 실패/취소 기록: ${messages[failure.job_status]} · ${failure.error||'사용자 취소'} · 기존 완료 결과는 보존됩니다.`));
    this.additional.hidden=!history.length;this.cancel.hidden=!pending;
    const signature=last?JSON.stringify([last.finalization_run_id,last.evaluation,last.newer_input_available]):'';
    if(signature!==this.resultSignature){this.resultSignature=signature;this.renderResult(last);}
  }
  balls(values){const box=make('div','','finalization-balls');for(const n of values||[]){const ball=make('span',String(n),'final-ball');ball.dataset.band=String(Math.min(5,Math.floor((n-1)/10)+1));ball.style.background=colors[Math.min(4,Math.floor((n-1)/10))];ball.style.color='#fff';box.append(ball);}return box;}
  renderResult(result){
    this.results.replaceChildren();if(!result)return;
    if(result.job_status!=='completed'){this.results.append(make('p',`${messages[result.job_status]} · ${result.error||'이 실행에는 완료된 번호가 없습니다.'}`));return;}
    this.results.append(make('h3',`최종 ${result.actual_game_count}게임 · 원본 ${result.source_games?.length||0}게임`));
    this.results.append(make('p',`${result.optimization_status==='improved'?'탐색 목적함수 개선(당첨 보장 아님)':result.optimization_status==='unchanged'?'동일 결과':'추가 개선 없음'} · ${result.termination_reason==='time_limit'?'시간 제한 종료':'계산 예산 완료'} · ${result.evaluation_mode==='research_replay'?'연구 재현':result.review_eligible?'정식 평가 대상으로 고정':'참고 결과'}`,'finalization-note'));
    this.results.append(make('p','입력 '+result.source_batch_id+' · 최종 '+result.bundle_generation_id,'finalization-provenance'));
    for(const game of result.games){const row=make('div','','finalization-game');row.append(make('span',game.game_id),this.balls(game.numbers));this.results.append(row);}
    const audit=result.metrics?.audit;
    if(audit){
      const table=make('table');const cap=make('caption','독립 합성 감사 · 전체 1~45에서 본번호 6개 · 실제 평가 회차 아님');table.append(cap);
      const head=make('tr');for(const text of ['비교군','게임','3수 이상','4수 이상','3수 부분집합','4수 부분집합'])head.append(make('th',text));table.append(head);
      for(const [key,label] of [['original','원본(입력 수 기준)'],['constrained_random','동일 후보·B 난수 배치'],['final','최종 재조합'],['uniform_full45','전체 45 균등 기준선']]){
        const item=audit[key];if(!item)continue;const row=make('tr');for(const value of [label,item.game_count,(item.coverage_3*100).toFixed(2)+'%',(item.coverage_4*100).toFixed(2)+'%',item.triple_subsets,item.quad_subsets])row.append(make('td',String(value)));table.append(row);
      }
      const scroll=make('div','','finalization-table-scroll');scroll.append(table);this.results.append(scroll);
      const compare=result.metrics.comparison;const interval=compare?.audit_delta_interval_95;
      this.results.append(make('p',`표본 ${audit.final.sample_count.toLocaleString()}개 · 감사 결과로 재선택하지 않음${compare?.audit_worsened?' · 독립 감사에서 악화됨':''}${interval?' · 동일 후보 난수 배치 대비 3수 차이 95% 구간 '+interval.map(x=>(x*100).toFixed(2)).join(' ~ ')+'%p':''}`,'finalization-note'));
      if(!compare?.original_direct_comparison)this.results.append(make('p','원본 N과 최종 B가 달라 원본 최고 성적의 우열을 직접 비교하지 않습니다.','finalization-note'));
    }
    if(result.evaluation){
      const final=result.evaluation.comparison.final;
      this.results.append(make('p',`실제 발표 결과 · 후보 포함 본번호 ${final.included_main_count}/6 · 보너스 ${final.bonus_in_candidates?'포함':'미포함'} · 최고 ${final.best_main_matches}개 일치`));
      const evaluated=make('table');evaluated.append(make('caption','동일 B 묶음 평가 · 원본 공식 순위에 합산하지 않음'));
      const header=make('tr');for(const title of ['비교군','게임','최고 일치','3+','4+','5+','평균 일치'])header.append(make('th',title));evaluated.append(header);
      for(const [key,label] of [['original','원본(입력 수)'],['constrained_random','동일 후보·B 난수'],['final','최종'],['uniform_full45','전체45 균등']]){const score=result.evaluation.comparison[key];if(!score)continue;const row=make('tr');for(const value of [label,score.game_count,score.best_main_matches,score.at_least['3'],score.at_least['4'],score.at_least['5'],score.mean_main_matches.toFixed(2)])row.append(make('td',String(value)));evaluated.append(row);}
      const scroll=make('div','','finalization-table-scroll');scroll.append(evaluated);this.results.append(scroll);
      this.results.append(make('p','최종 등위별 게임 수 · '+Object.entries(final.prize_counts).map(([rank,count])=>rank+'등 '+count).join(' · '),'finalization-note'));

    }
    const original=make('details');original.append(make('summary','원본 결과와 버전·완료 시각'));
    original.append(make('p',`Core ${result.source_core_version} → ${result.finalizer_core_version} · ${result.source_completed_at} → ${result.result_committed_at}`,'finalization-provenance'));
    for(const row of result.source_games||[]){const line=make('div','','finalization-game');line.append(make('span',row.formula_id),this.balls(row.numbers));original.append(line);}this.results.append(original);
  }
}
if(!customElements.get('lotto-finalization-panel'))customElements.define('lotto-finalization-panel',FinalizationPanel);

})();
