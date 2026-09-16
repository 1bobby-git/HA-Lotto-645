/* Fixed-budget read-only design. User text is never rendered as HTML. */
export function parsePortfolioCandidates(value) {
  const parts = String(value).trim().split(/[\s,·]+/);
  const numbers = parts.map(Number);
  if (parts.length < 6 || parts.length > 45 || parts.some(x => !/^\d{1,2}$/.test(x))
      || numbers.some(n => n < 1 || n > 45) || new Set(numbers).size !== numbers.length) {
    throw new Error('1~45의 중복 없는 후보번호 6~45개를 입력하세요.');
  }
  return numbers.sort((a, b) => a - b);
}

const markup = `
<style>
.portfolio-tools{padding:12px;margin-top:10px;border:1px solid var(--line,#ddd);border-radius:12px;background:var(--surface,#fff);color:var(--ink,#222);font-size:13px;line-height:1.5}
.portfolio-tools summary{font-weight:650;cursor:pointer;min-height:32px;line-height:32px}
.portfolio-tools p{margin:6px 0;overflow-wrap:anywhere}
.portfolio-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,140px),1fr));gap:8px}
.portfolio-tools label{display:block;font-weight:600;margin:4px 0}
.portfolio-tools input:not([type=checkbox]),.portfolio-tools select{box-sizing:border-box;width:100%;min-width:0;min-height:40px;padding:8px;border:1px solid var(--field,#aaa);border-radius:8px;background:var(--surface,#fff);color:var(--ink,#222);font:inherit}
.portfolio-tools button{min-height:40px;padding:8px 12px;font:inherit;margin-top:6px}
.portfolio-tools [role=status]{min-height:1.5em;margin-top:6px}
.portfolio-games{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:6px;margin:8px 0}
.portfolio-game{display:flex;gap:6px;align-items:center;border:1px solid var(--line,#ddd);border-radius:8px;padding:6px;min-width:0}
.portfolio-game b{width:18px;text-align:center}
.portfolio-ball{display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:28px;border-radius:50%;font-weight:650;font-variant-numeric:tabular-nums;color:#fff;background:#596574}
.portfolio-ball[data-zone="1"]{background:#896515}.portfolio-ball[data-zone="2"]{background:#2768a0}.portfolio-ball[data-zone="3"]{background:#b74145}.portfolio-ball[data-zone="5"]{background:#347d51}
.portfolio-tools small{font-size:12px;color:var(--muted,#555)}
.portfolio-tools [hidden]{display:none!important}
</style>
<summary>다중 조합 설계 · 1~5게임</summary>
<p>정해진 게임 수 안에서 번호 배분·3수 중복을 조절합니다. 기존 추천·구매·리뷰 기록은 변경하지 않습니다.</p>
<form>
<label for="portfolio-candidates">후보번호 6~45개</label>
<input id="portfolio-candidates" maxlength="160" autocomplete="off" placeholder="예: 1, 5, 10, 15, 20, 25, 30, 35, 45" aria-describedby="portfolio-help">
<div class="portfolio-controls">
<label>설계 방식<select id="portfolio-mode"><option value="balanced">번호 배분</option><option value="coverage">3수 커버리지</option><option value="wheel9">9후보 · 3게임 휠링</option></select></label>
<label>게임 수<select id="portfolio-count"><option>1</option><option>2</option><option>3</option><option>4</option><option selected>5</option></select></label>
<label>게임 간 최대 중복<select id="portfolio-overlap"><option value="6">제한 없음</option><option value="5">5개</option><option value="4">4개</option><option value="3">3개</option><option value="2">2개</option><option value="1">1개</option><option value="0">없음</option></select></label>
</div>
<label><input id="portfolio-rules" type="checkbox" checked> 통합 구성의 조건 지정 생성 설정 적용</label>
<p id="portfolio-help"><small>휠링은 후보 9개·3게임을 직접 지정해야 합니다. 조건을 만족하지 못하면 이유를 표시하며 임의로 완화하지 않습니다.</small></p>
<button type="submit">조합 설계</button>
</form>
<section data-portfolio-result hidden><strong data-portfolio-title></strong><div class="portfolio-games"></div><p data-portfolio-metrics></p><p data-portfolio-bound></p><p data-portfolio-notice></p></section>
<p role="status" aria-live="polite" aria-atomic="true"></p>
`;

