/* UI entry point: keep the stable controller isolated and add the Home Assistant-style two-tier header. */
import './lotto-panel-core.js?v=1.11.4';

const PANEL_NAME = 'Lotto 6/45 Analysis';
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

const Panel = customElements.get('lotto-ticket-panel');
if (!Panel) throw new Error('lotto-ticket-panel controller did not register');

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
    style.setAttribute('data-lotto-two-tier-header', '1.11.4');
    style.textContent = HEADER_STYLE;
    root.append(style);
  }
  return value;
};
