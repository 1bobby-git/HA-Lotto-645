/* On-demand historical simulations. Never updates live tickets or review rows. */
import { numberBalls, renderPredictionRows } from './lotto-panel-view.js?v=1.14.0';

const SAJU = 'myungri_hetu_day_pillar';
const AI = 'home_assistant_ai';
const STYLE = `
.main-tabs{overflow-x:auto;scrollbar-width:none;max-width:100%}
.main-tabs::-webkit-scrollbar{display:none}
.validation-form,.validation-output{padding:26px;border:1px solid var(--line);border-radius:18px;background:var(--surface);min-width:0}
.validation-output{margin-top:24px}
.validation-notice{margin:0 0 24px;padding:16px 20px;background:var(--blue-soft);color:var(--ink);border-radius:12px;font-size:13px;line-height:1.8}
.validation-notice strong{display:block;margin-bottom:5px}
.validation-fields{display:flex;align-items:flex-start;flex-wrap:wrap;gap:18px 28px}
.validation-fields>div{min-width:0;flex:1 1 220px}
.validation-fields input{max-width:240px}
.validation-help,.validation-audit,.validation-status{color:var(--muted);font-size:13px;line-height:1.8;margin-top:8px;overflow-wrap:anywhere}
.validation-settings{margin:18px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:8px 0}
.validation-settings summary{font-size:14px;font-weight:650}
.validation-settings .validation-defaults{margin:10px 0;font-size:12px}
.validation-choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 16px;margin:12px 0 20px;max-height:380px;overflow:auto;padding:4px}
.validation-choice{display:flex;align-items:flex-start;gap:9px;margin:0;padding:8px 4px;min-height:44px;font-size:13px;line-height:1.6;font-weight:500;overflow-wrap:anywhere}
.validation-choice input{width:20px;height:20px;min-height:20px;padding:0;flex:none;margin:2px 0;accent-color:var(--blue)}
.validation-choice:has(input:disabled){color:var(--muted)}
.validation-status[data-error="true"]{color:var(--danger)}
.validation-status:empty{display:none}
.validation-form .primary{margin-top:12px}
.validation-draw{margin:16px 0 25px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.validation-draw .draw-numbers{--ball-size:36px;gap:10px;min-height:65px;justify-content:flex-start}
.validation-draw .draw-numbers .ball{font-size:16px}
.validation-draw .bonus-group{gap:10px}
.validation-draw .bonus-caption{top:calc(100% + 5px)}
.validation-draw .plus{font-size:18px}
.validation-output h2{font-size:22px}
.validation-audit code{font:12px/1.8 ui-monospace,monospace;overflow-wrap:anywhere;white-space:normal}
.validation-output .result-detail{grid-column:2}
.validation-output th:first-child{width:38%}
.validation-output th:nth-child(2){width:40%}
.validation-output th:last-child{width:22%}
.validation-comparison{display:block;margin-top:5px;font-size:12px;color:var(--muted);line-height:1.65;white-space:normal}
.validation-placeholder{margin:16px 0;font-size:14px;color:var(--muted)}
@container wallet (max-width:560px){
 .validation-form,.validation-output{padding:20px 16px}
 .validation-choices{grid-template-columns:1fr}
 .validation-notice{padding:14px 16px;font-size:12px}
 .validation-draw .draw-numbers{--ball-size:clamp(20px,calc((100cqw - 150px)/7),27px);gap:6px;max-width:100%}
 .validation-draw .draw-numbers .ball{font-size:13px}
 .validation-draw .bonus-group{gap:6px}
 .validation-help,.validation-audit,.validation-status{font-size:12px}
}
`;


