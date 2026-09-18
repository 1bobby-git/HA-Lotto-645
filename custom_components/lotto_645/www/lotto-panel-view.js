/* Wallet redesign. Presentation only; no network, storage, or recommendation logic. */
const svg = body => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
export const icons = {
  menu: svg('<path d="M4 7h16M4 12h16M4 17h16"/>'),
  plus: svg('<path d="M12 5v14M5 12h14"/>'),
  arrow: svg('<path d="m9 5 7 7-7 7"/>'),
  back: svg('<path d="m14 6-6 6 6 6"/>'),
  close: svg('<path d="m6 6 12 12M6 18 18 6"/>'),
  scan: svg('<path d="M8 3H4a1 1 0 0 0-1 1v4m13-5h4a1 1 0 0 1 1 1v4M3 16v4a1 1 0 0 0 1 1h4m8 0h4a1 1 0 0 0 1-1-1v-4M3 12h18"/><path d="M8 7h2v2H8zm6 8h2v2h-2z"/>'),
  photo: svg('<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8" cy="8" r="1.3"/><path d="m3 16 5-5 4 4 3-3 6 6"/>'),
  edit: svg('<path d="m15 5 4 4M4 20l5-1L20 8a2.8 2.8 0 0 0-4-4L5 15l-1 5Z"/>'),
  refresh: svg('<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 6a8 8 0 0 1 13.2 3M4.7 15A8 8 0 0 0 18 18"/>'),
  settings: svg('<path d="m9 3-.6 2.2-2 .9-2.1-.7-2 3.4 1.6 1.6V13l-1.6 1.6 2 3.4 2.1-.7 2 .9L9 21h4l.6-2.8 2-.9 2.1.7 2-3.4-1.6-1.6v-2.6l1.6-1.6-2-3.4-2.1.7-2-.9L13 3H9Z"/><circle cx="11" cy="12" r="3"/>'),
  lock: svg('<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>'),
  ticket: svg('<path d="M3 5h18v5a2 2 0 0 0 0 4v5H3v-5a2 2 0 0 0 0-4V5Z"/><path d="M15 5v2m0 3v2m0 3v2m0 2v0"/>'),
  chart: svg('<path d="M4 4v16h17M8 15v-4m5 4V7m5 8v-6"/>'),
  check: svg('<path d="m5 12 4 4L19 6"/>'),
};

