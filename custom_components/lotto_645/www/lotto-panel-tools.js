/* Read-only method help and local countdown. Never polls or generates numbers. */
const VERSION = '2.0.4';
const WEEK = 7 * 86400000;
const DOC_CACHE = new Map();
import {reviewPresentation} from './lotto-panel-view.js?v=2.0.4';
const AI_ID = 'home_assistant_ai';
const validId = id => typeof id === 'string' && /^[a-z][a-z0-9_]{0,63}$/.test(id);
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};

// Stay in normal flow: HA reserves sidebar space with padding/margins, not
// necessarily a positioned ancestor. Absolute inset:0 would escape that space.
// Keep height/size containment and one panel scrollport without reading or
// changing parent/HA shadow DOM, sidebar widths, or global document styles.
const PANEL_STYLE = `
:host{position:relative;inset:auto;display:block;box-sizing:border-box;width:100%;height:100%;min-height:0;max-height:100%;min-width:0;overflow:auto;contain:layout size;overscroll-behavior-y:contain}
:host([data-editor-open]),:host([data-method-open]){overflow:hidden}
.shell{min-height:100%;box-sizing:border-box}
.table-scroll{max-height:none;overflow:visible}
.mobile-table{width:100%;max-width:100%;table-layout:fixed}
.mobile-table th,.mobile-table td{overflow-wrap:anywhere}
.mobile-table .ticket-balls{flex-wrap:wrap;row-gap:5px}
.method-info-trigger{display:inline-flex;align-items:center;justify-content:flex-start;gap:6px;width:auto;max-width:100%;min-height:44px;padding:4px 0;border:0;background:transparent;color:var(--blue);text-align:left;font-size:inherit;font-weight:inherit;line-height:1.6;box-shadow:none;white-space:normal}
.method-info-trigger span{min-width:0;overflow-wrap:anywhere;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:4px}
.method-info-trigger::after{content:'ⓘ';flex:none;font-size:14px;font-weight:400}
.method-info-trigger:hover:not(:disabled){background:var(--blue-soft);filter:none}
.method-help-hint{margin:0 0 12px;color:var(--muted);font-size:13px}
@container wallet (min-width:561px){
 table:has(#predictions) th:first-child{width:43%}
 table:has(#predictions) th:nth-child(2){width:42%}
 table:has(#predictions) th:last-child{width:15%}
 table:has(#reviews) th:first-child{width:44%}
 table:has(#reviews) th:not(:first-child){width:14%}
}
`;

export function countdownState(schedule, now = Date.now()) {
  if (!schedule || schedule.basis !== 'regular_schedule') return null;
  let at = Date.parse(schedule.scheduled_at), rollover = Date.parse(schedule.rollover_at);
  let round = Number(schedule.round);
  if (!Number.isFinite(at) || !Number.isFinite(rollover) || !Number.isInteger(round)
      || round < 1 || rollover <= at || rollover - at > 86400000 || !Number.isFinite(now)) return null;
  if (now >= rollover) {
    const weeks = Math.floor((now - rollover) / WEEK) + 1;
    at += weeks * WEEK; round += weeks;
  }
  const seconds = Math.max(0, Math.ceil((at - now) / 1000));
  return { round, at, waiting: seconds === 0, seconds,
    days: Math.floor(seconds / 86400), hours: Math.floor(seconds % 86400 / 3600),
    minutes: Math.floor(seconds % 3600 / 60), remainder: seconds % 60 };
}
const sourceURL = id => new URL(`./methods/${id}.md`,import.meta.url).href;

