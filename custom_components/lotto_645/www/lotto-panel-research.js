/* Explicit read-only previews; never register previews as purchased tickets. */
export function parseCandidates(value) {
  const parts = String(value).trim().split(/[\s,·]+/);
  if (parts.length !== 8 || parts.some(x => !/^\d{1,2}$/.test(x))) {
    throw new Error('1~45에서 후보번호 8개를 공백 또는 쉼표로 구분해 입력하세요.');
  }
  const numbers = parts.map(Number);
  if (numbers.some(n => n < 1 || n > 45) || new Set(numbers).size !== 8) {
    throw new Error('후보번호는 1~45의 중복 없는 8개여야 합니다.');
  }
  return numbers.sort((a, b) => a - b);
}

const template = `
<style>
.research-tools{margin-top:16px;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);font-size:13px}
.research-tools>summary{cursor:pointer;font-weight:650;min-height:28px;line-height:28px}
.research-tools p{margin:6px 0;overflow-wrap:anywhere;color:var(--muted);line-height:1.55}
.research-tools label{display:block;font-weight:600;margin:8px 0 4px}
.research-controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.research-controls input{flex:1 1 210px;min-width:0;box-sizing:border-box;max-width:100%;min-height:40px;padding:8px 10px;border:1px solid var(--field);border-radius:8px;background:var(--surface);color:var(--ink)}
.research-tools button{font:inherit;min-height:40px;padding:8px 12px}
.research-games{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:6px;margin:8px 0}
.research-game{display:grid;grid-template-columns:22px repeat(6,minmax(0,1fr));align-items:center;gap:4px;padding:6px;border:1px solid var(--line);border-radius:8px;font-variant-numeric:tabular-nums}
.research-game span{text-align:center;color:var(--ink);font-weight:650}
.research-tools [role=status]{min-height:1.5em}
.research-diagnostic{margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}
</style>
<summary>연구 공식 도구 · 4게임 휠링 / 추첨 빈도 진단</summary>
<p>번호 추천에 비인기 패턴 회피·3수 커버리지 보완을 사용하려면 통합 설정의 추첨 공식에서 선택하세요.</p>
<form data-research-form>
<label for="research-candidates">휠링 후보번호 8개</label>
<div class="research-controls"><input id="research-candidates" type="text" maxlength="120" placeholder="예: 1, 5, 10, 15, 20, 25, 35, 45" autocomplete="off" aria-describedby="research-wheel-help"><button type="submit">4게임 생성</button></div>
<p id="research-wheel-help">후보 안의 모든 3수 부분집합 56개를 덮습니다. 4게임 전체가 필요하며 후보 적중·1등을 보장하지 않습니다. 과거 1등과 현재 추천 조합은 제외합니다.</p>
</form>
<div data-research-wheel hidden><strong data-research-title></strong><div class="research-games" data-research-games></div><p data-research-notice></p></div>
<div class="research-diagnostic"><button type="button" data-research-diagnostic>추첨 빈도 진단</button><p data-research-diagnostic-result></p></div>
<p data-research-status role="status" aria-live="polite" aria-atomic="true"></p>
`;

export function installResearchTools(Panel) {
  const baseRender = Panel.prototype.render;
  Panel.prototype.render = function (...args) {
    const result = baseRender.apply(this, args);
    const home = this.node('screen-home');
    if (!home || this.node('research-tools')) return result;
    const box = document.createElement('details');
    box.id = 'research-tools'; box.className = 'research-tools'; box.innerHTML = template;
    home.append(box);
    const input = box.querySelector('input');
    const status = box.querySelector('[data-research-status]');
    const output = box.querySelector('[data-research-wheel]');
    const games = box.querySelector('[data-research-games]');
    const diagnostic = box.querySelector('[data-research-diagnostic-result]');
    const buttons = [...box.querySelectorAll('button')];
    let sequence = 0, pending = false;
    const reset = () => {
      sequence++; pending = false; buttons.forEach(b => b.disabled = false);
      box.removeAttribute('aria-busy'); output.hidden = true; games.replaceChildren();
      diagnostic.textContent = ''; status.textContent = '';
    };
    this._resetResearchTools = reset;
    input.addEventListener('input', reset);
    this.node('entry').addEventListener('change', () => { reset(); input.value = ''; });
    const run = async (type, payload, render) => {
      if (pending) return;
      const entry = this.node('entry').value, token = ++sequence;
      pending = true; buttons.forEach(b => b.disabled = true); box.setAttribute('aria-busy', 'true');
      status.textContent = '계산 중입니다. 실제 추천·구매·리뷰 기록은 변경하지 않습니다.';
      try {
        const data = await this.request(type, payload);
        if (!box.isConnected || token !== sequence || entry !== this.node('entry').value) return;
        render(data); status.textContent = '미리보기입니다. 구매번호로 저장하지 않았습니다.';
      } catch (error) {
        if (token === sequence && box.isConnected) status.textContent = error?.message || '계산하지 못했습니다.';
      } finally {
        if (token === sequence) {
          pending = false; buttons.forEach(b => b.disabled = false); box.removeAttribute('aria-busy');
        }
      }
    };
    box.querySelector('form').addEventListener('submit', event => {
      event.preventDefault();
      if (pending) return;
      let candidate_numbers;
      try { candidate_numbers = parseCandidates(input.value); }
      catch (error) { status.textContent = error.message; input.focus(); return; }
      output.hidden = true; games.replaceChildren();
      void run('covering_wheel', {candidate_numbers}, data => {
        if (!Array.isArray(data.tickets) || data.tickets.length !== 4
          || data.tickets.some(row => !Array.isArray(row) || row.length !== 6
            || new Set(row).size !== 6 || row.some(n => !Number.isInteger(n) || n < 1 || n > 45))) {
          throw new Error('올바른 4게임 결과를 받지 못했습니다. 다시 생성하세요.');
        }
        box.querySelector('[data-research-title]').textContent = `${data.target_round}회용 · 4게임 · 미구매`;
        data.tickets.forEach((numbers, index) => {
          const row = document.createElement('div'); row.className = 'research-game';
          for (const value of [String.fromCharCode(65 + index), ...numbers]) {
            const span = document.createElement('span'); span.textContent = String(value); row.append(span);
          }
          games.append(row);
        });
        box.querySelector('[data-research-notice]').textContent = `${data.notice} 게임당 1등 확률은 1/8,145,060입니다.`;
        output.hidden = false;
      });
    });
    box.querySelector('[data-research-diagnostic]').addEventListener('click', () => {
      diagnostic.textContent = '';
      void run('research_diagnostics', {}, data => {
        const p = data.p_value;
        const value = typeof p === 'number' && Number.isFinite(p)
          ? (p === 0 ? '계산 정밀도 이하' : p.toPrecision(4)) : '표본 부족으로 미표시';
        const q = Number.isFinite(data.corrected_statistic) ? data.corrected_statistic.toFixed(3) : '—';
        diagnostic.textContent = `${data.sample_size}회 분석 · 보정 통계량 ${q} · 점근 p값 ${value}. ${data.notice || '공식 이력이 필요합니다.'}`;
      });
    });
    return result;
  };
  const baseDisconnected = Panel.prototype.disconnectedCallback;
  Panel.prototype.disconnectedCallback = function (...args) {
    this._resetResearchTools?.();
    return baseDisconnected.apply(this, args);
  };
}
