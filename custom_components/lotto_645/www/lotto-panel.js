/* UI entry point: two-tier Home Assistant header plus demand-driven panel synchronization. */
import { PANEL_TAG } from './lotto-panel-core.js?v=2.1.1';

const PANEL_NAME = 'Lotto 6/45 Analysis';
const PANEL_SYNC_INTERVAL = 60_000;
const PANEL_RESUME_MIN_GAP = 15_000;
const KST_OFFSET = 9 * 60 * 60 * 1000;
const OFFICIAL_RESULT_STATES = new Set(['official_history', 'official_confirmed', 'official_corrected']);
const UNSETTLED_RESULT_STATES = new Set(['provisional', 'cross_checked', 'conflict']);

const HEADER_STYLE = `
.app-header{padding-top:var(--lotto-safe-top)}
.header-row{
  display:grid;
  grid-template-columns:48px minmax(0,1fr) auto;
  grid-template-rows:66px 82px;
  column-gap:14px;
  row-gap:0;
  min-height:148px;
  align-items:center;
  position:relative;
  background:linear-gradient(var(--line),var(--line)) left 66px/100% 1px no-repeat;
}
#menu{
  grid-column:1;
  grid-row:1;
  width:44px;
  min-width:44px;
  height:44px;
  min-height:44px;
  padding:0;
  border:1px solid var(--field);
  border-radius:50%;
  background:transparent;
  color:var(--ink);
  justify-self:start;
}
#menu:hover:not(:disabled){background:var(--soft);filter:none}
.ha-component-title{
  grid-column:2 / 4;
  grid-row:1;
  min-width:0;
  align-self:center;
  color:var(--ink);
  font-size:18px;
  font-weight:650;
  line-height:1.3;
  letter-spacing:-.025em;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
#brand-home{
  grid-column:1 / 3;
  grid-row:2;
  align-self:center;
  justify-self:start;
}
.header-label{display:none!important}
.header-tools{
  grid-column:3;
  grid-row:2;
  align-self:center;
  justify-self:end;
  margin-left:0;
}
@container wallet (max-width:560px){
  .header-row{
    grid-template-columns:48px minmax(0,1fr) 44px;
    grid-template-rows:64px 76px auto;
    min-height:140px;
    column-gap:10px;
    background-position:left 64px;
  }
  .ha-component-title{grid-column:2 / 4;font-size:17px;padding-right:4px}
  #brand-home{grid-column:1 / 3;grid-row:2;min-width:0}
  .brand-logo{width:min(146px,44vw)}
  .header-tools{display:contents}
  .header-tools .settings{grid-column:3;grid-row:2;justify-self:end;align-self:center;margin-left:0}
  .entry-field{
    grid-column:1 / -1;
    grid-row:3;
    order:initial;
    flex-basis:auto;
    max-width:none;
    width:100%;
    padding:0 0 12px;
  }
  .entry-field select{max-width:none;width:100%;font-size:13px}
}
@container wallet (max-width:350px){
  .header-row{grid-template-columns:44px minmax(0,1fr) 40px;column-gap:8px}
  #menu{width:40px;min-width:40px;height:40px;min-height:40px}
  .ha-component-title{font-size:16px}
  .brand-logo{width:min(126px,42vw)}
}
`;

function kstClock(now = Date.now()) {
  const shifted = new Date(now + KST_OFFSET);
  return {
    shifted,
    day: shifted.getUTCDay(),
    seconds: shifted.getUTCHours() * 3600 + shifted.getUTCMinutes() * 60 + shifted.getUTCSeconds(),
  };
}

function inPublicationWindow(now = Date.now()) {
  const {day, seconds} = kstClock(now);
  return (day === 6 && seconds >= 20 * 3600 + 30 * 60)
    || (day === 0 && seconds <= 10 * 3600 + 30 * 60);
}

