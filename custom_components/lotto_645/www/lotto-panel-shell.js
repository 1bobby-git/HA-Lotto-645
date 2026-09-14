/* Production entry: preserve the panel UI and follow Home Assistant's own narrow-state header behavior. */
import './lotto-panel.js?v=1.11.5';

const PANEL_NAME = 'Lotto 6/45 Analysis';
const Panel = customElements.get('lotto-ticket-panel');
if (!Panel) throw new Error('lotto-ticket-panel controller did not register');

const HA_HOST_HEADER_STYLE = `
/* The custom panel never guesses Home Assistant's breakpoint. The host supplies
   the narrow property; this row follows the same visibility condition used by
   Home Assistant's ha-panel-app. */
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
/* Once the menu moves to the HA host row, the component header is again only
   brand + component status/actions + its own tabs. */
.header-row{position:relative}
@container wallet (max-width:560px){
  .ha-host-title{margin-inline-start:var(--ha-space-2,8px)}
}
`;

Panel.prototype._syncHaHostHeader = function () {
  const narrow = Boolean(this._haNarrow);
  const visible = !this._hass?.kioskMode
    && (narrow || this._hass?.dockedSidebar === 'always_hidden');
  this.toggleAttribute('data-ha-narrow', narrow);
  this.toggleAttribute('data-ha-host-header', visible);
};

// ha-panel-custom supplies `narrow`; do not derive it from window or container width.
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

// Docked-sidebar/kiosk state can change without `narrow` changing.
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

  // v1.11.4/1.11.5 inserted a permanent imitation first row. Remove it on
  // every render before establishing the host-driven narrow row.
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
      style.setAttribute('data-lotto-ha-host-header', '1.11.6');
      style.textContent = HA_HOST_HEADER_STYLE;
      root.append(style);
    }
  }

  this._syncHaHostHeader?.();
  return value;
};
