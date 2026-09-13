from pathlib import Path
p=Path('custom_components/lotto_645/www/lotto-panel.js');s=p.read_text()
s=s.replace('    if (!this.shadowRoot.firstChild) this.render();','    if (!this.shadowRoot.firstChild) this.render();\n    this.syncEntries();')
s=s.replace("  node(id) { return this.shadowRoot.getElementById(id); }", """  syncEntries() {
    const entries=this._panel.config?.entries||{}, key=JSON.stringify(entries), select=this.node('entry');
    if(!select || key===this._entriesKey)return;
    this._entriesKey=key;const old=select.value;
    select.replaceChildren();
    for(const [id,title] of Object.entries(entries)){const n=document.createElement('option');n.value=id;n.textContent=title;select.append(n);}
    if(Object.hasOwn(entries,old))select.value=old;
    if(!select.options.length)this.message('등록된 로또 통합이 없습니다. 설정에서 통합을 확인하세요.',true);
  }
  node(id) { return this.shadowRoot.getElementById(id); }""")
s=s.replace("      main{max-width:780px;", """      .toolbar{display:flex;align-items:center;gap:12px;padding:10px 16px;background:var(--app-header-background-color,var(--card-background-color));border-bottom:1px solid var(--divider-color)}.toolbar button{font-size:24px;line-height:1;padding:7px 12px}.brand{display:block;width:min(100%,460px);height:auto;margin:0 auto 12px;object-fit:contain}.pageintro{font-size:14px}.review-note{font-size:13px;line-height:1.5}
      main{max-width:780px;""")
s=s.replace("</style><main><h1>로또 복권</h1>", """</style><header class="toolbar"><button id="menu" aria-label="홈어시스턴트 메뉴 열기" title="메뉴">☰</button><span>로또 복권</span></header><main><img id="brand" class="brand" alt="로또 6/45" width="2048" height="682"><h1>로또 복권</h1><p class="note pageintro">이 페이지는 추가 관리 화면입니다. 기존 추천 센서·대시보드·자동화는 그대로 사용할 수 있습니다.</p>""")
s=s.replace("const config=this._panel.config || {};", """const config=this._panel.config || {};
    this.node('brand').src=config.logo_url||'/lotto_645_brand/logo.png?v=1.10.1';
    this.node('brand').onerror=()=>{this.node('brand').hidden=true;};
    this.node('menu').onclick=()=>this.dispatchEvent(new CustomEvent('hass-toggle-menu',{bubbles:true,composed:true}));""")
s=s.replace("th,td{padding:9px 5px;border-bottom:1px solid var(--divider-color)}", "th,td{padding:9px 5px;border-bottom:1px solid var(--divider-color);vertical-align:top}th{white-space:nowrap}td:last-child{min-width:48px;white-space:nowrap}#reviews td:nth-child(n+2){white-space:nowrap}#reviews td:first-child{min-width:180px}")
s=s.replace("    const current=new Map((roundReview.methods||[]).map(r=>[r.method_id,r]));", "    const current=new Map((roundReview.methods||[]).map(r=>[r.method_id,r]));\n    const excluded=new Map((roundReview.excluded_methods||[]).map(r=>[r.method_id,r]));")
s=s.replace("      const now=current.get(r.method_id);\n      return [r.display_name,r.reviewed_rounds||0,now?`${roundReview.status==='provisional'?'잠정 ':''}${now.review_score.toFixed(1)}점`:'평가 대기'", "      const now=current.get(r.method_id), skip=excluded.get(r.method_id)||r.current_review_exclusion;\n      return [r.display_name+(skip?' · 누적 제외':''),r.reviewed_rounds||0,now?`${roundReview.status==='provisional'?'잠정 ':''}${now.review_score.toFixed(1)}점`:skip?`${skip.prize||''} · 누적 제외`:'평가 대기'")
s=s.replace("    const sourceRoot=this.node('sources');", "    if(excluded.size)this.node('reviewstatus').textContent+=` ${excluded.size}개 방식: 저장된 추첨 전 생성시각·기준회차를 확인할 수 없어 누적평가에서 제외합니다. 당첨 판정과는 별개이며 새 번호로 과거 기록을 만들지 않습니다.`;\n    const sourceRoot=this.node('sources');")
p.write_text(s)