function msUntilPublicationWindow(now = Date.now()) {
  if (inPublicationWindow(now)) return 0;
  const {shifted, day, seconds} = kstClock(now);
  let days = (6 - day + 7) % 7;
  if (day === 6 && seconds < 20 * 3600 + 30 * 60) days = 0;
  else if (days === 0) days = 7;
  const target = Date.UTC(
    shifted.getUTCFullYear(), shifted.getUTCMonth(), shifted.getUTCDate() + days,
    20, 30, 0, 0,
  );
  return Math.max(1000, target - shifted.getTime());
}

const Panel = customElements.get(PANEL_TAG);
if (!Panel) throw new Error('lotto-ticket-panel controller did not register');

Panel.prototype._hasPendingFutureDraw = function () {
  const target = Number(this._targetRound);
  const result = Number(this._panelResultRound);
  return Number.isInteger(target) && target > 0
    && (!Number.isInteger(result) || result <= 0 || result < target);
};

Panel.prototype._smartSyncPolicy = function (now = Date.now()) {
  const status = this._panelResultStatus || 'waiting';
  if (UNSETTLED_RESULT_STATES.has(status)) {
    return {mode: 'poll', delay: PANEL_SYNC_INTERVAL, reason: 'official_recheck'};
  }
  if (this._hasPendingFutureDraw()) {
    if (inPublicationWindow(now)) {
      return {mode: 'poll', delay: PANEL_SYNC_INTERVAL, reason: 'draw_window'};
    }
    return {mode: 'wake', delay: msUntilPublicationWindow(now), reason: 'next_draw_window'};
  }
  return {mode: 'idle', delay: 0, reason: OFFICIAL_RESULT_STATES.has(status) ? 'official_done' : 'stable'};
};

Panel.prototype._renderSmartSyncStatus = function (now = Date.now(), policy = this._smartSyncPolicy(now)) {
  const node = this.node?.('sync-status');
  if (!node || !this._lastPanelSyncAt) return;
  const time = new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(this._lastPanelSyncAt));
  const status = this._panelResultStatus || 'waiting';
  let suffix = '';
  if (policy.mode === 'poll') {
    suffix = UNSETTLED_RESULT_STATES.has(status)
      ? '공식 대조 대기 · HA 상태 자동 동기화 중'
      : '추첨 결과 대기 · HA 상태 자동 동기화 중';
  } else if (OFFICIAL_RESULT_STATES.has(status)) {
    suffix = '공식 결과 확인 완료';
  } else if (status === 'waiting') {
    suffix = '추첨 결과 대기';
  } else {
    suffix = '동기화 완료';
  }
  node.textContent = `최근 동기화 ${time}${suffix ? ` · ${suffix}` : ''}`;
};

Panel.prototype._clearSmartSync = function () {
  clearTimeout(this._smartSyncTimer);
  this._smartSyncTimer = null;
};

Panel.prototype._scheduleSmartSync = function (now = Date.now()) {
  this._clearSmartSync();
  if (!this.isConnected || document.hidden || !this.node?.('entry')?.value) return;
  const policy = this._smartSyncPolicy(now);
  this._renderSmartSyncStatus(now, policy);
  if (policy.mode === 'idle') return;
  this._smartSyncTimer = setTimeout(() => {
    this._smartSyncTimer = null;
    void this._runSmartSync();
  }, policy.delay);
};

Panel.prototype._runSmartSync = async function () {
  if (!this.isConnected || document.hidden || !this.node?.('entry')?.value) return;
  if (this._busy) {
    this._smartSyncTimer = setTimeout(() => {
      this._smartSyncTimer = null;
      void this._runSmartSync();
    }, PANEL_RESUME_MIN_GAP);
    return;
  }
  const policy = this._smartSyncPolicy();
  if (policy.mode === 'idle' || policy.mode === 'wake') {
    this._scheduleSmartSync();
    return;
  }
  await this.operation(() => this.refreshStatus(), true);
  if (!this._smartSyncTimer) this._scheduleSmartSync();
};