// DOM-only subset covering our bundled Markdown guides. Raw HTML stays text;
// never evaluate Markdown, inject its HTML, or load images/external parsers.
function inline(parent, text, base) {
  const tokens = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^\s)]+\))/g;
  let offset = 0;
  for (const match of text.matchAll(tokens)) {
    parent.append(document.createTextNode(text.slice(offset, match.index)));
    const value = match[0];
    if (value.startsWith('`')) parent.append(element('code', value.slice(1, -1)));
    else if (value.startsWith('**')) parent.append(element('strong', value.slice(2, -2)));
    else {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(value);
      let url;
      try { url = new URL(link[2], base); } catch { /* display literal below */ }
      if (url && ['https:', 'http:'].includes(url.protocol)) {
        const a = element('a', link[1]); a.href = url.href;
        a.target = '_blank'; a.rel = 'noopener noreferrer'; parent.append(a);
      } else parent.append(document.createTextNode(value));
    }
    offset = match.index + value.length;
  }
  parent.append(document.createTextNode(text.slice(offset)));
}
export function renderGuideMarkdown(text, base) {
  const root = document.createDocumentFragment();
  const lines = String(text).replace(/\r\n?/g, '\n').split('\n');
  const cells = line => line.trim().replace(/^\||\|$/g, '').split('|').map(v => v.trim());
  const separator = line => /^\s*\|?\s*:?-{3,}/.test(line || '') && cells(line).every(v => /^:?-{3,}:?$/.test(v));
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (/^```/.test(line)) {
      const pre = element('pre'), code = element('code'), body = []; i++;
      while (i < lines.length && !/^```/.test(lines[i])) body.push(lines[i++]);
      code.textContent = body.join('\n'); pre.append(code); root.append(pre); i++; continue;
    }
    if (line.includes('|') && separator(lines[i + 1])) {
      const table = element('table'), head = element('thead'), hr = element('tr');
      for (const value of cells(line)) { const th = element('th'); th.scope = 'col'; inline(th, value, base); hr.append(th); }
      head.append(hr); table.append(head); const body = element('tbody'); i += 2;
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        const tr = element('tr');
        for (const value of cells(lines[i++])) { const td = element('td'); inline(td, value, base); tr.append(td); }
        body.append(tr);
      }
      table.append(body); root.append(table); continue;
    }
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) { const h = element(`h${Math.min(6, heading[1].length + 1)}`); inline(h, heading[2], base); root.append(h); i++; continue; }
    if (/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)) { root.append(element('hr')); i++; continue; }
    const list = /^\s*(?:([-*+])|\d+\.)\s+(.+)$/.exec(line);
    if (list) {
      const ul = element(list[1] ? 'ul' : 'ol');
      while (i < lines.length) {
        const item = /^\s*(?:([-*+])|\d+\.)\s+(.+)$/.exec(lines[i]);
        if (!item || Boolean(item[1]) !== Boolean(list[1])) break;
        const li = element('li'); inline(li, item[2], base); ul.append(li); i++;
      }
      root.append(ul); continue;
    }
    if (/^>\s?/.test(line)) { const quote = element('blockquote'); inline(quote, line.replace(/^>\s?/, ''), base); root.append(quote); i++; continue; }
    const p = element('p'), body = [line]; i++;
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|>|\s*[-*+]\s|\d+\.\s)/.test(lines[i]) && !separator(lines[i + 1])) body.push(lines[i++]);
    inline(p, body.join('\n'), base); root.append(p);
  }
  return root;
}