export const panelTemplate = `<style>
:host {
  /* handle_safe_area=true: this panel owns the insets. HA values (including
     an explicit zero) take precedence over the browser fallback. Never add both. */
  --lotto-safe-top:var(--safe-area-inset-top,env(safe-area-inset-top,0px));
  --lotto-safe-bottom:var(--safe-area-inset-bottom,env(safe-area-inset-bottom,0px));
  --lotto-viewport-left:var(--safe-area-inset-left,env(safe-area-inset-left,0px));
  --lotto-viewport-right:var(--safe-area-inset-right,env(safe-area-inset-right,0px));
  --lotto-safe-left:var(--safe-area-content-inset-left,var(--lotto-viewport-left));
  --lotto-safe-right:var(--safe-area-content-inset-right,var(--lotto-viewport-right));
  --bg:#f7f8fa; --surface:#fff; --ink:#191f28; --muted:#667182; --line:#e9ecf1;
  --soft:#f1f3f6; --blue:#2563eb; --blue-soft:#edf3ff; --green:#147455;
  --green-soft:#e9f6ef; --danger:#b4233d; --danger-soft:#fff0f2; --field:#c2c9d3;
  --shadow:0 8px 32px #19243b05; --dim:#677386;
  display:block; height:100%; min-height:100%; overflow:auto; color:var(--ink);
  background:var(--bg); font:15px/1.65 -apple-system,BlinkMacSystemFont,"Pretendard","Noto Sans CJK KR","Malgun Gothic",sans-serif;
  -webkit-font-smoothing:antialiased; container:wallet / inline-size; color-scheme:light;
}
:host([data-theme="dark"]) {
  --bg:#11151c; --surface:#1b222c; --ink:#f1f4fa; --muted:#afbacb; --line:#303b4b;
  --soft:#252e3c; --blue:#91b6ff; --blue-soft:#233b61; --green:#89d8b5;
  --green-soft:#1c3b31; --danger:#ffacb9; --danger-soft:#432936; --field:#69778c;
  --shadow:none; --dim:#b4c0d3; color-scheme:dark;
}
:host([data-editor-open]){overflow:hidden}
*,*::before,*::after{box-sizing:border-box} [hidden]{display:none!important}
h1,h2,h3,p{margin:0} h1,h2,h3{line-height:1.35;letter-spacing:-.045em}
h1{font-size:38px;font-weight:750} h2{font-size:23px;font-weight:720} h3{font-size:18px;font-weight:700}
a{color:var(--blue);text-underline-offset:4px} button,input,select,textarea{font:inherit}
button,a,input,select,textarea,summary{-webkit-tap-highlight-color:transparent}
button{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:10px 16px;border:0;border-radius:12px;background:var(--soft);color:var(--ink);font-weight:650;line-height:1.45;cursor:pointer;transition:background .15s,transform .15s}
button:hover:not(:disabled){filter:brightness(.97)} button:active:not(:disabled){transform:translateY(1px)}
button:disabled{opacity:.5;cursor:wait} button.primary{background:#2563eb;color:#fff;box-shadow:0 4px 12px #2563eb15}
button.ghost{background:transparent} button.soft-blue{color:var(--blue);background:var(--blue-soft)}
button.danger{background:transparent;color:var(--danger)} button.icon-only{width:44px;padding:10px;flex:none}
svg{width:20px;height:20px;flex:none} :focus-visible{outline:3px solid var(--blue);outline-offset:4px}
.shell{min-height:100%;padding-bottom:max(20px,var(--lotto-safe-bottom))} .wrap{--page-gutter:40px;max-width:1248px;margin:0 auto;padding:0 max(var(--page-gutter),var(--lotto-safe-right)) 0 max(var(--page-gutter),var(--lotto-safe-left))}
.app-header{padding-top:var(--lotto-safe-top);background:var(--surface);border-bottom:1px solid var(--line)}
.header-row{display:flex;align-items:center;min-height:94px;gap:14px}
.brand-link{display:flex;align-items:center;text-decoration:none;padding:0;min-height:52px;background:transparent}
.brand-logo{display:block;width:166px;height:auto;aspect-ratio:512/170;object-fit:contain}
.brand-fallback{font-size:21px;font-weight:800;letter-spacing:-.7px}
:host([data-theme="dark"]) .brand-link{background:#fff;border-radius:12px;padding:2px 9px}
.header-label{font-size:12px;letter-spacing:.03em;color:var(--muted);padding-left:19px;margin-left:6px;border-left:1px solid var(--line)}
.header-tools{display:flex;align-items:center;gap:14px;margin-left:auto}
.settings{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px;color:var(--muted);border-radius:12px;text-decoration:none}
.connection{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--muted)}
.connection::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--field)}
.connection[data-online="true"]::before{background:var(--green)} .entry-field{max-width:200px}
.entry-field select{font-size:12px;min-height:40px;padding:8px 28px 8px 12px}
.main-tabs{display:flex;gap:32px;min-height:53px}
.main-tabs button{position:relative;background:none;padding:12px 2px 16px;border-radius:0;color:var(--muted);font-size:15px;font-weight:600;white-space:nowrap}
.main-tabs button[aria-selected="true"]{color:var(--ink);font-weight:750}
.main-tabs button[aria-selected="true"]::after{content:'';position:absolute;bottom:-1px;left:0;right:0;height:3px;background:var(--ink);border-radius:3px 3px 0 0}
main{padding-top:40px!important} .screen{outline:0}.page-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:30px}
.page-heading p{color:var(--muted);margin-top:10px;font-size:14px}.page-heading .primary{min-height:50px;padding:13px 22px;white-space:nowrap}
.kicker{font-size:11px;letter-spacing:.13em;color:var(--muted);font-weight:650;margin-bottom:11px}
/* The requested white result card has its own palette in both HA themes.
   Keep these tokens local: wallet/review surfaces and number-ball colors are unchanged. */
.draw-stage{
  --draw-bg:#fff; --draw-ink:#191f28; --draw-muted:#526073; --draw-line:#e2e7ef;
  --draw-soft:#f7f8fa; --draw-accent:#245edb; --draw-action-bg:#edf3ff;
  --draw-action-hover:#e0eaff; --draw-action-border:#b3c7f1;
  --draw-positive:#11684c; --draw-positive-bg:#eaf7f0;
  --draw-warning:#865400; --draw-warning-bg:#fff4d6;
  --draw-danger:#a51d35; --draw-danger-bg:#fff0f2;
  overflow:hidden;position:relative;border:1px solid var(--draw-line);border-radius:24px;
  background:var(--draw-bg);color:var(--draw-ink);color-scheme:light;
  padding:32px 36px 0;box-shadow:0 8px 28px #19243b06;
}
.draw-main{display:grid;grid-template-columns:205px minmax(0,1fr);gap:30px;align-items:center;min-height:135px}
.draw-kicker{color:var(--draw-muted);font-size:12px;margin-bottom:9px}.draw-stage h2{font-size:32px;font-weight:750;letter-spacing:-.035em}
.verification{display:inline-flex;align-items:center;gap:5px;max-width:100%;font-size:12px;line-height:1.6;color:var(--draw-positive);background:var(--draw-positive-bg);border-radius:8px;padding:5px 9px;margin-top:11px;font-weight:600}
.verification::before{content:'✓';font-weight:800}.verification[data-state="pending"]{color:var(--draw-warning);background:var(--draw-warning-bg)}.verification[data-state="pending"]::before{content:'◷'}
.verification[data-state="conflict"]{color:var(--draw-danger);background:var(--draw-danger-bg)}.verification[data-state="conflict"]::before{content:'!'}
.draw-numbers{--ball-size:60px;display:flex;align-items:center;justify-content:flex-end;gap:18px;min-height:110px;font-size:15px;color:var(--draw-muted)}
.ball{display:inline-flex;align-items:center;justify-content:center;flex:none;position:relative;width:var(--ball-size,34px);height:var(--ball-size,34px);border-radius:50%;font-weight:750;font-variant-numeric:tabular-nums;line-height:1;background:var(--soft);color:var(--ink)}
/* Flat number balls: colors sampled from the user-provided result screenshot.
   Scope to recent draw results; wallet/review number chips keep their own style. */
.draw-numbers .ball{font-size:24px;font-weight:700;color:#fff;background:#8c8c8c;box-shadow:none;border:0}
.draw-numbers .ball[data-band="1"]{background:#cd9234}
.draw-numbers .ball[data-band="2"]{background:#3e63c5}
.draw-numbers .ball[data-band="3"]{background:#bd4152}
.draw-numbers .ball[data-band="4"]{background:#8c8c8c}
.draw-numbers .ball[data-band="5"]{background:#5a9b50}
.bonus-group{display:inline-flex;align-items:center;gap:18px;margin-left:0}.bonus-label{position:relative;display:flex;flex:none;align-items:center;justify-content:center}
.bonus-caption{position:absolute;top:calc(100% + 10px);color:var(--draw-muted);font-size:12px;white-space:nowrap;font-weight:400}.plus{font-size:24px;font-weight:700;color:var(--draw-muted)}
.draw-foot{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:21px;padding:19px 0;border-top:1px solid var(--draw-line);min-height:76px}
.result-copy{display:flex;align-items:center;gap:13px;flex-wrap:wrap}.result-copy .caption{font-size:12px;color:var(--draw-muted)}.result-copy strong{font-size:14px;font-weight:650;color:var(--draw-ink)}
.draw-foot button{background:var(--draw-action-bg);color:var(--draw-accent);font-size:12px;min-height:44px;padding:8px 12px;border:1px solid var(--draw-action-border);white-space:nowrap}.draw-foot button:hover:not(:disabled){background:var(--draw-action-hover);filter:none}.draw-foot button svg{width:15px;height:15px}
.draw-stage :focus-visible{outline-color:var(--draw-accent)}.draw-details{background:var(--draw-soft);margin:0 -36px;padding:0 36px;border-top:1px solid var(--draw-line);font-size:12px;color:var(--draw-muted)}
.draw-details summary{color:var(--draw-ink);min-height:44px;align-content:center;cursor:pointer;list-style-position:inside}.draw-details p{padding:0 0 16px;max-width:870px;line-height:1.9}.draw-details a{color:var(--draw-accent);margin-right:14px;display:inline-block;min-height:32px}
/* Wallet: paper-like number rows, with registration moved into an on-demand sheet. */
.current-formulas{margin-top:24px}.dashboard-grid{display:grid;grid-template-columns:minmax(0,1fr) 304px;gap:32px;margin-top:36px;align-items:start}
.section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}.section-heading h2{font-size:21px}.section-heading button{font-size:12px;color:var(--muted);padding:6px 0 6px 10px;background:none;min-height:36px}.section-heading svg{width:15px;height:15px}
.ticket-paper{background:var(--surface);border:1px solid var(--line);border-radius:19px;box-shadow:var(--shadow);overflow:hidden}
.paper-top{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:19px 24px;border-bottom:1px dashed var(--field)}
.paper-label{display:flex;align-items:center;gap:9px;font-size:14px;font-weight:650}.paper-label svg{color:var(--muted);width:18px;height:18px}.paper-meta{font-size:11px;color:var(--muted)}
.ticket-list{padding:0 24px}.ticket-row{display:grid;grid-template-columns:26px minmax(0,1fr) auto;gap:14px;align-items:center;min-height:76px;border-bottom:1px solid var(--line)}.ticket-row:last-child{border:0}
.game-label{font-size:12px;color:var(--muted);font-weight:600}.ticket-balls{display:flex;gap:9px;flex-wrap:wrap;--ball-size:33px}
.ticket-balls .ball{font-size:13px;background:transparent;border:1px solid var(--line);color:var(--ink)}
.ticket-status{display:flex;align-items:center;justify-content:flex-end;gap:6px;flex-wrap:wrap}
.prize,.match-badge{font-size:11px;white-space:nowrap;border-radius:6px;padding:4px 8px}
.prize{color:var(--muted);background:var(--soft)}
.prize[data-purchase-match="true"],.match-badge{background:var(--blue-soft);color:var(--blue);font-weight:700}
.prize[data-winning="true"]{background:var(--green-soft);color:var(--green);font-weight:700}
.paper-bottom{display:flex;justify-content:space-between;align-items:center;gap:12px;background:var(--surface);padding:13px 24px;border-top:1px solid var(--line);font-size:11px;color:var(--muted)}
.paper-bottom button{flex:none;white-space:nowrap;font-size:12px;min-height:34px;padding:4px 0 4px 10px;background:transparent;color:var(--blue)}
.empty{padding:38px 18px;text-align:center;color:var(--muted);font-size:12px}.empty svg{width:32px;height:32px;margin-bottom:10px;color:var(--muted)}.empty strong{display:block;color:var(--ink);font-size:15px;margin:3px 0 8px}.empty p{line-height:1.9}
.import-promo{background:var(--blue-soft);border-radius:19px;padding:26px 26px 20px;position:relative;overflow:hidden;min-height:288px;margin-top:53px}
.import-promo h3{font-size:20px;line-height:1.55;position:relative;z-index:1}.import-promo p{font-size:12px;color:var(--muted);margin-top:9px;position:relative;z-index:1}
.import-promo button{font-size:13px;margin-top:18px;color:var(--blue);padding:9px 0;background:transparent;position:relative;z-index:1}
.ticket-art{position:absolute;right:-21px;bottom:-26px;width:165px;height:125px;background:var(--surface);border:1px solid var(--line);border-radius:14px;transform:rotate(-17deg);box-shadow:-8px 8px 24px #3a5fa015;pointer-events:none}
.art-head{padding:14px 14px 8px;font-size:10px;font-weight:800;color:var(--blue);letter-spacing:.08em;border-bottom:1px dashed var(--line)}
.art-row{display:flex;gap:7px;margin:11px 14px}.art-row i{width:14px;height:14px;background:var(--soft);border-radius:50%}.art-row:nth-child(3) i:nth-child(2n){background:var(--blue-soft)}
.quick-link{display:flex;align-items:center;gap:14px;margin-top:17px;padding:18px 0;border-bottom:1px solid var(--line);background:transparent;text-align:left;width:100%;border-radius:0}
.quick-link .quick-icon{display:flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:12px;background:var(--surface);border:1px solid var(--line);color:var(--muted)}
.quick-copy{flex:1}.quick-copy strong{display:block;font-size:13px}.quick-copy small{display:block;font-size:11px;font-weight:400;color:var(--muted);margin-top:2px}.quick-link>svg{width:15px;color:var(--muted)}
.small-print{display:flex;align-items:flex-start;gap:7px;color:var(--muted);font-size:11px;margin:20px 2px 0;line-height:1.8}.small-print svg{width:14px;height:14px;margin-top:3px}
.footer{margin-top:32px;padding-top:20px;border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:18px;font-size:10px;color:var(--muted)}
.footer .sync{white-space:nowrap}.wallet-toolbar{display:flex;flex-wrap:wrap;min-width:0;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.wallet-toolbar .select-wrap{display:flex;flex-wrap:wrap;min-width:0;align-items:center;gap:12px}.wallet-toolbar label{font-size:13px;color:var(--muted);white-space:nowrap;margin:0}.wallet-toolbar select{width:190px;max-width:100%}
.wallet-paper .ticket-list{padding:0 30px}.wallet-paper .ticket-row{min-height:92px;grid-template-columns:40px minmax(0,1fr) auto;gap:24px}.wallet-paper .ticket-balls{--ball-size:43px;gap:16px}.wallet-paper .ball{font-size:17px}.wallet-paper .game-label{font-size:15px}.wallet-paper .prize{font-size:13px}.wallet-paper .paper-top{padding:24px 30px}.wallet-paper .paper-bottom{padding:18px 30px}
.wallet-actions{display:flex;flex-wrap:wrap;gap:8px}.wallet-actions button{font-size:13px}.wallet-description{font-size:12px;color:var(--muted);margin:18px 2px 0}
.review-grid{display:grid;gap:24px}.review-block{border:1px solid var(--line);border-radius:18px;background:var(--surface);padding:26px}
.review-block .section-heading{margin-bottom:10px}.review-note{font-size:12px;color:var(--muted);margin-bottom:20px;line-height:1.9}
.result-balls[data-evaluated="true"] .ball[data-hit="main"]{outline:3px solid var(--green);outline-offset:-3px;transform:none;z-index:1}
.result-balls[data-evaluated="true"] .ball[data-hit="bonus"]{outline:3px dashed var(--blue);outline-offset:-3px;transform:none;z-index:1}
.result-balls[data-evaluated="true"] .ball[data-hit="miss"]{opacity:.38;filter:saturate(.35) brightness(1.06)}
.result-detail{display:block;margin-top:6px;color:var(--green);font-size:11px;font-weight:650;line-height:1.55}
@media(forced-colors:active){.result-balls[data-evaluated="true"] .ball[data-hit="main"],.result-balls[data-evaluated="true"] .ball[data-hit="bonus"]{outline:3px solid Highlight;outline-offset:2px}.result-balls[data-evaluated="true"] .ball[data-hit="miss"]{opacity:1;filter:none}}
.review-count{padding:4px 8px;background:var(--soft);font-size:11px;color:var(--muted);border-radius:6px}
.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;text-align:left}caption{text-align:left;color:var(--muted);font-size:12px;padding-bottom:16px}
th{font-size:11px;font-weight:500;color:var(--muted);background:var(--soft)}th,td{padding:16px 12px;border-bottom:1px solid var(--line);vertical-align:middle}th:first-child{border-radius:8px 0 0 8px}th:last-child{border-radius:0 8px 8px 0}tbody tr:last-child td{border:0}td:first-child{font-weight:600;max-width:300px}td .ticket-balls{gap:6px;--ball-size:29px}.empty-cell{text-align:center!important;color:var(--muted);padding:36px!important;font-weight:400!important;font-size:12px}.empty-cell strong{display:block;color:var(--ink);font-size:14px;margin-bottom:8px}
.review-method{display:flex;align-items:flex-start;gap:10px}.method-mark{display:flex;align-items:center;justify-content:center;background:var(--blue-soft);color:var(--blue);width:32px;height:32px;border-radius:10px;flex:none}.method-mark svg{width:17px;height:17px}
.review-footnote{color:var(--muted);font-size:12px;line-height:1.9}details summary{cursor:pointer;min-height:44px;align-content:center;list-style-position:inside}details p{padding-bottom:12px}
/* Native modal sheet: focus trapping, background inertness, and Escape support. */
dialog{inset:0 0 0 auto;margin:0;width:min(580px,100%);max-width:none;height:100dvh;max-height:none;border:0;border-left:1px solid var(--line);padding:var(--lotto-safe-top) var(--lotto-viewport-right) 0 var(--lotto-viewport-left);color:var(--ink);background:var(--surface);box-shadow:-12px 0 60px #0a17382b;overflow:hidden;outline:0}
dialog::backdrop{background:#14213b66;backdrop-filter:blur(4px)}.sheet{height:100%;display:flex;flex-direction:column}.sheet-head{display:flex;align-items:center;justify-content:space-between;padding:22px 26px;border-bottom:1px solid var(--line);flex:none}.sheet-head h2{font-size:22px}.sheet-head .icon-only{background:var(--soft);border-radius:50%;width:36px;min-height:36px;padding:8px}.sheet-scroll{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;padding:26px}
.steps{display:flex;align-items:center;gap:10px;margin-bottom:30px;font-size:12px;color:var(--muted)}.steps span{display:flex;align-items:center;gap:7px}.steps b{font-size:10px;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;background:var(--soft);border-radius:50%;font-weight:600}.steps span[data-current="true"]{color:var(--blue);font-weight:600}.steps span[data-current="true"] b{color:#fff;background:#2563eb}.steps>svg{width:12px;height:12px;color:var(--muted)}
.sheet-intro h3{font-size:25px;line-height:1.5;margin-bottom:10px}.sheet-intro p{font-size:13px;color:var(--muted);line-height:1.8}.import-choices{display:grid;gap:12px;margin:26px 0}
.import-choice{display:flex;width:100%;align-items:center;justify-content:initial;gap:16px;padding:18px;border-radius:15px;background:var(--surface);border:1px solid var(--line);text-align:left;min-height:90px}.import-choice:first-child{background:var(--blue-soft);border-color:transparent}.import-choice .choice-icon{display:flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:14px;background:var(--soft);color:var(--muted)}.import-choice:first-child .choice-icon{background:var(--surface);color:var(--blue)}.choice-text{flex:1}.choice-text strong{display:block;font-size:15px}.choice-text small{display:block;color:var(--muted);font-size:12px;font-weight:400;margin-top:4px}.import-choice>svg{width:16px;color:var(--muted)}
.address-import{padding-top:10px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}.address-import label{margin:8px 0}.address-import button{width:100%;margin:10px 0}.camera-view{padding:14px;background:var(--soft);border-radius:14px;margin:16px 0}video{display:block;width:100%;max-height:300px;object-fit:contain;border-radius:10px}.camera-view button{width:100%;margin-top:10px;background:var(--surface)}
label{display:block;font-size:13px;font-weight:600;margin-bottom:8px}input,select,textarea{border:1px solid var(--field);border-radius:11px;padding:12px 13px;width:100%;min-height:46px;color:var(--ink);background:var(--surface);line-height:1.5;font-variant-numeric:tabular-nums}
input::placeholder,textarea::placeholder{color:var(--muted);opacity:1}textarea{resize:vertical;min-height:86px;font-size:13px}input[aria-invalid="true"]{border:2px solid var(--danger)}
.round-control{display:flex;align-items:end;gap:10px;margin:23px 0 8px}.round-control>div{flex:1}.round-control button{min-height:46px;white-space:nowrap;font-size:13px}.savedrounds{font-size:11px;color:var(--muted);margin-bottom:22px;overflow-wrap:anywhere}
.form-count{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted)}.form-count strong{color:var(--ink)}
.game-field{padding:18px 0 6px;border-bottom:1px solid var(--line)}.game-field label{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:8px}.slot-tag{display:flex;align-items:center;justify-content:center;width:23px;height:23px;background:var(--soft);color:var(--ink);border-radius:6px;font-size:11px;font-weight:700}.game-field input{letter-spacing:.03em;font-size:16px}
.game-feedback{font-size:11px;margin:6px 0 10px;min-height:19px;color:var(--muted)}.game-feedback[data-valid="true"]{color:var(--green)}.game-feedback[data-valid="false"]{color:var(--danger)}
.add-game{width:100%;margin:14px 0 6px;background:transparent;color:var(--blue);border:1px dashed var(--field);font-size:13px}.input-help{font-size:11px;color:var(--muted);line-height:1.9;margin-top:10px}.input-help summary{min-height:36px}
.sheet-foot{padding:17px 26px max(20px,var(--lotto-safe-bottom));border-top:1px solid var(--line);background:var(--surface);flex:none}.draft-status{font-size:12px;margin-bottom:11px;color:var(--muted);text-align:center}.sheet-actions{display:flex;gap:10px}.sheet-actions .primary{flex:1;min-height:50px}.sheet-actions .ghost{font-size:13px}.sheet-privacy{display:flex;align-items:center;justify-content:center;gap:6px;font-size:11px;color:var(--muted);padding:5px 0}.sheet-privacy svg{width:14px;height:14px}
.notice{position:fixed;z-index:12;left:var(--lotto-viewport-left);right:var(--lotto-viewport-right);bottom:calc(22px + var(--lotto-safe-bottom));margin-inline:auto;max-width:min(650px,calc(100vw - 32px - var(--lotto-viewport-left) - var(--lotto-viewport-right)));width:max-content;background:var(--ink);color:var(--surface);border-radius:14px;padding:14px 20px;box-shadow:0 6px 26px #15213626;font-size:13px;line-height:1.8;white-space:pre-line;overflow-wrap:anywhere}.notice:empty{display:none}.notice[data-error="true"]{background:var(--danger-soft);color:var(--danger);border:1px solid var(--danger)}
.editor-notice{padding:12px 14px;border-radius:10px;background:var(--blue-soft);font-size:12px;color:var(--blue);line-height:1.9;margin-bottom:18px;white-space:pre-line;overflow-wrap:anywhere}.editor-notice:empty{display:none}.editor-notice[data-error="true"]{background:var(--danger-soft);color:var(--danger)}
.sr-only{position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;padding:0!important;margin:-1px!important;border:0!important}
@container wallet (max-width:1100px){.draw-stage{padding:28px 28px 0}.draw-details{margin:0 -28px;padding:0 28px}.draw-main{grid-template-columns:170px minmax(0,1fr);gap:20px}.draw-stage h2{font-size:28px}.draw-numbers{--ball-size:54px;gap:9px}.draw-numbers .ball{font-size:23px}.bonus-group{gap:8px}.dashboard-grid{grid-template-columns:minmax(0,1fr) 266px;gap:24px}.ticket-list{padding:0 18px}.paper-top,.paper-bottom{padding-left:18px;padding-right:18px}.ticket-balls{--ball-size:29px;gap:6px}.ticket-row{gap:10px;grid-template-columns:18px minmax(0,1fr) auto}.import-promo{padding:24px 22px 18px}}
@container wallet (max-width:870px){.wrap{--page-gutter:28px}.header-label{display:none}.draw-main{grid-template-columns:1fr;gap:14px}.draw-intro{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.draw-kicker{width:100%;margin:0}.verification{margin:0 0 0 auto}.draw-numbers{justify-content:flex-start;--ball-size:58px;min-height:110px;gap:12px}.draw-foot{margin-top:15px}.dashboard-grid{grid-template-columns:1fr;gap:0}.import-promo{margin-top:24px;min-height:190px}.ticket-art{width:200px;height:145px;right:34px;bottom:-20px}.quick-link{margin-top:10px}.ticket-row{min-height:74px}.ticket-balls{--ball-size:34px;gap:11px}.wallet-paper .ticket-balls{--ball-size:36px;gap:10px}.wallet-paper .ticket-row{gap:12px;grid-template-columns:26px minmax(0,1fr) auto}.connection{display:none}.draw-stage h2{font-size:29px}}
@container wallet (max-width:560px){.wrap{--page-gutter:20px}.header-row{min-height:76px;gap:8px}.brand-logo{width:136px}.header-tools{gap:3px}.main-tabs{gap:29px;min-height:50px}.main-tabs button{font-size:14px;padding-bottom:13px}.entry-field{max-width:120px}.entry-field select{font-size:11px;width:120px;padding-left:8px}.header-tools .settings span{display:none}main{padding-top:26px!important}.page-heading{align-items:flex-start;margin-bottom:23px;flex-wrap:wrap;gap:17px}h1{font-size:28px}.page-heading p{font-size:12px;margin-top:8px}.page-heading .primary{font-size:13px;min-height:44px;padding:11px 16px}.kicker{font-size:10px;margin-bottom:8px}.draw-stage{padding:22px 18px 0;border-radius:20px}.draw-intro{gap:9px}.draw-kicker{font-size:12px}.draw-stage h2{font-size:25px}.verification{font-size:12px}.draw-numbers{--ball-size:clamp(26px,calc((100cqw - 142px)/7),45px);min-height:84px;gap:6px}.draw-numbers .ball{font-size:clamp(13px,4cqw,19px)}.bonus-group{gap:6px;margin-left:0}.plus{font-size:14px}.bonus-caption{font-size:12px;top:calc(100% + 8px)}.draw-main{gap:8px}.draw-foot{align-items:flex-start;margin-top:10px;gap:10px;padding:15px 0;min-height:80px}.result-copy{display:block;flex:1}.result-copy .caption{display:block;margin-bottom:4px;font-size:12px}.result-copy strong{display:block;font-size:13px}.draw-foot button{font-size:12px;min-height:44px;padding:8px}.draw-foot button svg{width:13px}.draw-details{margin:0 -18px;padding:0 18px;font-size:12px}.draw-details summary{min-height:44px}.dashboard-grid{margin-top:27px}.section-heading{margin-bottom:12px}.section-heading h2{font-size:19px}.section-heading button{font-size:11px}.paper-top{padding:15px 16px}.paper-label{font-size:12px;gap:6px}.paper-meta{font-size:10px}.ticket-list{padding:0 16px}.ticket-row{gap:8px;grid-template-columns:14px minmax(0,1fr) auto;min-height:67px}.ticket-balls{--ball-size:clamp(23px,calc((100cqw - 176px)/6),32px);gap:5px}.ticket-balls .ball{font-size:11px}.prize{font-size:9px;padding:3px 5px}.game-label{font-size:11px}.paper-bottom{padding:10px 16px;font-size:10px;gap:6px}.paper-bottom button{font-size:11px}.import-promo{margin-top:20px;padding:24px;min-height:200px}.import-promo h3{font-size:19px}.ticket-art{width:158px;right:-22px;bottom:-19px;height:129px}.import-promo p{font-size:11px;max-width:200px}.quick-copy strong{font-size:12px}.quick-copy small{font-size:10px}.small-print{font-size:10px}.footer{display:block;font-size:9px;line-height:1.9;margin-top:26px}.footer .sync{display:block;margin-top:6px}.wallet-toolbar{align-items:flex-start}.wallet-toolbar .select-wrap{gap:8px;flex-wrap:wrap}.wallet-toolbar select{width:143px;font-size:13px}.wallet-toolbar label{font-size:12px}.wallet-actions button{padding:10px;font-size:12px}.wallet-paper .paper-top{padding:18px 16px}.wallet-paper .paper-bottom{padding:12px 16px}.wallet-paper .ticket-list{padding:0 16px}.wallet-paper .ticket-row{grid-template-columns:16px minmax(0,1fr) auto;gap:8px;min-height:77px}.wallet-paper .ticket-balls{--ball-size:clamp(23px,calc((100cqw - 176px)/6),33px);gap:5px}.wallet-paper .ball{font-size:12px}.wallet-paper .game-label{font-size:12px}.wallet-paper .prize{font-size:9px}.wallet-description{font-size:11px}.review-block{padding:20px 16px}.review-block .section-heading h2{font-size:18px}.review-note{font-size:11px;margin-bottom:14px}.review-footnote{font-size:11px}.table-scroll{overflow:visible}.mobile-table,.mobile-table tbody{display:block}.mobile-table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}.mobile-table tr{display:block;border-bottom:1px solid var(--line);padding:14px 0}.mobile-table tr:last-child{border:0}.mobile-table td{display:grid;grid-template-columns:70px minmax(0,1fr);gap:8px;border:0;padding:6px 0;font-size:12px;max-width:none}.mobile-table td::before{content:attr(data-label);color:var(--muted);font-size:10px;font-weight:400}.mobile-table td .ticket-balls{--ball-size:23px;gap:4px}.mobile-table .empty-cell{display:block}.mobile-table .empty-cell::before{display:none}.mobile-table caption{display:block}.sheet-head{padding:18px 20px}.sheet-scroll{padding:22px 20px}.sheet-foot{padding:16px 20px max(20px,var(--lotto-safe-bottom))}.sheet-intro h3{font-size:24px}.steps{gap:8px}.import-choice{padding:17px 14px}.game-field input{font-size:16px}.notice{font-size:12px;bottom:calc(16px + var(--lotto-safe-bottom))}}
@container wallet (max-width:350px){.wrap{--page-gutter:16px}.brand-logo{width:115px}.main-tabs{gap:25px}.header-row{gap:4px}.draw-stage{padding:20px 14px 0}.draw-details{margin:0 -14px;padding:0 14px}.verification{margin-left:0}.draw-numbers{gap:4px}.bonus-group{gap:4px}.ticket-list,.wallet-paper .ticket-list{padding:0 12px}.ticket-row,.wallet-paper .ticket-row{gap:5px;grid-template-columns:12px minmax(0,1fr) auto}.ticket-balls,.wallet-paper .ticket-balls{--ball-size:23px;gap:3px}.ticket-art{right:-50px}.paper-meta{font-size:9px}.header-tools .settings{min-width:36px}.entry-field,.entry-field select{max-width:99px;width:99px}}
@container wallet (max-width:560px){.header-row{flex-wrap:wrap}.header-tools{display:contents}.header-tools .settings{margin-left:auto}.entry-field{order:5;flex-basis:100%;max-width:none;width:100%;padding:0 0 12px}.entry-field select{max-width:none;width:100%;font-size:13px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
@media(forced-colors:active){button,.ticket-paper,.draw-stage,.ball{border:1px solid CanvasText}.main-tabs button[aria-selected="true"]{outline:2px solid Highlight}.verification{color:CanvasText}}
/* Match marks stay inside their ball. Gaps survive narrow-table overrides. */
.ticket-balls.result-balls,.mobile-table td .ticket-balls.result-balls{gap:8px;row-gap:8px;flex-wrap:wrap;min-width:0;max-width:100%;box-sizing:border-box}
.ticket-balls.result-balls .ball[data-hit="main"]{outline:3px solid var(--green);outline-offset:-3px;box-shadow:none}
.ticket-balls.result-balls .ball[data-hit="bonus"]{outline:3px dashed var(--blue);outline-offset:-3px;box-shadow:none}
.ticket-balls.result-balls[data-has-matches="false"] .ball{opacity:1;filter:none}
.mobile-table .result-detail{grid-column:2;white-space:normal;overflow-wrap:anywhere}
@media(forced-colors:active){.ticket-balls.result-balls .ball[data-hit="main"],.ticket-balls.result-balls .ball[data-hit="bonus"]{outline-color:Highlight}.ticket-balls.result-balls .ball{opacity:1;filter:none}}
</style>
<div class="shell">
  <header class="app-header">
    <div class="wrap header-row">
      <button id="menu" class="ghost icon-only" type="button" aria-label="Home Assistant 메뉴 열기">${icons.menu}</button>
      <button id="brand-home" class="brand-link" type="button" aria-label="로또 6/45 한눈에 화면으로"><img id="brand" class="brand-logo" alt="Lotto 6/45" width="512" height="170"><span id="brand-fallback" class="brand-fallback" hidden>Lotto 6/45</span></button>
      <span class="header-label">나의 로또, 한곳에</span>
      <div class="header-tools"><span id="connection" class="connection" data-online="false">연결 확인 중</span><div id="entry-field" class="entry-field" hidden><label for="entry" class="sr-only">로또 통합 선택</label><select id="entry"></select></div><a class="settings" href="/config/integrations/integration/lotto_645" aria-label="로또 통합 및 센서 설정">${icons.settings}</a></div>
    </div>
    <div class="wrap"><div class="main-tabs" role="tablist" aria-label="로또 관리 화면"><button id="tab-home" type="button" role="tab" aria-selected="true" aria-controls="screen-home" tabindex="0" data-screen="home">한눈에</button><button id="tab-wallet" type="button" role="tab" aria-selected="false" aria-controls="screen-wallet" tabindex="-1" data-screen="wallet">내 복권</button><button id="tab-review" type="button" role="tab" aria-selected="false" aria-controls="screen-review" tabindex="-1" data-screen="review">추천 리뷰</button></div></div>
  </header>
  <main class="wrap">
    <section id="screen-home" class="screen" role="tabpanel" aria-labelledby="tab-home" tabindex="0">
      <div class="page-heading"><div><div class="kicker">MY LOTTO</div><h1>이번 주의 작은 기대.</h1><p>당첨 결과를 확인하고, 내 복권을 한곳에 모아보세요.</p></div><button class="primary" type="button" data-register>${icons.plus}복권 등록</button></div>
      <section class="draw-stage" aria-labelledby="drawtitle">
        <div class="draw-main"><div class="draw-intro"><p class="draw-kicker">최근 추첨 결과</p><h2 id="drawtitle">결과 확인 중</h2><span id="verification" class="verification" data-state="pending">공식 결과 확인 중</span></div><div id="numbers" class="draw-numbers">당첨번호를 불러오고 있어요.</div></div>
        <div class="draw-foot"><div class="result-copy"><span class="caption">구매·추천번호 대조</span><strong id="result">저장한 번호를 확인하고 있어요.</strong></div><button id="check" type="button">${icons.refresh}다시 확인</button></div>
        <details class="draw-details"><summary>결과 확인 기준과 출처</summary><p>속보 결과는 공식 이력이 확인되면 다시 대조합니다. 출처가 서로 다르면 판정을 보류합니다. 결과 발표나 수신이 늦어질 수 있습니다.</p><div id="sources"></div></details>
      </section>
 <div class="dashboard-grid">
        <section aria-labelledby="home-wallet-heading"><div class="section-heading"><h2 id="home-wallet-heading">내 복권</h2><button type="button" data-go="wallet">전체 보기${icons.arrow}</button></div>
          <div class="ticket-paper"><div class="paper-top"><span class="paper-label">${icons.ticket}<span id="mini-round">보관한 복권</span></span><span id="mini-count" class="paper-meta">불러오는 중</span></div><div id="mini-games" class="ticket-list"></div><div class="paper-bottom"><span>등록한 번호는 결과 발표 후 자동 대조해요.</span><button type="button" data-go="wallet">복권 관리${icons.arrow}</button></div></div>
          <p class="small-print">${icons.lock}<span>내 번호는 Home Assistant에 보관해요. 실제 복권은 별도로 보관해 주세요.</span></p>
        </section>
        <aside aria-label="간편 등록과 리뷰"><div class="import-promo"><h3>종이 복권은 그대로,<br>번호만 간편하게.</h3><p>QR을 읽으면 번호 입력이 끝.<br>확인 후 내 복권에 저장하세요.</p><button type="button" data-register>QR로 가져오기${icons.arrow}</button><div class="ticket-art" aria-hidden="true"><div class="art-head">MY LOTTO</div><div class="art-row"><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="art-row"><i></i><i></i><i></i><i></i><i></i><i></i></div></div></div><button class="quick-link" type="button" data-go="review"><span class="quick-icon">${icons.chart}</span><span class="quick-copy"><strong>추첨 공식별 결과는 어땠을까요?</strong><small>이번 결과와 누적 리뷰 확인</small></span>${icons.arrow}</button></aside>
      </div>
    </section>
    <section id="screen-wallet" class="screen" role="tabpanel" aria-labelledby="tab-wallet" tabindex="0" hidden>
      <div class="page-heading"><div><div class="kicker">MY TICKETS</div><h1>내 복권</h1><p>구매한 번호를 회차별로 보관하고 확인하세요.</p></div><button class="primary" type="button" data-register>${icons.plus}복권 등록</button></div>
      <div class="wallet-toolbar"><div class="select-wrap"><label for="wallet-round">회차 선택</label><select id="wallet-round"></select><label for="wallet-ticket">복권 선택</label><select id="wallet-ticket"></select></div><div class="wallet-actions"><button id="export-wallet" type="button">내보내기</button><button id="edit-wallet" type="button" class="soft-blue">${icons.edit}번호 수정</button></div></div>
      <section class="ticket-paper wallet-paper" aria-labelledby="ticket-round"><div class="paper-top"><span class="paper-label">${icons.ticket}<span id="ticket-round">보관한 복권</span></span><span id="wallet-count" class="paper-meta"></span></div><div id="wallet-games" class="ticket-list"></div><div class="paper-bottom"><span>입력 중인 번호가 아닌, 저장된 번호의 결과입니다.</span><button id="delete-wallet" type="button" class="danger">이 복권 삭제</button></div></section>
      <p class="wallet-description">최대 5게임(A~E)을 저장할 수 있어요. 같은 회차를 다시 저장하면 기존 번호를 교체합니다.</p>
    </section>
    <section id="screen-review" class="screen" role="tabpanel" aria-labelledby="tab-review" tabindex="0" hidden>
      <div class="page-heading"><div><div class="kicker">RECOMMENDATION REVIEW</div><h1>추천을 돌아보는 시간.</h1><p>추첨 공식의 실제 결과를 차곡차곡 비교해 보세요.</p></div><span id="method-count" class="review-count"></span></div>
      <section class="review-block current-formulas" aria-labelledby="current-recommendations-heading">
        <div class="section-heading"><h2 id="current-recommendations-heading">현재 생성번호</h2></div>
        <p id="current-recommendations-note" class="review-note">선택한 공식의 현재 생성번호입니다. 실제 구매와 추첨 결과는 별도로 관리합니다.</p>
        <div class="table-scroll"><table class="mobile-table"><caption class="sr-only">선택 공식의 현재 생성번호와 연결 상태</caption><thead><tr><th scope="col">추첨 공식</th><th scope="col">번호</th><th scope="col">상태</th></tr></thead><tbody id="current-recommendations"></tbody></table></div>
      </section>
      <div class="review-grid"><section class="review-block" aria-labelledby="predictions-heading"><div class="section-heading"><h2 id="predictions-heading">이번 추첨, 추천번호 결과</h2></div><p id="predictions-note" class="review-note">추첨 전에 저장된 추천과 발표된 당첨번호를 비교합니다. 당첨 게임은 본번호 일치를 테두리로, 보너스 일치를 점선 테두리로 강조하고 미일치 번호는 흐리게 표시합니다.</p><div class="table-scroll"><table class="mobile-table" role="table"><caption class="sr-only">추첨 공식별 번호와 이번 추첨 판정</caption><thead role="rowgroup"><tr role="row"><th scope="col">추첨 공식</th><th scope="col">번호</th><th scope="col">결과</th></tr></thead><tbody id="predictions" role="rowgroup"></tbody></table></div></section>
      <section class="review-block" aria-labelledby="reviews-heading"><div class="section-heading"><h2 id="reviews-heading">공식별 누적 리뷰</h2></div><p id="reviewstatus" class="review-note"></p><div class="table-scroll"><table class="mobile-table" role="table"><caption class="sr-only">추첨 공식별 누적 별점, 평가 회차, 이번 점수, 정확 일치와 인접 번호, 순위</caption><thead role="rowgroup"><tr role="row"><th scope="col">추첨 공식 / 누적 별점</th><th scope="col">평가 회차</th><th scope="col">이번 점수</th><th scope="col">정확 / ±1</th><th scope="col">순위</th></tr></thead><tbody id="reviews" role="rowgroup"></tbody></table></div></section>
      <details class="review-footnote"><summary>리뷰 점수는 이렇게 해석해 주세요</summary><p>공식 확인 회차의 평균 점수 ÷ 20이 누적 별점입니다. ±1은 비슷한 번호일 뿐 당첨이 아닙니다. 속보 점수는 잠정이며 누적 평균과 분리합니다. 표본이 적은 별점이나 과거 결과는 미래 당첨 가능성을 뜻하지 않습니다.</p></details></div>
    </section>

    <footer class="footer"><span>이 화면은 번호 관리·대조용입니다. 실제 구매나 당첨금 지급을 인증하지 않습니다.</span><span id="sync-status" class="sync">Home Assistant 연결 확인 중</span></footer>
  </main>
</div>
<div id="message" class="notice" role="status" aria-live="polite" aria-atomic="true"></div>
<dialog id="editor" aria-labelledby="editor-title" aria-modal="true"><div class="sheet"><header class="sheet-head"><h2 id="editor-title">복권 등록</h2><button id="close-editor" type="button" class="icon-only" aria-label="복권 등록 닫기">${icons.close}</button></header><div class="sheet-scroll" id="sheet-scroll"><div class="steps" aria-label="복권 등록 단계"><span id="step-1" data-current="true"><b>1</b>번호 가져오기</span>${icons.arrow}<span id="step-2" data-current="false"><b>2</b>확인하고 저장</span></div><div id="editor-message" class="editor-notice" role="status" aria-live="polite" aria-atomic="true"></div>
  <div id="import-step"><div class="sheet-intro"><h3>어떤 방법으로<br>가져올까요?</h3><p>편한 방법을 선택하세요.<br>불러온 번호는 확인 후에만 저장돼요.</p></div><div class="import-choices"><button id="scan" class="import-choice" type="button"><span class="choice-icon">${icons.scan}</span><span class="choice-text"><strong>QR 스캔</strong><small>카메라로 복권의 QR을 읽어요.</small></span>${icons.arrow}</button><button id="photo" class="import-choice" type="button"><span class="choice-icon">${icons.photo}</span><span class="choice-text"><strong>사진에서 가져오기</strong><small>이미 찍어 둔 복권 사진을 선택해요.</small></span>${icons.arrow}</button><button id="manual" class="import-choice" type="button"><span class="choice-icon">${icons.edit}</span><span class="choice-text"><strong>직접 입력</strong><small>회차와 6개의 번호를 입력해요.</small></span>${icons.arrow}</button></div><input id="file" type="file" accept="image/png,image/jpeg,image/webp" hidden><div id="camera" class="camera-view" hidden><video id="video" autoplay muted playsinline aria-label="복권 QR 스캔 카메라"></video><button id="stop" type="button">카메라 종료</button></div><details class="address-import" id="address-import"><summary>QR 주소를 복사해 두셨나요?</summary><label for="qr">복권 QR 주소</label><textarea id="qr" maxlength="2048" placeholder="https://qr.dhlottery.co.kr/?v=..."></textarea><button id="preview" class="soft-blue" type="button">주소에서 번호 가져오기</button><p>주소를 열지 않고 회차와 번호를 해석합니다.</p></details></div>
  <div id="edit-step" hidden><div class="sheet-intro"><h3>번호가 맞는지<br>한 번 더 확인해 주세요.</h3><p>빈 게임은 저장하지 않아요. 최대 5게임까지 가능해요.</p></div><div class="round-control"><div><label for="round">복권에 적힌 회차</label><input id="round" type="text" inputmode="numeric" maxlength="6" autocomplete="off"></div><button id="load" type="button">회차 불러오기</button></div><p id="savedrounds" class="savedrounds"></p><div class="form-count"><strong>구매번호 A~E</strong><span id="ticket-count"></span></div><div id="games"></div><button id="add-game" class="add-game" type="button">${icons.plus}게임 추가</button><details class="input-help"><summary>번호를 빠르게 입력하는 방법</summary><p>예: 1, 7, 15, 24, 33, 45 또는 1 7 15 24 33 45.<br>숫자 키패드에서는 010715243345처럼 두 자리씩 붙여 넣을 수도 있어요.<br>게임당 1~45의 중복 없는 번호 6개를 입력하세요.</p></details></div>
</div><footer class="sheet-foot"><div id="save-footer" hidden><p id="draft-status" class="draft-status" role="status" aria-live="polite"></p><div class="sheet-actions"><button id="back-editor" type="button" class="ghost">${icons.back}이전</button><button id="save" type="button" class="primary">내 복권에 저장</button></div></div><p id="privacy-footer" class="sheet-privacy">${icons.lock}QR 사진은 기기 밖으로 전송하지 않아요.</p></footer></div></dialog>`;