export function installPortfolioTools(Panel) {
  const baseRender = Panel.prototype.render;
  Panel.prototype.render = function (...args) {
    const result = baseRender.apply(this, args);
    const home = this.node('screen-home');
    if (!home || this.node('portfolio-tools')) return result;
    const box = document.createElement('details');
    box.id = 'portfolio-tools'; box.className = 'portfolio-tools'; box.innerHTML = markup;
    home.append(box);
    const field = box.querySelector('#portfolio-candidates');
    const status = box.querySelector('[role=status]');
    const output = box.querySelector('[data-portfolio-result]');
    const games = box.querySelector('.portfolio-games');
    const button = box.querySelector('button');
    const mode = box.querySelector('#portfolio-mode');
    const count = box.querySelector('#portfolio-count');
    let sequence = 0, pending = false;
    const reset = () => {
      sequence++; pending = false; button.disabled = false; output.hidden = true;
      box.removeAttribute('aria-busy'); games.replaceChildren(); status.textContent = '';
    };
    this._resetPortfolioTools = reset;
    box.querySelectorAll('input,select').forEach(control => {
      control.addEventListener('input', reset); control.addEventListener('change', reset);
    });
    this.node('entry')?.addEventListener('change', () => { reset(); field.value = ''; });
    box.querySelector('form').addEventListener('submit', async event => {
      event.preventDefault();
      if (pending) return;
      let candidate_numbers;
      try {
        candidate_numbers = parsePortfolioCandidates(field.value);
        if (mode.value === 'wheel9' && (candidate_numbers.length !== 9 || Number(count.value) !== 3)) {
          throw new Error('9후보 휠링은 후보 9개·게임 수 3개를 선택하세요.');
        }
      } catch (error) { status.textContent = error.message; field.focus(); return; }
      const entry = this.node('entry')?.value, token = ++sequence;
      const expectedCount = Number(count.value);
      pending = true; button.disabled = true; output.hidden = true; games.replaceChildren();
      box.setAttribute('aria-busy', 'true'); status.textContent = '조건 확인·조합 설계 중입니다.';
      try {
        const data = await this.request('portfolio_coverage', {
          candidate_numbers, ticket_count: expectedCount, mode: mode.value,
          max_overlap: Number(box.querySelector('#portfolio-overlap').value),
          apply_rules: box.querySelector('#portfolio-rules').checked,
        });
        if (!box.isConnected || token !== sequence || entry !== this.node('entry')?.value) return;
        if (!Array.isArray(data.tickets) || data.tickets.length !== expectedCount
            || data.tickets.some(row => !Array.isArray(row) || row.length !== 6 || new Set(row).size !== 6
              || row.some(n => !Number.isInteger(n) || n < 1 || n > 45))
            || new Set(data.tickets.map(row => [...row].sort((a,b)=>a-b).join(','))).size !== expectedCount) {
          throw new Error('요청한 게임 수와 일치하는 유효한 조합을 받지 못했습니다.');
        }
        box.querySelector('[data-portfolio-title]').textContent = `${data.target_round}회용 · ${expectedCount}게임 · 미구매`;
        for (const [i, ticket] of data.tickets.entries()) {
          const row = document.createElement('div'); row.className = 'portfolio-game';
          const label = document.createElement('b'); label.textContent = String.fromCharCode(65+i); row.append(label);
          for (const n of [...ticket].sort((a,b)=>a-b)) {
            const ball = document.createElement('span'); ball.className = 'portfolio-ball';
            ball.dataset.zone = String(Math.ceil(n/10)); ball.textContent = String(n); row.append(ball);
          }
          games.append(row);
        }
        box.querySelector('[data-portfolio-metrics]').textContent = `사용한 번호 ${data.number_coverage}/${data.candidate_count}개 · 번호쌍 ${data.pair_coverage}종 · 3수 묶음 ${data.triple_coverage}종 · 최대 중복 ${data.maximum_overlap}개`;
        const bounds = data.conditional_min_match || {};
        box.querySelector('[data-portfolio-bound]').textContent = data.verification_complete === true
          ? `전수 확인 ${data.verification_cases}경우. ` + Object.entries(bounds).map(([r,k])=>`후보 내 본번호 ${r}개 포함 → 한 게임 이상 최소 ${k}개 일치`).join(' / ')
          : '후보군이 커 조건부 최소 일치를 전수 검증하지 않았습니다. 보장을 표시하지 않습니다.';
        box.querySelector('[data-portfolio-notice]').textContent = `${data.saved_rules_applied ? '저장 조건 적용.' : '저장 조건 미적용.'} ${data.notice || '후보 적중·1등·수익을 보장하지 않습니다.'}`;
        output.hidden = false; status.textContent = '미리보기 완료 · 구매번호로 저장하지 않았습니다.';
      } catch (error) {
        if (token === sequence && box.isConnected) status.textContent = error?.message || '조합을 설계하지 못했습니다.';
      } finally {
        if (token === sequence) { pending = false; button.disabled = false; box.removeAttribute('aria-busy'); }
      }
    });
    return result;
  };
  const baseDisconnected = Panel.prototype.disconnectedCallback;
  Panel.prototype.disconnectedCallback = function (...args) {
    this._resetPortfolioTools?.();
    return baseDisconnected?.apply(this, args);
  };
}