const TOOL_STYLE = `
:host{display:block;margin:0 0 24px;min-width:0;font:inherit;color:var(--ink)}
*{box-sizing:border-box}[hidden]{display:none!important}
.countdown{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px 24px;padding:16px 20px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}
.clock-label{margin:0;font-size:13px;color:var(--muted)}
.clock-value{display:block;min-height:30px;font-size:22px;line-height:1.5;font-weight:750;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.clock-date{font-size:13px;color:var(--muted)}
.clock-note{margin:0;font-size:12px;line-height:1.65;color:var(--muted);text-align:right;max-width:380px}
a{color:var(--blue);text-underline-offset:3px}button{font:inherit;cursor:pointer}
:focus-visible{outline:3px solid var(--blue);outline-offset:3px}
dialog{position:fixed;inset:var(--lotto-safe-top,0px) var(--lotto-viewport-right,0px) var(--lotto-safe-bottom,0px) var(--lotto-viewport-left,0px);margin:auto;width:min(780px,calc(100vw - 32px - var(--lotto-viewport-left,0px) - var(--lotto-viewport-right,0px)));height:min(840px,calc(100dvh - 32px - var(--lotto-safe-top,0px) - var(--lotto-safe-bottom,0px)));max-height:calc(100dvh - var(--lotto-safe-top,0px) - var(--lotto-safe-bottom,0px));max-width:100%;padding:0;border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--ink);box-shadow:0 8px 32px #0003;overflow:hidden;font:inherit}
dialog[open]{display:flex;flex-direction:column}
dialog::backdrop{background:#11182788}
.method-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px;border-bottom:1px solid var(--line);flex:none}
.method-title{margin:0;font-size:20px;font-weight:750;line-height:1.4;overflow-wrap:anywhere}
.method-close{min-width:44px;min-height:44px;flex:none;padding:8px;border:0;border-radius:10px;background:var(--soft);color:var(--ink);font-size:22px}
.method-body{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;padding:20px;font-size:14px;line-height:1.8;overflow-wrap:anywhere}
.method-body h2{font-size:20px}.method-body h3{font-size:17px}.method-body h4{font-size:15px}
.method-body h2,.method-body h3,.method-body h4{line-height:1.5;margin:24px 0 10px}
.method-body>:first-child{margin-top:0}.method-body p{margin:10px 0;white-space:pre-line}
.method-body ul,.method-body ol{padding-left:24px}.method-body li{margin:6px 0}
.method-body table{border-collapse:collapse;width:100%;table-layout:fixed;margin:16px 0;font-size:13px}
.method-body th,.method-body td{border:1px solid var(--line);padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
.method-body th{background:var(--soft)}
.method-body pre{background:var(--soft);border-radius:10px;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
.method-body code{font-family:ui-monospace,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
.method-body blockquote{border-left:3px solid var(--blue);padding-left:12px;margin:12px 0;color:var(--muted)}
.method-foot{flex:none;border-top:1px solid var(--line);padding:12px 20px;color:var(--muted);font-size:12px;line-height:1.7}
.method-foot p{margin:0}.method-foot a{display:inline-flex;min-height:32px;align-items:center}
.method-error{color:var(--danger)}.method-retry{min-height:44px;padding:8px 16px;border:0;border-radius:10px;color:var(--blue);background:var(--blue-soft)}
@container wallet (max-width:560px){.countdown{padding:14px 16px;gap:8px}.clock-note{text-align:left;max-width:none}.clock-value{font-size:20px}}
@media(max-width:560px){
 dialog{width:auto;height:auto;max-height:none;margin:0;max-width:none;border-radius:0}
 .method-head{padding:12px 16px}.method-title{font-size:18px}.method-body{padding:16px}.method-foot{padding:12px 16px}
}
@media(forced-colors:active){dialog,.countdown{border:1px solid CanvasText}}
`;