// The existing accepted input formats remain unchanged.
export function parseGame(value) {
  const raw=String(value||'').trim();
  if(!raw) return {empty:true,numbers:[]};
  const parts=/^\d{12}$/.test(raw)?raw.match(/\d{2}/g):raw.split(/[\s,]+/).filter(Boolean);
  if(parts.some(p=>!/^\d{1,2}$/.test(p)))return {empty:false,error:'1~45의 숫자만 입력해 주세요.'};
  const numbers=parts.map(Number);
  if(numbers.some(n=>n<1||n>45))return {empty:false,error:'번호는 1부터 45까지 입력할 수 있어요.'};
  if(new Set(numbers).size!==numbers.length)return {empty:false,error:'같은 게임에 중복된 번호가 있어요.'};
  if(numbers.length!==6)return {empty:false,error:`번호 6개가 필요해요. 현재 ${numbers.length}개예요.`};
  return {empty:false,numbers};
}

export function numberBalls(root, numbers, bonus=null, outcome=null) {
  root.replaceChildren();
  const valid=(numbers||[]).filter(n=>Number.isInteger(n)&&n>=1&&n<=45);
  const hasBonus=Number.isInteger(bonus)&&bonus>=1&&bonus<=45;
  const winning=Number.isInteger(outcome?.prize_rank)&&outcome.prize_rank>=1&&outcome.prize_rank<=5;
  const evaluated=Number.isInteger(outcome?.main_match_count)&&outcome.main_match_count>=0&&outcome.main_match_count<=6&&Array.isArray(outcome?.matched_main_numbers)&&outcome.generation_status!=='unavailable';
  const matchedMain=new Set((outcome?.matched_main_numbers||[]).filter(n=>valid.includes(n)));
  const matchedBonus=evaluated&&outcome?.bonus_match===true&&valid.includes(outcome?.matched_bonus_number)?outcome.matched_bonus_number:null;
  root.dataset.winning=String(winning);root.dataset.evaluated=String(evaluated);root.dataset.hasMatches=String(matchedMain.size>0||matchedBonus!==null);
  const missed=evaluated?valid.filter(n=>!matchedMain.has(n)&&n!==matchedBonus):[];
  const aria=[`번호 ${valid.join(', ')}`];
  if(hasBonus)aria.push(`보너스 ${bonus}`);
  if(evaluated){
    if(matchedMain.size)aria.push(`당첨번호 일치 ${[...matchedMain].sort((a,b)=>a-b).join(', ')}`);
    if(matchedBonus!==null)aria.push(`보너스 일치 ${matchedBonus}`);
    if(missed.length)aria.push(`미일치 ${missed.join(', ')}`);
  }
  root.setAttribute('role','img');root.setAttribute('aria-label',aria.join('; '));
  const ball=n=>{const el=document.createElement('span');el.className='ball';el.dataset.band=String(Math.ceil(n/10));if(evaluated)el.dataset.hit=matchedMain.has(n)?'main':n===matchedBonus?'bonus':'miss';el.textContent=n;el.setAttribute('aria-hidden','true');return el;};
  valid.forEach(n=>root.append(ball(n)));
  if(hasBonus){const group=document.createElement('span');group.className='bonus-group';group.setAttribute('aria-hidden','true');const plus=document.createElement('span');plus.className='plus';plus.textContent='+';const wrap=document.createElement('span');wrap.className='bonus-label';const text=document.createElement('span');text.className='bonus-caption';text.textContent='보너스';wrap.append(ball(bonus),text);group.append(plus,wrap);root.append(group);}
}

