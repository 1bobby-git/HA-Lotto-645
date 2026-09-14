/* Component-only design system.
 * Reference: HA-SmartThings_Web/bridge/src/server/status-page.ts (v1.8.52).
 * The HA host header, data controller and result-number colors are not restyled.
 * Card shadows follow the supplied shared design guide instead of a global reset.
 */
export const COMPONENT_STYLE = `
:host {
  --lotto-font: -apple-system, BlinkMacSystemFont, "Pretendard", "Noto Sans KR", "Noto Sans CJK KR", "Malgun Gothic", sans-serif;
  --lotto-radius-hero:18px;
  --lotto-radius-card:14px;
  --lotto-radius-control:10px;
  --lotto-radius-badge:6px;
  --lotto-shadow-card:0 8px 28px rgba(25,36,59,.06);
  font-family:var(--lotto-font);
  font-size:15px;
  line-height:1.65;
  text-rendering:optimizeLegibility;
}
:host([data-theme="dark"]) { --lotto-shadow-card:none; }
/* Keep the host-owned navigation palette separate from the white brand area. */
.app-header { background:#fff; border-bottom:1px solid #e9ecf1; }
.header-row, .main-tabs {
  --ink:#191f28; --muted:#667182; --line:#e9ecf1; --soft:#f1f3f6;
  --blue:#2563eb; --green:#147455; --field:#c2c9d3; --surface:#fff;
  color:#191f28;
}
.header-row {
  display:grid;
  grid-template-columns:minmax(0,1fr) auto auto auto auto;
  align-items:center;
  gap:0 12px;
  min-height:76px;
  padding-top:8px;
  padding-bottom:8px;
}
.header-label { display:none; }
.header-tools { display:contents; }
.brand-link, :host([data-theme="dark"]) .brand-link {
  grid-column:1; grid-row:1; justify-self:start;
  min-width:0; min-height:44px; padding:0;
  background:transparent; border:0; border-radius:0; box-shadow:none;
}
.brand-logo {
  width:auto; height:38px; aspect-ratio:auto;
  max-width:min(280px,44cqw); object-fit:contain; object-position:left center;
}
.brand-fallback { font-size:18px; font-weight:750; letter-spacing:-.03em; }
.connection {
  grid-column:2; grid-row:1; display:inline-flex; min-height:44px;
  align-items:center; gap:7px; color:#667182;
  font-size:13px; font-weight:700; white-space:nowrap;
}
.connection::before { width:7px; height:7px; border-radius:999px; }
.component-version {
  grid-column:3; grid-row:1; padding:4px 8px;
  border-radius:var(--lotto-radius-badge); background:#f1f3f6; color:#667182;
  font-size:12px; font-weight:400; white-space:nowrap;
  font-variant-numeric:tabular-nums;
}
.entry-field { grid-column:4; grid-row:1; width:180px; max-width:180px; }
.entry-field select { min-height:44px; font-size:13px; }
.header-tools .settings {
  grid-column:5; grid-row:1; justify-self:end; margin-left:0;
  display:inline-flex; align-items:center; gap:8px;
  min-width:44px; min-height:44px; padding:8px 12px;
  color:#667182; background:#fff; border:1px solid #e9ecf1;
  border-radius:var(--lotto-radius-control); font-size:13px; font-weight:700;
  white-space:nowrap; box-shadow:none;
}
.header-tools .settings:hover { color:#2563eb; border-color:#c2c9d3; }
.header-tools .settings .settings-copy { display:inline; }
.main-tabs { min-height:48px; gap:30px; align-items:end; overflow-x:auto; }
.main-tabs button {
  min-height:48px; padding:0; border:0; border-radius:0;
  color:#667182; font-size:14px; line-height:1.65; font-weight:700;
  background:transparent; box-shadow:none;
}
.main-tabs button[aria-selected="true"] { color:#191f28; font-weight:800; }
.main-tabs button[aria-selected="true"]::after {
  bottom:0; height:3px; border-radius:2px 2px 0 0; background:#191f28;
}
.main-tabs button:focus-visible { outline-offset:-3px; }
/* One text hierarchy for every screen, including the editor and empty states. */
main { padding-top:38px!important; padding-bottom:48px!important; }
h1 { font-size:clamp(28px,4cqw,38px); line-height:1.3; font-weight:780; letter-spacing:-.045em; word-break:keep-all; overflow-wrap:anywhere; }
h2 { font-size:22px; line-height:1.4; font-weight:760; letter-spacing:-.035em; }
h3 { font-size:19px; line-height:1.4; font-weight:760; letter-spacing:-.03em; }
.page-heading { align-items:end; gap:24px; margin-bottom:26px; }
.page-heading p { margin-top:10px; font-size:15px; line-height:1.65; max-width:720px; }
.kicker { margin-bottom:8px; color:var(--blue); font-size:12px; font-weight:800; letter-spacing:.12em; }
.section-heading { align-items:end; margin-bottom:14px; gap:20px; }
.section-heading h2, .review-block .section-heading h2 { font-size:22px; font-weight:760; }
.dashboard-grid { margin-top:34px; gap:28px; }
/* Keep the layout and purpose of the lottery wallet; share surface treatment. */
.draw-stage { padding:28px 28px 0; border-radius:var(--lotto-radius-hero); box-shadow:var(--lotto-shadow-card); }
.draw-stage h2 { font-size:32px; line-height:1.28; font-weight:780; letter-spacing:-.04em; }
.draw-kicker { margin-bottom:8px; font-size:12px; font-weight:750; }
.draw-details { margin:0 -28px; padding:0 28px; font-size:13px; }
.verification { font-size:12px; font-weight:700; border-radius:var(--lotto-radius-badge); }
.result-copy .caption { font-size:13px; }
.result-copy strong { font-size:15px; font-weight:700; }
.ticket-paper, .review-block { border-radius:var(--lotto-radius-card); box-shadow:var(--lotto-shadow-card); }
.import-promo { border-radius:var(--lotto-radius-card); padding:24px; margin-top:50px; }
.review-block { padding:24px; }
.paper-label { font-size:14px; font-weight:700; }
.paper-meta, .paper-bottom, .paper-bottom button, .small-print,
.quick-copy small, .wallet-description, .review-count, .review-note,
.review-footnote, .import-promo p, .footer, .empty,
.steps, .savedrounds, .game-feedback, .input-help, .sheet-privacy,
.game-field label, .game-label, .prize, .wallet-paper .prize {
  font-size:12px; line-height:1.65;
}
.quick-copy strong, .quick-link, .wallet-toolbar label, .wallet-toolbar select,
.wallet-actions button, .review-note, .review-footnote,
.choice-text small, .sheet-intro p, .address-import,
.draft-status, .editor-notice { font-size:13px; }
.quick-copy strong, .game-field label, .form-count strong { font-weight:700; }
.empty strong { font-size:17px; font-weight:750; }
.import-promo h3 { font-size:19px; font-weight:760; }
.footer { margin-top:28px; padding-top:18px; display:flex; flex-wrap:wrap; gap:8px 20px; }
.footer .sync { white-space:normal; overflow-wrap:anywhere; }
.review-note { line-height:1.8; }
th { font-size:12px; font-weight:700; }
td { font-size:13px; }
/* Touch controls are not reduced together with secondary text. Native #menu is excluded. */
main button, dialog button, input, select, textarea {
  min-height:44px; border-radius:var(--lotto-radius-control); font-weight:700;
}
input, select, textarea { font-weight:400; }
main button, dialog button { font-size:14px; }
.page-heading .primary, .sheet-actions .primary { min-height:50px; padding:0 18px; font-size:15px; font-weight:760; box-shadow:none; }
.draw-foot button { min-height:44px; font-size:13px; padding:8px 12px; }
.section-heading button, .paper-bottom button, .import-promo button { min-height:44px; font-size:13px; }
.quick-link { border-radius:0; }
.prize, .review-count, .slot-tag { border-radius:var(--lotto-radius-badge); }
.sheet-head .icon-only { width:44px; height:44px; min-height:44px; border-radius:var(--lotto-radius-control); }
.sheet-head h2 { font-size:22px; }
.import-choice { border-radius:var(--lotto-radius-card); }
.choice-text strong { font-size:15px; font-weight:750; }
.notice, .editor-notice, .camera-view { border-radius:var(--lotto-radius-control); }
@container wallet (min-width:871px) {
  .header-row:has(.entry-field[hidden]) { grid-template-columns:minmax(0,1fr) auto auto auto; }
  .header-row:has(.entry-field[hidden]) .settings { grid-column:4; }
}
@container wallet (max-width:870px) {
  /* A docked HA sidebar can leave only 615px in an 871px browser. */
  .header-row { grid-template-columns:minmax(0,1fr) auto auto auto; }
  .header-tools .settings { grid-column:4; }
  .entry-field { grid-column:1 / -1; grid-row:2; order:initial; width:100%; max-width:none; padding:4px 0 8px; }
  .entry-field select { width:100%; max-width:none; }
  .draw-numbers { --ball-size:clamp(38px,calc((100cqw - 200px)/7),58px); gap:8px; }
  .bonus-group { gap:8px; }
  .dashboard-grid { gap:0; }
  .import-promo { margin-top:24px; }
}
@container wallet (max-width:560px) {
  .header-row { min-height:68px; grid-template-columns:minmax(0,1fr) auto 44px; gap:0 10px; }
  .brand-logo { height:32px; max-width:min(52cqw,100%); }
  .connection { font-size:12px; }
  .component-version { display:none; }
  .header-tools .settings { grid-column:3; width:44px; padding:10px; }
  .header-tools .settings .settings-copy { display:none; }
  .entry-field, .entry-field select { width:100%; max-width:none; }
  .main-tabs { gap:24px; }
  main { padding-top:28px!important; padding-bottom:36px!important; }
  .page-heading { margin-bottom:22px; gap:18px; align-items:flex-start; }
  .page-heading .primary { min-height:46px; font-size:14px; }
  .draw-stage { padding:22px 20px 0; border-radius:16px; }
  .draw-stage h2 { font-size:26px; }
  .draw-kicker { margin:0; }
  .draw-details { margin:0 -20px; padding:0 20px; }
  .draw-numbers { --ball-size:clamp(26px,calc((100cqw - 142px)/7),45px); gap:6px; }
  .bonus-group { gap:6px; }
  .draw-foot { flex-wrap:wrap; gap:12px; }
  .result-copy { flex:1 1 145px; }
  .result-copy strong { font-size:14px; }
  .draw-foot button { margin-left:auto; }
  .dashboard-grid { margin-top:28px; }
  .section-heading h2, .review-block .section-heading h2 { font-size:21px; }
  .section-heading { gap:12px; }
  .paper-label { font-size:13px; }
  .paper-bottom { flex-wrap:wrap; gap:4px 12px; }
  .paper-bottom button { margin-left:auto; }
  .paper-meta { white-space:nowrap; }
  .import-promo { padding:22px 20px; }
  .review-block { padding:20px 16px; }
  .mobile-table td { grid-template-columns:76px minmax(0,1fr); font-size:13px; }
  .mobile-table td::before { font-size:12px; }
  .footer { display:flex; font-size:12px; }
  .footer .sync { margin-top:0; }
  .wallet-toolbar { flex-wrap:wrap; }
  .wallet-paper .game-label { font-size:12px; }
  .wallet-paper .ticket-row, .ticket-row { gap:6px; }
  .wallet-paper .prize, .prize { font-size:12px; padding:3px 5px; }
}
@container wallet (max-width:350px) {
  .header-row { gap:0 8px; }
  .brand-logo { height:30px; }
  .draw-numbers, .bonus-group { gap:4px; }
  .ticket-row, .wallet-paper .ticket-row { gap:5px; }
}
@media (forced-colors:active) {
  .component-version, .header-tools .settings { border:1px solid CanvasText; }
  .main-tabs button[aria-selected="true"] { outline:2px solid Highlight; outline-offset:-3px; }
}
`;

export function applyComponentDesign(panel) {
  const root = panel.shadowRoot;
  if (!root) return;
  // One synchronous module: no remote fonts, delayed stylesheet or extra data calls.
  if (!root.querySelector('style[data-lotto-component-design]')) {
    const style = document.createElement('style');
    style.dataset.lottoComponentDesign = '1.14.0';
    style.textContent = COMPONENT_STYLE;
    root.append(style);
  }
  const tools = root.querySelector('.header-tools');
  if (!tools) return;
  let version = tools.querySelector('.component-version');
  if (!version) {
    version = document.createElement('span');
    version.className = 'component-version';
    tools.insertBefore(version, tools.querySelector('.entry-field'));
  }
  const value = String(panel._panel?.config?.version || '1.14.0');
  version.textContent = `v${value}`;
  version.setAttribute('aria-label', `컴포넌트 버전 ${value}`);
  const settings = tools.querySelector('.settings');
  if (settings && !settings.querySelector('.settings-copy')) {
    const text = document.createElement('span');
    text.className = 'settings-copy';
    text.textContent = '설정';
    text.setAttribute('aria-hidden', 'true');
    settings.append(text);
  }
}
