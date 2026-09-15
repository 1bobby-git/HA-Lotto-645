/* Full-width disclosure rows and lazily rendered, bounded historical hits. */
import { numberBalls } from './lotto-panel-view.js?v=1.15.0';

const node = (tag, text, cls) => {
  const element=document.createElement(tag);
  if(text!==undefined)element.textContent=text;
  if(cls)element.className=cls;
  return element;
};
const fmt = n => Number(n||0).toLocaleString('ko-KR');
const PAGE_SIZE = 10;

export const DETAIL_STYLE = `
#validation-results .validation-detail-toggle{min-width:44px;min-height:32px;margin:0 0 0 6px;padding:3px 6px;border:0;background:transparent;color:var(--muted);font-size:12px;white-space:nowrap}
#validation-results .validation-detail-toggle::before{content:'▸';margin-right:4px}
#validation-results .validation-detail-toggle[aria-expanded="true"]::before{content:'▾'}
#validation-results .validation-detail-toggle:focus-visible,#validation-results .validation-hit-more:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
#validation-results > tr.validation-detail-row[hidden]{display:none!important}
#validation-results > tr.validation-detail-row > td{display:table-cell;padding:0;border-bottom:1px solid var(--line);background:var(--surface);color:var(--ink);font-weight:400}
#validation-results > tr.validation-detail-row > td::before{display:none}
.validation-detail-body{min-width:0;padding:8px 10px 10px;font-size:12px;line-height:1.6;overflow-wrap:anywhere}
.validation-detail-metrics{display:flex;flex-wrap:wrap;gap:3px 16px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.validation-detail-metrics span{min-width:0}
.validation-detail-body h3{margin:7px 0 3px;font-size:13px;font-weight:700}
.validation-detail-body p{margin:4px 0;color:var(--muted)}
.validation-hit-list{padding:0;margin:0;list-style:none}
.validation-hit{display:grid;grid-template-columns:minmax(140px,.8fr) minmax(180px,1fr) minmax(0,1.3fr);gap:4px 12px;padding:6px 0;border-bottom:1px solid var(--line);align-items:center}
.validation-hit:last-child{border-bottom:0}
.validation-hit-meta{display:flex;flex-wrap:wrap;gap:0 8px;align-items:baseline;font-variant-numeric:tabular-nums}
.validation-hit-meta strong{font-size:12px}
.validation-hit-meta small{font-size:12px;color:var(--muted)}
#validation-results .validation-hit .ticket-balls{--ball-size:24px;gap:4px}
.validation-hit-match{font-variant-numeric:tabular-nums;min-width:0}
.validation-hit-unavailable{color:var(--muted);grid-column:2/-1}
#validation-results .validation-hit-more{font-size:12px;min-height:36px;padding:4px 10px;margin-top:4px}
.validation-detail-note{font-size:12px}
@container wallet (max-width:560px){
 #validation-results > tr.validation-detail-row{display:block;padding:0;border:0}
 #validation-results > tr.validation-detail-row > td{display:block;padding:0}
 .validation-detail-body{padding:8px}
 .validation-detail-metrics{gap:3px 12px}
 .validation-hit{grid-template-columns:minmax(0,1fr);gap:3px;padding:6px 0}
 .validation-hit-unavailable{grid-column:auto}
 #validation-results > .prediction-row > td:last-child{gap:3px 6px;align-items:center}
 #validation-results .validation-points{margin-right:0}
 #validation-results .validation-detail-toggle{margin-left:auto;padding:3px 4px}
}
`;