export function ticketRows(root, games, limit=Infinity, matches=[]) {
  root.replaceChildren();root.setAttribute('role','list');
  if(!games?.length){root.removeAttribute('role');const empty=document.createElement('div');empty.className='empty';empty.innerHTML=`${icons.ticket}<strong>아직 보관한 복권이 없어요.</strong><p>복권 등록을 눌러 QR이나 사진으로 가져오세요.<br>번호를 직접 입력해도 좋아요.</p>`;root.append(empty);return;}
  for(const g of games.slice(0,limit)) {
    const row=document.createElement('div');row.className='ticket-row';row.setAttribute('role','listitem');
    const slot=document.createElement('span');slot.className='game-label';slot.textContent=g.slot||'';slot.setAttribute('aria-label',`${g.slot||''} 게임`);
    const nums=document.createElement('span');nums.className='ticket-balls result-balls';
    const isWinner=Number.isInteger(g.prize_rank)&&g.prize_rank>=1&&g.prize_rank<=5;
    numberBalls(nums,g.numbers||g.recommended_numbers||[],null,g);
    const status=document.createElement('span');status.className='ticket-status';
    const linked=(Array.isArray(matches)?matches:[]).filter(m=>m.slot===g.slot&&(!g.ticket_id||m.ticket_id===g.ticket_id));
    if(linked.length){
      const badge=document.createElement('span');badge.className='match-badge';
      badge.textContent=linked.length===1?'공식 일치':`공식 ${linked.length}개 일치`;
      const labels=[...new Set(linked.map(m=>m.formula_label||m.formula_id).filter(Boolean))];
      if(labels.length)badge.title=`${labels.join(', ')} 생성번호와 6개 번호가 모두 같습니다.`;
      status.append(badge);
    }
    const prize=document.createElement('span');prize.className='prize';prize.textContent=g.prize||'추첨 대기';prize.dataset.winning=String(isWinner);status.append(prize);
    row.append(slot,nums,status);root.append(row);
  }
}

