/* Production entry: component presentation with HA-owned narrow-state decisions. */
import './lotto-panel.js?v=2.3.2';
import { PANEL_TAG } from './lotto-panel-core.js?v=2.3.2';
import { applyComponentDesign } from './lotto-panel-design.js?v=2.3.2';
import { applyPanelTools } from './lotto-panel-tools.js?v=2.3.2';


const PANEL_NAME = 'Lotto 6/45 Analysis';
const Panel = customElements.get(PANEL_TAG);
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

/* Colors sampled directly from the two user-supplied Donghaeng Lottery result captures.
   !important is intentional: these five colors are the canonical ball palette for every
   rendered Lotto number and must win over legacy view/design styles after hot updates. */
const LOTTO_BALL_AND_COUNTDOWN_STYLE = `
.draw-numbers .ball[data-band],
.ticket-balls .ball[data-band]{
  color:#fff!important;
  border:0!important;
  background-image:none!important;
  box-shadow:none!important;
  text-shadow:0 1px 1px rgba(0,0,0,.16)!important;
}
.draw-numbers .ball[data-band="1"],.ticket-balls .ball[data-band="1"]{background:#e08f00!important}
.draw-numbers .ball[data-band="2"],.ticket-balls .ball[data-band="2"]{background:#0063cc!important}
.draw-numbers .ball[data-band="3"],.ticket-balls .ball[data-band="3"]{background:#d8314f!important}
.draw-numbers .ball[data-band="4"],.ticket-balls .ball[data-band="4"]{background:#6d7381!important}
.draw-numbers .ball[data-band="5"],.ticket-balls .ball[data-band="5"]{background:#2c9e44!important}
.ticket-balls.result-balls[data-evaluated="true"] .ball[data-hit="main"],
.ticket-balls.result-balls[data-evaluated="true"] .ball[data-hit="bonus"]{
  outline:none!important;
  box-shadow:none!important;
  transform:none!important;
  filter:none!important;
  opacity:1!important;
}
.ticket-balls.result-balls[data-evaluated="true"] .ball[data-hit="miss"]{
  background:#e5e7eb!important;
  color:#4b5563!important;
  border:1px solid #d1d5db!important;
  text-shadow:none!important;
  outline:none!important;
  box-shadow:none!important;
  transform:none!important;
  filter:none!important;
  opacity:1!important;
}
:host([data-theme="dark"]) .ticket-balls.result-balls[data-evaluated="true"] .ball[data-hit="miss"]{
  background:#374151!important;
  color:#d1d5db!important;
  border-color:#4b5563!important;
}
lotto-panel-tools-v2-3-2{display:block!important;height:0!important;min-height:0!important;margin:0!important;overflow:visible!important}
@media(forced-colors:active){
  .draw-numbers .ball[data-band],.ticket-balls .ball[data-band]{
    background:Canvas!important;
    color:CanvasText!important;
    border:1px solid CanvasText!important;
    text-shadow:none!important;
  }
}
`;

function removeLegacyHeroCountdown(panel) {
  panel.shadowRoot?.querySelector('.hero-draw-countdown')?.remove();
}

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
    let hostStyle = root.querySelector('style[data-lotto-ha-host-header]');
    if (!hostStyle) {
      hostStyle = document.createElement('style');
      root.append(hostStyle);
    }
    hostStyle.setAttribute('data-lotto-ha-host-header', '2.3.2');
    hostStyle.textContent = HA_HOST_HEADER_STYLE;
  }
  removeLegacyHeroCountdown(this);
  applyComponentDesign(this);
  applyPanelTools(this);
  if (root) {
    let ballStyle = root.querySelector('style[data-lotto-official-ball-colors]');
    if (!ballStyle) {
      ballStyle = document.createElement('style');
      root.append(ballStyle);
    }
    /* Refresh stale style nodes instead of accepting their old text. */
    ballStyle.setAttribute('data-lotto-official-ball-colors', '2.3.2');
    ballStyle.textContent = LOTTO_BALL_AND_COUNTDOWN_STYLE;
  }
  const tools = root?.querySelector('lotto-panel-tools-v2-3-2');
  if (tools) {
    tools.style.height = '0';
    tools.style.minHeight = '0';
    tools.style.margin = '0';
    tools.style.overflow = 'visible';
    const oldSection = tools.shadowRoot?.querySelector('.countdown');
    if (oldSection) oldSection.hidden = true;
    removeLegacyHeroCountdown(this);
  }
  this._syncHaHostHeader?.();
  return value;
};