class LottoPanelTools extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:'open'});
    // Only this fixed, developer-controlled template uses innerHTML.
    this.shadowRoot.innerHTML = `<style>${TOOL_STYLE}</style>
      <section class="countdown" aria-label="회차별 추첨 일정" hidden>
        <div><p class="clock-label"></p><strong class="clock-value" role="timer" aria-live="off"></strong><div class="clock-date"></div></div>
        <p class="clock-note">정규 일정 기준 · 회차별 방송 편성 변경은 자동 확인하지 않습니다.<br><a href="https://www.dhlottery.co.kr/guide/wnrGuide" target="_blank" rel="noopener noreferrer">동행복권 추첨 안내</a> · <a href="https://program.imbc.com/lotto" target="_blank" rel="noopener noreferrer">MBC 방송 안내</a></p>
      </section>
      <dialog id="method-dialog" aria-modal="true" aria-labelledby="method-title">
        <header class="method-head"><h2 id="method-title" class="method-title" tabindex="-1"></h2><button class="method-close" type="button" aria-label="추첨 공식 설명 닫기">×</button></header>
        <div class="method-body" tabindex="0" aria-label="추첨 공식 상세 설명"></div>
        <footer class="method-foot"><p>추천 점수와 과거 리뷰는 당첨 확률이 아닙니다.</p><button class="method-source" type="button">닫기</button></footer>
      </dialog>`;
    this.catalog = new Map(); this._generation = 0;
    this.shadowRoot.querySelector('.method-close').onclick = () => this.closeGuide();
    this.dialog.addEventListener('cancel', event => { event.preventDefault(); this.closeGuide(); });
    this.dialog.addEventListener('close', () => this.afterClose());
    this.dialog.addEventListener('keydown', event => this.trapFocus(event));
    this.dialog.addEventListener('click', event => {
      if (event.target !== this.dialog) return;
      const r = this.dialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) this.closeGuide();
    });
    this.shadowRoot.addEventListener('click', event => {
      const a = event.target.closest?.('a'); if (!a || a.classList.contains('method-source')) return;
      const url = new URL(a.href);
      const match = /\/lotto_645_static\/methods\/([a-z0-9_]+)\.md$/.exec(url.pathname);
      if (url.origin === location.origin && match && this.catalog.has(match[1])) { event.preventDefault(); void this.openGuide(match[1]); }
    });
  }
  get dialog() { return this.shadowRoot.querySelector('dialog'); }
  connectedCallback() {
    if (!this.panel) return;
    this._onClick = event => {
      const trigger = event.target.closest?.('.method-info-trigger');
      if (trigger) void this.openGuide(trigger.dataset.methodId, trigger);
    };
    this.panel.shadowRoot.addEventListener('click', this._onClick);
    this._visibility = () => document.hidden ? this.stopClock() : this.startClock();
    document.addEventListener('visibilitychange', this._visibility);
    this._pageHide = () => { this.stopClock(); this.closeGuide(false); };
    this._pageShow = () => this.startClock();
    window.addEventListener('pagehide', this._pageHide); window.addEventListener('pageshow', this._pageShow);
    this._panelVisible = true;
    if (globalThis.IntersectionObserver) {
      this._observer = new IntersectionObserver(entries => {
        this._panelVisible = entries[0]?.isIntersecting !== false;
        if (this._panelVisible) this.startClock();
        else { this.stopClock(); this.closeGuide(false); }
      });
      this._observer.observe(this.panel);
    }
    this.startClock();
  }
  disconnectedCallback() {
    this.stopClock(); this.closeGuide(false); this._generation++; this._observer?.disconnect();
    this.panel?.shadowRoot.removeEventListener('click', this._onClick);
    document.removeEventListener('visibilitychange', this._visibility);
    window.removeEventListener('pagehide', this._pageHide); window.removeEventListener('pageshow', this._pageShow);
  }
  setData(data) {
    const entry = this.panel.node('entry')?.value;
    if (this._entry && entry !== this._entry) this.closeGuide(false);
    this._entry = entry;
    this.catalog = new Map([...(data.method_catalog || []), ...(data.archived_method_catalog || [])].filter(m => validId(m.method_id)).map(m => [m.method_id, m]));
    this.schedule = data.draw_schedule;
    const serverNow = Date.parse(this.schedule?.server_now);
    this._clockOffset = Number.isFinite(serverNow) ? serverNow - Date.now() : 0;
    this.decorate('predictions', reviewPresentation(data).rows);
    this.decorate('reviews', data.reviews || []);
    this.startClock();
  }
  decorate(id, rows) {
    const table = this.panel.node(id); if (!table) return;
    const nodes = [...table.children];
    rows.forEach((row, index) => {
      const cell = nodes[index]?.querySelector('td');
      if (!cell || !this.catalog.has(row.method_id)) return;
      const text = cell.textContent;
      const button = element('button', undefined, 'method-info-trigger');
      button.type = 'button'; button.dataset.methodId = row.method_id; button.dataset.table = id;
      button.setAttribute('aria-haspopup', 'dialog'); button.setAttribute('aria-label', `${text} 상세 설명 열기`);
      button.append(element('span', text)); cell.replaceChildren(button);
    });
  }
  stopClock() { clearTimeout(this._clockTimer); this._clockTimer = null; }
  startClock() {
    this.stopClock(); this.tickClock();
    if (this.isConnected && !document.hidden && this._panelVisible !== false && countdownState(this.schedule)) this._clockTimer = setTimeout(() => this.startClock(), 1000);
  }
  tickClock(now = Date.now() + (this._clockOffset || 0)) {
    const state = countdownState(this.schedule, now);
    const section = this.shadowRoot.querySelector('.countdown'); section.hidden = !state;
    if (!state) return;
    const set = (selector, value) => { const n = this.shadowRoot.querySelector(selector); if (n.textContent !== value) n.textContent = value; };
    set('.clock-label', `${state.waiting ? '결과 확인 대기' : '다음 추첨까지'} · 제 ${state.round.toLocaleString('ko-KR')}회`);
    const pad = n => String(n).padStart(2, '0');
    set('.clock-value', state.waiting ? '추첨 예정 시각이 지났어요' : `${state.days}일 ${pad(state.hours)}시간 ${pad(state.minutes)}분 ${pad(state.remainder)}초`);
    const time = new Intl.DateTimeFormat('ko-KR', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',weekday:'short',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(state.at));
    set('.clock-date', `${time}경 · 한국시간`);
  }
  async openGuide(id, opener) {
    if (!validId(id) || !this.catalog.has(id) || !this.isConnected || this.panel.node('editor')?.open) return;
    this._restoreFocus = true;
    if (opener) this._opener = {node:opener, id, table:opener.dataset.table};
    const generation = ++this._generation;
    this._currentMethod = id;
    this.shadowRoot.querySelector('.method-title').textContent = this.catalog.get(id).name || id;
    this.shadowRoot.querySelector('.method-source').onclick = () => this.closeGuide();
    const body = this.shadowRoot.querySelector('.method-body');
    body.replaceChildren(element('p', '상세 설명을 불러오고 있어요.')); body.setAttribute('aria-busy', 'true');
    this.panel.setAttribute('data-method-open', '');
    if (!this.dialog.open) this.dialog.showModal();
    this.shadowRoot.querySelector('.method-title').focus({preventScroll:true});
    try {
      let pending = DOC_CACHE.get(id);
      if (!pending) {
        pending = (async () => {
          const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 10000);
          try {
            const response = await fetch(sourceURL(id), {credentials:'same-origin', redirect:'error', signal:controller.signal});
            if (!response.ok) throw new Error('guide_unavailable');
            const text = await response.text();
            if (text.length > 200000 || !text.trimStart().startsWith('# ')) throw new Error('invalid_guide');
            return text;
          } finally { clearTimeout(timer); }
        })();
        DOC_CACHE.set(id, pending);
        pending.catch(() => { if (DOC_CACHE.get(id) === pending) DOC_CACHE.delete(id); });
      }
      const markdown = await pending;
      if (generation !== this._generation || !this.isConnected || !this.dialog.open) return;
      body.replaceChildren(renderGuideMarkdown(markdown, sourceURL(id))); body.scrollTop = 0;
    } catch {
      if (generation !== this._generation || !this.isConnected || !this.dialog.open) return;
      const error = element('p', '설명을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.', 'method-error'); error.setAttribute('role', 'alert');
      const retry = element('button', '다시 불러오기', 'method-retry'); retry.type = 'button'; retry.onclick = () => void this.openGuide(id);
      body.replaceChildren(error, retry);
    } finally { if (generation === this._generation) body.removeAttribute('aria-busy'); }
  }
  closeGuide(restore = true) {
    this._restoreFocus = restore; this._generation++;
    if (this.dialog.open) this.dialog.close();
    this.afterClose();
  }
  afterClose() {
    if (this.dialog.open) return;
    this.panel?.removeAttribute('data-method-open');
    const opener = this._opener; this._opener = null;
    if (!opener || this._restoreFocus === false || !this.panel?.isConnected) return;
    const target = opener.node.isConnected ? opener.node : [...(this.panel.node(opener.table)?.querySelectorAll('.method-info-trigger') || [])].find(n => n.dataset.methodId === opener.id);
    target?.focus({preventScroll:true});
  }
  trapFocus(event) {
    if (event.key !== 'Tab') return;
    const focusable = [...this.dialog.querySelectorAll('button,a[href],[tabindex="0"]')].filter(n => !n.disabled && n.getClientRects().length);
    const first = focusable[0], last = focusable.at(-1), active = this.shadowRoot.activeElement;
    if (event.shiftKey && (active === first || active === this.shadowRoot.querySelector('.method-title'))) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && active === last) { event.preventDefault(); first?.focus(); }
  }
}
if (!customElements.get('lotto-panel-tools-v2-0-4')) customElements.define('lotto-panel-tools-v2-0-4', LottoPanelTools);