export function currentRecommendations(data) {
  const target=Number(data.recommendation_target),selected=new Set(data.selected_method_ids||[]);
  if(!Number.isInteger(target)||target<1)return [];
  return (Array.isArray(data.recommendations)?data.recommendations:[]).filter(row=>
    (!selected.size||selected.has(row.method_id))&&Number(row.target_round??target)===target&&
    Array.isArray(row.numbers)&&row.numbers.length===6&&new Set(row.numbers).size===6&&
    row.numbers.every(n=>Number.isInteger(n)&&n>=1&&n<=45)).map(row=>({
      method_id:row.method_id,sensor_name:row.label||row.method||row.method_id,
      recommended_numbers:[...row.numbers],
      purchase_match:row.purchase_match===true,
      purchase_matches:Array.isArray(row.purchase_matches)?row.purchase_matches:[],
      prize:row.purchase_match===true?'구매번호 일치':'생성번호 · 평가 전'
    }));
}

export function reviewPresentation(data) {
  const report=data.review_round||{}, round=Number(report.round||data.draw_schedule?.round||data.recommendation_target);
  const evaluated=['confirmed','provisional'].includes(report.status);
  const methods=(report.methods||[]).filter(row=>!row.target_round||Number(row.target_round)===round);
  const rows=methods.map(row=>evaluated?{...row,sensor_name:row.label||row.method_id,recommended_numbers:row.numbers||[]}:
    {method_id:row.method_id,sensor_name:row.label||row.method_id,recommended_numbers:row.numbers||[],prize:'추첨 대기'});
  return {report,round,rows,evaluated};
}