Panel.prototype._resumePanelSync = function () {
  if (!this.isConnected || document.hidden || this._busy || !this.node?.('entry')?.value) return;
  const now = Date.now();
  if (now - (this._lastPanelSyncAt || 0) < PANEL_RESUME_MIN_GAP) {
    this._scheduleSmartSync(now);
    return;
  }
  void this.operation(() => this.refreshStatus(), true).then(() => {
    if (!this._smartSyncTimer) this._scheduleSmartSync();
  });
};

const baseStart = Panel.prototype._start;
Panel.prototype._start = function (...args) {
  const value = baseStart.apply(this, args);
  // v1.11.4 core creates a legacy 30-second interval. The entry module owns
  // synchronization now, so cancel it immediately on every HA property update.
  if (this._poll) {
    clearInterval(this._poll);
    this._poll = null;
  }
  return value;
};

Panel.prototype._onLottoConnected = function () {
  if (!this._smartVisibilityHandler) {
    this._smartVisibilityHandler = () => {
      if (!document.hidden) this._resumePanelSync();
    };
    this._smartFocusHandler = () => this._resumePanelSync();
    this._smartPageShowHandler = () => this._resumePanelSync();
    document.addEventListener('visibilitychange', this._smartVisibilityHandler);
    window.addEventListener('focus', this._smartFocusHandler);
    window.addEventListener('pageshow', this._smartPageShowHandler);
  }
};

Panel.prototype._onLottoDisconnected = function () {
  if (this._smartVisibilityHandler) {
    document.removeEventListener('visibilitychange', this._smartVisibilityHandler);
    window.removeEventListener('focus', this._smartFocusHandler);
    window.removeEventListener('pageshow', this._smartPageShowHandler);
    this._smartVisibilityHandler = null;
    this._smartFocusHandler = null;
    this._smartPageShowHandler = null;
  }
  this._clearSmartSync();
};

const baseUpdateResults = Panel.prototype.updateResults;
Panel.prototype.updateResults = function (data, ...args) {
  const value = baseUpdateResults.call(this, data, ...args);
  this._panelResultStatus = data?.result_verification?.status || 'waiting';
  this._panelResultRound = Number(data?.result_round) || null;
  this._lastPanelSyncAt = Date.now();
  this._renderSmartSyncStatus();
  this._scheduleSmartSync();
  return value;
};

const baseOperation = Panel.prototype.operation;
Panel.prototype.operation = async function (action, background = false) {
  const value = await baseOperation.call(this, action, background);
  if (background) {
    const status = this.node?.('sync-status');
    if (status?.textContent?.startsWith('자동 확인 실패')) {
      status.textContent = '자동 동기화 실패 · 다시 확인해 주세요';
    }
  }
  return value;
};

const baseRender = Panel.prototype.render;
Panel.prototype.render = function (...args) {
  const value = baseRender.apply(this, args);
  const root = this.shadowRoot;
  const row = root?.querySelector('.header-row');
  if (row && !row.querySelector('.ha-component-title')) {
    const title = document.createElement('span');
    title.className = 'ha-component-title';
    title.textContent = PANEL_NAME;
    title.setAttribute('aria-label', `컴포넌트 이름 ${PANEL_NAME}`);
    row.insertBefore(title, row.querySelector('#brand-home'));
  }
  if (root && !root.querySelector('style[data-lotto-two-tier-header]')) {
    const style = document.createElement('style');
    style.setAttribute('data-lotto-two-tier-header', '1.11.5');
    style.textContent = HEADER_STYLE;
    root.append(style);
  }
  const check = this.node?.('check');
  if (check) {
    check.onclick = () => this.operation(async () => {
      this.message('새 추첨 결과를 확인하고 있어요.');
      this.updateResults(await this.request('result_check'));
      await this.refreshStatus();
      this.message(OFFICIAL_RESULT_STATES.has(this._panelResultStatus)
        ? '공식 결과를 확인했어요.'
        : '확인했어요. 결과가 확정될 때까지만 필요한 시간에 자동 동기화합니다.');
    });
  }
  return value;
};



// Keep subscriptions independent of Saturday result polling.
import { installLiveSync } from './lotto-panel-live.js?v=2.1.1';
installLiveSync(Panel);