export function applyPanelTools(panel) {
  const root = panel.shadowRoot, main = root?.querySelector('main'); if (!main) return;
  if (!root.querySelector('style[data-lotto-panel-tools-v2-0-4]')) {
    const style = element('style'); style.dataset.lottoPanelTools = VERSION; style.textContent = PANEL_STYLE; root.append(style);
  }
  if (!root.querySelector('lotto-panel-tools-v2-0-4')) {
    const tools = document.createElement('lotto-panel-tools-v2-0-4'); tools.panel = panel; main.prepend(tools);
    if (panel._latestToolsData) tools.setData(panel._latestToolsData);
  }
  for (const id of ['current-recommendations', 'predictions', 'reviews']) {
    const block = panel.node(id)?.closest('.review-block');
    if (block && !block.querySelector('.method-help-hint')) {
      const hint = element('p', '공식 이름을 누르면 번호 선택 방식과 이용 시 참고사항을 볼 수 있어요.', 'method-help-hint'); block.insertBefore(hint, block.querySelector('.table-scroll'));
    }
  }
  if (!panel._toolsDataHook) {
    panel._toolsDataHook = true;
    const update = panel.updateResults;
    panel.updateResults = function (data, ...args) {
      const result = update.call(this, data, ...args); this._latestToolsData = data;
      this.shadowRoot.querySelector('lotto-panel-tools-v2-0-4')?.setData(data); return result;
    };
  }
}