export function renderPredictionRows(root, rows, empty) {
  root.replaceChildren();
  if(!rows.length){renderRows(root,[],['추첨 공식','번호','결과'],empty);return;}
  for(const row of rows){
    const tr=document.createElement('tr');tr.setAttribute('role','row');
    const isWinner=Number.isInteger(row.prize_rank)&&row.prize_rank>=1&&row.prize_rank<=5;tr.dataset.winning=String(isWinner);tr.className='prediction-row';
    const method=document.createElement('td');method.setAttribute('role','cell');method.dataset.label='추첨 공식';method.textContent=row.sensor_name||row.method_id||'—';
    const numberCell=document.createElement('td');numberCell.setAttribute('role','cell');numberCell.dataset.label='번호';const balls=document.createElement('span');balls.className='ticket-balls result-balls';numberBalls(balls,row.recommended_numbers||[],null,row);numberCell.append(balls);
    if(balls.dataset.evaluated==='true'){const detail=document.createElement('span');detail.className='result-detail';const main=(row.matched_main_numbers||[]).join(', ');detail.textContent=`일치 ${row.main_match_count}개${main?` · ${main}`:''}${row.bonus_match?` · 보너스 ${row.matched_bonus_number}`:''}`;numberCell.append(detail);}
    const result=document.createElement('td');result.setAttribute('role','cell');result.dataset.label='결과';const prize=document.createElement('span');prize.className='prize';prize.dataset.winning=String(isWinner);prize.dataset.purchaseMatch=String(row.purchase_match===true);prize.textContent=row.prize||'판정 대기';const linked=Array.isArray(row.purchase_matches)?row.purchase_matches:[];if(linked.length){const labels=linked.map(m=>`복권 ${m.ticket_number} · ${m.slot}게임`);prize.title=`${labels.join(', ')}과 6개 번호가 모두 같습니다.`;}result.append(prize);
    tr.append(method,numberCell,result);root.append(tr);
  }
}

export function renderRows(root, rows, headers, empty) {
  root.replaceChildren();
  if(!rows.length){const tr=document.createElement('tr');tr.setAttribute('role','row');const td=document.createElement('td');td.setAttribute('role','cell');td.colSpan=headers.length;td.className='empty-cell';const title=document.createElement('strong');title.textContent=empty[0];const text=document.createElement('span');text.textContent=empty[1];td.append(title,text);tr.append(td);root.append(tr);return;}
  for(const values of rows){const tr=document.createElement('tr');tr.setAttribute('role','row');values.forEach((v,i)=>{const td=document.createElement('td');td.setAttribute('role','cell');td.dataset.label=headers[i];const text=String(v??'—');if(headers[i]==='번호'&&/^\d{1,2}(?:, \d{1,2}){5}$/.test(text)){const balls=document.createElement('span');balls.className='ticket-balls';numberBalls(balls,text.split(', ').map(Number));td.append(balls);}else{const span=document.createElement('span');span.textContent=text;if(headers[i]==='결과'){span.className='prize';span.dataset.winning=String(/^[1-5]등/.test(text));}td.append(span);}tr.append(td);});root.append(tr);}
}
