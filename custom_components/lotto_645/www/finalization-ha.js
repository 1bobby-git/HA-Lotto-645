/* Optional HA UI. Reads/polls never submit a manual finalization. */
import './finalization-panel.js';
export function applyFinalizationPanel(panel){
  const root=panel.shadowRoot;if(!root)return;
  let style=root.querySelector('link[data-finalization-style]');
  if(!style){style=document.createElement('link');style.rel='stylesheet';style.href=new URL('./finalization-panel.css',import.meta.url).href;style.dataset.finalizationStyle='1';root.append(style);}
  const host=root.getElementById('screen-review');if(!host)return;
  let widget=host.querySelector('lotto-finalization-panel');
  if(!widget){
    widget=document.createElement('lotto-finalization-panel');host.append(widget);
    let entry=null;
    widget.configure(async(action,data)=>{
      const current=panel.node('entry')?.value;if(current!==entry){entry=current;widget.selected=null;widget.resultSignature=null;}
      const result=await panel.request('finalization',{action,...data});
      if(panel.node('entry')?.value!==current){const error=new Error('선택한 통합이 변경됐습니다.');error.code='context_changed';throw error;}
      const ready=result.readiness;const selected=ready?.source_batch_id;
      result.sources=selected?[{source_batch_id:selected,target_round:ready.target_round,evaluation_mode:'live'}]:[];
      if(result.latest_source_batch_id&&result.latest_source_batch_id!==selected)result.sources.push({source_batch_id:result.latest_source_batch_id,target_round:ready?.target_round,evaluation_mode:'live'});
      return result;
    });
  }
  const home=root.getElementById('screen-home');
  if(home&&!home.querySelector('[data-finalization-go]')){const button=document.createElement('button');button.type='button';button.dataset.finalizationGo='1';button.textContent='최종 번호 산출 · 준비 상태 확인';button.onclick=()=>{panel.showScreen('review',true);widget.scrollIntoView({block:'nearest'});widget.perform('refresh');};home.append(button);}
}