function fillDetails(view, row, score, body) {
  const s=row.score, metrics=node('div',undefined,'validation-detail-metrics');
  metrics.append(
    node('span',`누적 ${fmt(s.points)}점 · 100회당 ${Number(s.points_per_100||0).toFixed(1)}점`),
    node('span',`3개 ${fmt(s.match_3)} · 4개 ${fmt(s.match_4)} · 5개 ${fmt(s.match_5)} · 6개 ${fmt(s.match_6)}회`),
    node('span',`최고 ${s.best_match||0}개 · 생성 불가 ${fmt(s.unavailable)}회`),
    node('span',`회차별 첫 검증 ${fmt(s.unique_rounds)}회 · ${s.sample_notice||'표본 부족'}`),
  );
  if(s.interval_99)metrics.append(node('span',`99% 참고구간 ${s.interval_99[0]}~${s.interval_99[1]}%`));
  body.append(metrics);
  const events=[...(s.hit_history||[])].sort((a,b)=>b.run-a.run);
  body.append(node('h3',`적중 이력 · 본번호 3개 이상 ${fmt(s.three_plus_hits)}회`));
  const note=node('p','검증 순서는 현재 집계의 전체 실행 기준입니다.','validation-detail-note');
  body.append(note);
  if(!s.three_plus_hits)body.append(node('p','아직 본번호 3개 이상 적중한 검증이 없습니다.'));
  const omitted=Number(s.hit_history_omitted ?? Math.max(0,Number(s.three_plus_hits||0)-events.length));
  if(omitted>0)body.append(node('p',`${fmt(omitted)}회는 상세 이력이 남아 있지 않습니다. 누적 점수에는 포함됩니다. 공식별 최근 ${fmt(s.hit_history_limit||100)}건을 보관합니다.`));
  if(events.some(e=>!e.details_available))body.append(node('p','이전 버전에서 번호를 저장하지 않은 검증은 순서·회차·일치 개수만 표시합니다. 번호를 추정해 채우지 않습니다.'));
  const list=node('ol',undefined,'validation-hit-list');
  list.setAttribute('aria-label',`${row.label} 적중 이력, 최근 검증순`);
  body.append(list);
  let shown=0;
  const more=node('button','','validation-hit-more');more.type='button';
  const appendUntil = limit => {
    for(const hit of events.slice(shown,limit)){
      const item=node('li',undefined,'validation-hit');item.dataset.run=String(hit.run);
      const meta=node('div',undefined,'validation-hit-meta');
      meta.append(node('strong',`${fmt(hit.run)}번째 검증`),node('small',`${fmt(hit.round)}회`));
      if(hit.generated_at)meta.title=hit.generated_at;
      item.append(meta);
      if(hit.details_available){
        const balls=node('span',undefined,'ticket-balls result-balls');
        numberBalls(balls,hit.recommended_numbers,null,hit);item.append(balls);
        const match=node('div',undefined,'validation-hit-match');match.dataset.prize=String(hit.prize_rank);
        match.append(node('span',hit.prize,'validation-prize'),
          document.createTextNode(`본번호 ${hit.main_match_count}개 · ${hit.matched_main_numbers.join(', ')}${hit.bonus_match?` · 보너스 ${hit.matched_bonus_number}`:''}`));
        item.append(match);
      }else item.append(node('span',`본번호 ${hit.main_match_count}개 일치 · 번호 기록 없음`,'validation-hit-unavailable'));
      list.append(item);
    }
    shown=Math.min(limit,events.length);view.detailLimits.set(row.method_id,shown);
    more.hidden=shown>=events.length;
    more.textContent=`적중 이력 ${Math.min(PAGE_SIZE,events.length-shown)}건 더 보기 · ${shown}/${events.length}`;
  };
  appendUntil(view.detailLimits.get(row.method_id)||PAGE_SIZE);
  more.onclick=()=>{appendUntil(shown+PAGE_SIZE);if(more.hidden)view.node('validation-results').querySelector(`button[aria-controls="${body.id}"]`)?.focus({preventScroll:true});};
  body.append(more);
  const explanation=node('details',undefined,'validation-detail-note');
  explanation.append(node('summary','점수 기준·통계 해석'));
  explanation.append(node('p',`${score.point_policy||'3개=1점 · 4개=3점 · 5개=10점 · 6개=50점'} · 보너스 가산 없음`),
    node('p','같은 회차의 반복 검증은 참고구간에서 제외합니다. 독립 시행을 가정한 기술통계이며 회차 선택·다중 비교·공식 변경의 영향을 보정한 예측확률이 아닙니다.'),
    node('p',`공식 버전 ${(s.formula_versions||[]).join(', ')||'기존 기록'}${row.current?.reason?` · ${row.current.reason}`:''}`));
  body.append(explanation);
}

export function attachValidationDetails(view, rows, score) {
  const root=view.node('validation-results');
  // Decorate and rank primary rows before inserting any colspan detail rows.
  const primary=[...root.querySelectorAll(':scope > .prediction-row')];
  rows.forEach((row,index)=>{
    const tr=primary[index],button=tr?.querySelector('.validation-detail-toggle');
    if(!button)return;
    const detail=node('tr',undefined,'validation-detail-row');detail.setAttribute('role','row');
    detail.dataset.detailsFor=row.method_id;
    const cell=node('td');cell.colSpan=3;cell.setAttribute('role','cell');cell.setAttribute('aria-colspan','3');
    const body=node('div',undefined,'validation-detail-body');
    body.id=`validation-details-${encodeURIComponent(view.entry||'default')}-${encodeURIComponent(row.method_id)}`;
    body.setAttribute('role','group');body.setAttribute('aria-label',`${row.label} 검증 상세`);
    cell.append(body);detail.append(cell);tr.after(detail);
    button.setAttribute('aria-controls',body.id);
    const setExpanded = expanded => {
      if(expanded&&!body.childElementCount)fillDetails(view,row,score,body);
      detail.hidden=!expanded;
      button.setAttribute('aria-expanded',String(expanded));
      button.setAttribute('aria-label',`${row.label} 검증 상세 ${expanded?'접기':'펼치기'}`);
      button.textContent=expanded?'접기':'상세';
      if(expanded)view.expandedMethods.add(row.method_id);else view.expandedMethods.delete(row.method_id);
    };
    setExpanded(view.expandedMethods.has(row.method_id));
    button.onclick=()=>setExpanded(button.getAttribute('aria-expanded')!=='true');
  });
}
