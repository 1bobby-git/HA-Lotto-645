/* Production entry: component presentation with HA-owned narrow-state decisions. */
import './lotto-panel.js?v=1.11.5';
import { applyComponentDesign } from './lotto-panel-design.js?v=1.11.7';
import { applyPanelTools } from './lotto-panel-tools.js?v=1.11.9';

const PANEL_NAME = 'Lotto 6/45 Analysis';
const Panel = customElements.get('lotto-ticket-panel');
if (!Panel) throw new Error('lotto-ticket-panel controller did not register');

const HA_HOST_HEADER_STYLE = `
/* HA supplies narrow; never infer its breakpoint from the component width. */
.app-header{padding-top:var(--lotto-safe-top)}
:host([data-ha-host-header]) .app-header{padding-top:0}
.ha-host-header{display:none}
:host([data-ha-host-header]) .ha-host-header{
  display:flex;
  align-items:center;
  box-sizing:border-box;
  width:100%;
  height:calc(40px + var(--lotto-safe-top,0px));
  padding:var(--lotto-safe-top,0px)
    calc(16px + var(--lotto-viewport-right,0px)) 0
    calc(16px + var(--lotto-viewport-left,0px));
  pointer-events:none;
  background:var(--app-header-background-color,var(--surface));
  color:var(--app-header-text-color,var(--ink));
  border-bottom:var(--app-header-border-bottom,1px solid var(--line));
  font-family:var(--primary-font-family,Roboto,sans-serif);
  font-size:var(--ha-font-size-l,14px);
  font-weight:var(--ha-font-weight-normal,400);
  line-height:var(--ha-line-height-condensed,1.2);
}
.ha-host-header #menu{
  width:40px;
  min-width:40px;
  height:40px;
  min-height:40px;
  padding:10px;
  border:0;
  border-radius:0;
  background:transparent;
  color:var(--sidebar-icon-color,var(--ink));
  pointer-events:auto;
  flex:none;
}
.ha-host-header #menu:hover:not(:disabled){background:transparent;filter:none}
.ha-host-title{
  min-width:0;
  margin-inline-start:var(--ha-space-6,24px);
  flex:1;
  overflow:hidden;
  white-space:nowrap;
  text-overflow:ellipsis;
}
.header-row{position:relative}
@container wallet (max-width:560px){
  .ha-host-title{margin-inline-start:var(--ha-space-2,8px)}
}
`;

/* Donghaeng Lottery Lotto 6/45 number-band palette.
   Apply it to every rendered lottery ball: recent draw, saved tickets and review rows. */
const OFFICIAL_BALL_STYLE = `
.draw-numbers .ball[data-band],
.ticket-balls .ball[data-band]{
  color:#fff;
  border:0;
  background-image:none;
  box-shadow:none;
}
.draw-numbers .ball[data-band="1"],.ticket-balls .ball[data-band="1"]{
  background:#fbc400;
  text-shadow:0 0 3px rgba(73,57,0,.8);
}
.draw-numbers .ball[data-band="2"],.ticket-balls .ball[data-band="2"]{
  background:#69c8f2;
  text-shadow:0 0 3px rgba(0,49,70,.8);
}
.draw-numbers .ball[data-band="3"],.ticket-balls .ball[data-band="3"]{
  background:#ff7272;
  text-shadow:0 0 3px rgba(64,0,0,.8);
}
.draw-numbers .ball[data-band="4"],.ticket-balls .ball[data-band="4"]{
  background:#aaa;
  text-shadow:0 0 3px rgba(61,61,61,.8);
}
.draw-numbers .ball[data-band="5"],.ticket-balls .ball[data-band="5"]{
  background:#b0d840;
  text-shadow:0 0 3px rgba(41,56,0,.8);
}
@media(forced-colors:active){
  .draw-numbers .ball[data-band],.ticket-balls .ball[data-band]{
    background:Canvas;
    color:CanvasText;
    border:1px solid CanvasText;
    text-shadow:none;
  }
}
`;

Panel.prototype._syncHaHostHeader = function () {
  const narrow = Boolean(this._haNarrow);
  const visible = !this._hass?.kioskMode
    && (narrow || this._hass?.dockedSidebar === 'always_hidden');
  this.toggleAttribute('data-ha-narrow', narrow);
  this.toggleAttribute('data-ha-host-header', visible);
};

const previousNarrow = Object.getOwnPropertyDescriptor(Panel.prototype, 'narrow');
Object.defineProperty(Panel.prototype, 'narrow', {
  configurable: true,
  enumerable: previousNarrow?.enumerable ?? false,
  get() {
    return previousNarrow?.get ? previousNarrow.get.call(this) : Boolean(this._haNarrow);
  },
  set(value) {
    if (previousNarrow?.set) previousNarrow.set.call(this, value);
    this._haNarrow = Boolean(value);
    this._syncHaHostHeader?.();
  },
});

const previousHass = Object.getOwnPropertyDescriptor(Panel.prototype, 'hass');
if (previousHass?.set) {
  Object.defineProperty(Panel.prototype, 'hass', {
    configurable: true,
    enumerable: previousHass.enumerable,
    get: previousHass.get,
    set(value) {
      previousHass.set.call(this, value);
      this._syncHaHostHeader?.();
    },
  });
}

const previousRender = Panel.prototype.render;
Panel.prototype.render = function (...args) {
  const value = previousRender.apply(this, args);
  const root = this.shadowRoot;
  const appHeader = root?.querySelector('.app-header');
  const componentRow = root?.querySelector('.header-row');
  root?.querySelector('style[data-lotto-two-tier-header]')?.remove();
  root?.querySelector('.ha-component-title')?.remove();

  if (root && appHeader && componentRow) {
    let hostHeader = root.querySelector('.ha-host-header');
    if (!hostHeader) {
      hostHeader = document.createElement('div');
      hostHeader.className = 'ha-host-header';
      hostHeader.setAttribute('role', 'banner');
      hostHeader.setAttribute('aria-label', `${PANEL_NAME} Home Assistant 헤더`);
      const menu = this.node?.('menu');
      if (menu) hostHeader.append(menu);
      const title = document.createElement('div');
      title.className = 'ha-host-title';
      title.textContent = PANEL_NAME;
      hostHeader.append(title);
      appHeader.insertBefore(hostHeader, appHeader.firstChild);
    }
    if (!root.querySelector('style[data-lotto-ha-host-header]')) {
      const style = document.createElement('style');
      style.setAttribute('data-lotto-ha-host-header', '1.11.10');
      style.textContent = HA_HOST_HEADER_STYLE;
      root.append(style);
    }
  }
  applyComponentDesign(this);
  applyPanelTools(this);
  if (root && !root.querySelector('style[data-lotto-official-ball-colors]')) {
    const style = document.createElement('style');
    style.setAttribute('data-lotto-official-ball-colors', '1.11.10');
    style.textContent = OFFICIAL_BALL_STYLE;
    root.append(style);
  }
  this._syncHaHostHeader?.();
  return value;
};