class HistoricalValidationView {
  constructor(panel) {
    this.panel = panel; this.form = panel.node('validation-form'); this.sequence = 0; this.busy = false; this.entry = null;
    this.node('validation-form').onsubmit = event => { event.preventDefault(); void this.run(); };
    for (const id of ['validation-round', 'validation-seed']) this.node(id).oninput = () => this.changed();
    this.node('validation-choices').onchange = () => this.changed();
    this.node('validation-defaults').onclick = () => { this.selectDefaults(); this.changed(); };
  }
  node(id) { return this.panel.node(id); }
  ids() { return [...this.node('validation-choices').querySelectorAll('input:checked')].filter(n => n.dataset.profileUnavailable !== 'true').map(n => n.value); }
  message(text, error = false) {
    const node = this.node('validation-status'); node.dataset.error = String(error);
    node.setAttribute('role', error ? 'alert' : 'status'); node.textContent = text;
  }
  changed() {
    this.sequence++; this.busy = false; this.node('validation-output').hidden = true;
    this.message(''); this.renderConditions();
  }
  selectDefaults() {
    const selected = new Set(this.options?.default_method_ids || []);
    for (const input of this.node('validation-choices').querySelectorAll('input')) input.checked = !input.disabled && selected.has(input.value);
  }
  setData(data) {
    const entry = this.node('entry')?.value;
    const switched = entry !== this.entry;
    if (switched) {
      this.entry = entry; this.sequence++; this.busy = false; this.catalogSignature = null; this.initialized = false;
      this.node('validation-output').hidden = true; this.message('');
      this.node('validation-seed').value = '0'; this.node('validation-round').value = '';
    }
    this.options = data.historical_validation || {};
    const ready = this.options.saju_profile_ready === true;
    const catalog = Array.isArray(data.method_catalog) ? data.method_catalog : [];
    const signature = JSON.stringify([ready, catalog.map(m => [m.method_id, m.name])]);
    if (signature !== this.catalogSignature || !this.initialized) {
      const prior = !this.initialized || switched ? null : new Set(this.ids());
      this.catalogSignature = signature;
      const root = this.node('validation-choices'); root.replaceChildren();
      for (const method of catalog) {
        const label = document.createElement('label'); label.className = 'validation-choice';
        const input = document.createElement('input'); input.type = 'checkbox'; input.value = method.method_id;
        input.dataset.profileUnavailable = String(method.method_id === SAJU && !ready);
        input.disabled = method.method_id === SAJU && !ready;
        const text = document.createElement('span');
        text.textContent = method.name + (input.disabled ? ' · 사주정보 설정 필요' : method.method_id === AI ? ' · CCSS 번호만 검증' : '');
        input.checked = !input.disabled && (prior || new Set(this.options.default_method_ids || [])).has(method.method_id);
        label.append(input, text); root.append(label);
      }
      if (prior) this.changed();
    }
    const max = Number(this.options.max_round) || 0, min = Number(this.options.min_round) || 31;
    const input = this.node('validation-round'); input.min = String(min); input.max = String(Math.max(min, max));
    if (!input.value && max >= min) input.value = String(max);
    if (max >= min && catalog.length && Array.isArray(this.options.default_method_ids)) this.initialized = true;
    this.node('validation-range').textContent = max >= min ? `${min}~${max}회 선택 가능 · 공식 이력 기준` : '검증 가능한 공식 이력이 아직 없습니다. 최소 31회 결과가 필요합니다.';
    this.renderConditions();
  }
  renderConditions() {
    const round = Number(this.node('validation-round').value), ids = this.ids();
    this.node('validation-method-count').textContent = `${ids.length}개 선택`;
    this.node('validation-cutoff').textContent = Number.isInteger(round) && round >= 31
      ? `${round}회 검증: 1~${round - 1}회 데이터만 생성에 사용하고, ${round}회 당첨번호는 마지막 대조 단계에서만 사용합니다.` : '';
    this.node('validation-run').disabled = this.busy || !ids.length || !(Number(this.options?.max_round) >= 31);
    this.node('validation-run').textContent = this.busy ? '과거 데이터로 계산 중…' : '검증번호 생성·당첨 확인';
    this.node('validation-form').setAttribute('aria-busy', String(this.busy));
    for (const input of this.node('validation-form').querySelectorAll('input,button:not(#validation-run)')) {
      input.disabled = this.busy || input.dataset.profileUnavailable === 'true';
    }
  }
  async run() {
    if (this.busy || !this.node('validation-form').reportValidity()) return;
    const round = Number(this.node('validation-round').value), seed = Number(this.node('validation-seed').value), method_ids = this.ids();
    if (!method_ids.length) { this.message('검증할 추첨 공식을 선택하세요.', true); return; }
    const sequence = ++this.sequence, entry = this.entry;
    this.busy = true; this.node('validation-output').hidden = true; this.renderConditions();
    this.message(`${round}회 직전까지의 이력으로 번호를 생성하고 있습니다. 실제 추천번호와 리뷰는 변경하지 않습니다.`);
    try {
      const result = await this.panel.request('historical_validate', {round, method_ids, seed});
      if (sequence !== this.sequence || entry !== this.node('entry')?.value || !this.panel.isConnected) return;
      if (result.mode !== 'historical_validation' || result.counts_toward_reviews !== false || result.persisted !== false
          || result.target_round !== round || result.based_on_round !== round - 1 || !Array.isArray(result.results)) throw new Error('검증 응답의 회차 또는 분리 상태를 확인할 수 없습니다.');
      this.render(result);
      this.message(`${round}회 검증 완료. 실제 추천번호·당첨 기록·리뷰 점수는 변경되지 않았습니다.`);
    } catch (error) {
      if (sequence === this.sequence && entry === this.node('entry')?.value && this.panel.isConnected) this.message(error?.message || '과거 검증에 실패했습니다. 기존 기록은 변경되지 않았습니다.', true);
    } finally {
      if (sequence === this.sequence && entry === this.node('entry')?.value) { this.busy = false; this.renderConditions(); }
    }
  }
  render(data) {
    this.node('validation-title').textContent = `${data.target_round}회 검증 결과 · 실제 추천과 별도`;
    this.node('validation-meta').textContent = `사용 이력 1~${data.based_on_round}회 (${data.training_draw_count}회) · 현재 공식 v${data.component_version} · 시드 ${data.seed}`;
    numberBalls(this.node('validation-draw'), data.draw?.numbers || [], data.draw?.bonus);
    this.node('validation-summary').textContent = `검증 ${data.checked_game_count}게임 · 당첨 ${data.winning_game_count}게임${data.highest_prize ? ` · 최고 ${data.highest_prize}` : ''}${data.unavailable_game_count ? ` · 생성 불가 ${data.unavailable_game_count}개` : ''} · 실선: 본번호 일치 / 점선: 보너스 일치`;
    const root = this.node('validation-results');
    renderPredictionRows(root, data.results, ['검증번호가 없습니다.', '다른 추첨 공식을 선택해 다시 실행하세요.']);
    data.results.forEach((row, i) => {
      const tr = root.children[i]; if (!tr) return;
      tr.cells[1].dataset.label = '검증번호'; tr.cells[2].dataset.label = '검증 결과';
      const detail = document.createElement('span'); detail.className = 'validation-comparison';
      detail.textContent = row.generation_status === 'generated'
        ? `본번호 ${row.main_match_count}개 일치${row.bonus_match ? ` · 보너스 ${row.matched_bonus_number} 일치` : ''}`
        : row.reason || '생성 불가';
      tr.cells[2].firstElementChild?.append(detail);
    });
    this.panel.shadowRoot.querySelector('lotto-panel-tools')?.decorate('validation-results', data.results);
    this.node('validation-audit-text').textContent = `생성시각 ${data.generated_at} · 입력 마감 ${data.training_last_round}회 · 검증용 시드 난수 · AI 호출 없음 · 저장 및 리뷰 반영 없음${data.uses_current_saju_profile ? ' · 현재 사주 설정 사용' : ''}. 아래 해시는 생성에 사용한 이전 회차 데이터만의 SHA-256입니다.`;
    this.node('validation-hash').textContent = data.training_sha256;
    this.node('validation-notice').textContent = data.notice;
    this.node('validation-output').hidden = false;
  }
}

export function applyHistoricalValidation(panel) {
  if (!panel.node('screen-validation')) return;
  if (!panel.shadowRoot.querySelector('style[data-lotto-validation]')) {
    const style = document.createElement('style'); style.dataset.lottoValidation = '1.14.0'; style.textContent = STYLE; panel.shadowRoot.append(style);
  }
  if (panel._historicalValidation && panel._historicalValidation.form !== panel.node('validation-form')) { panel._historicalValidation.sequence++; panel._historicalValidation = null; }
  if (!panel._historicalValidation) panel._historicalValidation = new HistoricalValidationView(panel);
  if (panel._latestToolsData) panel._historicalValidation.setData(panel._latestToolsData);
  if (!panel._historicalValidationHook) {
    panel._historicalValidationHook = true;
    const update = panel.updateResults;
    panel.updateResults = function (data, ...args) {
      const value = update.call(this, data, ...args); this._historicalValidation?.setData(data); return value;
    };
  }
}
