/* UI entry point: two-tier Home Assistant header with manual-only page synchronization. */
import { PANEL_TAG } from './lotto-panel-core.js?v=2.4.23';

const PANEL_NAME = 'Lotto 6/45 Analysis';
const OFFICIAL_RESULT_STATES = new Set(['official_history', 'official_confirmed', 'official_corrected']);

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

const Panel = customElements.get(PANEL_TAG);
if (!Panel) throw new Error('lotto-ticket-panel controller did not register');

const baseUpdateResults = Panel.prototype.updateResults;
Panel.prototype.updateResults = function (data, ...args) {
  const value = baseUpdateResults.call(this, data, ...args);
  this._panelResultStatus = data?.result_verification?.status || 'waiting';
  const node = this.node?.('sync-status');
  if (node) {
    const time = new Intl.DateTimeFormat('ko-KR', {
      hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(new Date());
    node.textContent = `최근 확인 ${time} · 화면 자동 갱신 꺼짐 · 결과 확인 버튼으로 갱신`;
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
        : '확인했어요. 화면은 자동 갱신하지 않습니다. 새 결과는 결과 확인 버튼으로 확인하세요.');
    });
  }
  return value;
};



// Keep announcement delivery independent of manual page refresh.
import { installLiveSync } from './lotto-panel-live.js?v=2.4.23';
installLiveSync(Panel);
