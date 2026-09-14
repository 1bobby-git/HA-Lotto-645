from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    assert text.count(old) == 1, (path, text.count(old), old[:100])
    p.write_text(text.replace(old, new))


replace_once('custom_components/lotto_645/const.py', 'VERSION = "1.12.1"', 'VERSION = "1.12.2"')
replace_once('custom_components/lotto_645/manifest.json', '"version": "1.12.1"', '"version": "1.12.2"')
for path in (
    'custom_components/lotto_645/www/lotto-panel-shell.js',
    'custom_components/lotto_645/www/lotto-panel.js',
    'custom_components/lotto_645/www/lotto-panel-tools.js',
):
    p = Path(path)
    text = p.read_text()
    assert '1.12.1' in text
    p.write_text(text.replace('1.12.1', '1.12.2'))

replace_once(
    'custom_components/lotto_645/www/lotto-panel-core.js',
    "import { panelTemplate, parseGame, numberBalls, ticketRows, renderRows } from './lotto-panel-view.js?v=1.11.3';",
    "import { panelTemplate, parseGame, numberBalls, ticketRows, renderRows, renderPredictionRows } from './lotto-panel-view.js?v=1.12.2';",
)

view = 'custom_components/lotto_645/www/lotto-panel-view.js'
replace_once(
    view,
    '.review-block .section-heading{margin-bottom:10px}.review-note{font-size:12px;color:var(--muted);margin-bottom:20px;line-height:1.9}',
    '.review-block .section-heading{margin-bottom:10px}.review-note{font-size:12px;color:var(--muted);margin-bottom:20px;line-height:1.9}\n'
    '.result-balls[data-winning="true"] .ball[data-hit="main"]{outline:3px solid var(--green);outline-offset:2px;transform:scale(1.06);z-index:1}\n'
    '.result-balls[data-winning="true"] .ball[data-hit="bonus"]{outline:3px dashed var(--blue);outline-offset:2px;transform:scale(1.06);z-index:1}\n'
    '.result-balls[data-winning="true"] .ball[data-hit="miss"]{opacity:.38;filter:saturate(.35) brightness(1.06)}\n'
    '.result-detail{display:block;margin-top:6px;color:var(--green);font-size:11px;font-weight:650;line-height:1.55}\n'
    '@media(forced-colors:active){.result-balls[data-winning="true"] .ball[data-hit="main"],.result-balls[data-winning="true"] .ball[data-hit="bonus"]{outline:3px solid Highlight;outline-offset:2px}.result-balls[data-winning="true"] .ball[data-hit="miss"]{opacity:1;filter:none}}',
)
replace_once(
    view,
    '<div class="review-grid"><section class="review-block" aria-labelledby="predictions-heading"><div class="section-heading"><h2 id="predictions-heading">이번 추첨, 추천번호 결과</h2></div><p class="review-note">추첨 전에 저장된 추천과 발표된 당첨번호를 비교합니다.</p>',
    '<div class="review-grid"><section class="review-block" aria-labelledby="predictions-heading"><div class="section-heading"><h2 id="predictions-heading">이번 추첨, 추천번호 결과</h2></div><p class="review-note">추첨 전에 저장된 추천과 발표된 당첨번호를 비교합니다. 당첨 게임은 본번호 일치를 테두리로, 보너스 일치를 점선 테두리로 강조하고 미일치 번호는 흐리게 표시합니다.</p>',
)

old = '''export function numberBalls(root, numbers, bonus=null) {
  root.replaceChildren();
  const valid=(numbers||[]).filter(n=>Number.isInteger(n)&&n>=1&&n<=45);
  const hasBonus=Number.isInteger(bonus)&&bonus>=1&&bonus<=45;
  root.setAttribute('role','img');root.setAttribute('aria-label',`번호 ${valid.join(', ')}${hasBonus?`, 보너스 ${bonus}`:''}`);
  const ball=n=>{const el=document.createElement('span');el.className='ball';el.dataset.band=String(Math.ceil(n/10));el.textContent=n;el.setAttribute('aria-hidden','true');return el;};
  valid.forEach(n=>root.append(ball(n)));
  if(hasBonus){const group=document.createElement('span');group.className='bonus-group';group.setAttribute('aria-hidden','true');const plus=document.createElement('span');plus.className='plus';plus.textContent='+';const wrap=document.createElement('span');wrap.className='bonus-label';const text=document.createElement('span');text.className='bonus-caption';text.textContent='보너스';wrap.append(ball(bonus),text);group.append(plus,wrap);root.append(group);}
}

export function ticketRows(root, games, limit=Infinity) {
  root.replaceChildren();root.setAttribute('role','list');
  if(!games?.length){root.removeAttribute('role');const empty=document.createElement('div');empty.className='empty';empty.innerHTML=`${icons.ticket}<strong>아직 보관한 복권이 없어요.</strong><p>복권 등록을 눌러 QR이나 사진으로 가져오세요.<br>번호를 직접 입력해도 좋아요.</p>`;root.append(empty);return;}
  for(const g of games.slice(0,limit)) {const row=document.createElement('div');row.className='ticket-row';row.setAttribute('role','listitem');const slot=document.createElement('span');slot.className='game-label';slot.textContent=g.slot||'';slot.setAttribute('aria-label',`${g.slot||''} 게임`);const nums=document.createElement('span');nums.className='ticket-balls';numberBalls(nums,g.numbers||g.recommended_numbers||[]);const prize=document.createElement('span');prize.className='prize';prize.textContent=g.prize||'추첨 대기';prize.dataset.winning=String(/^[1-5]등/.test(prize.textContent));row.append(slot,nums,prize);root.append(row);}
}
'''
new = '''export function numberBalls(root, numbers, bonus=null, outcome=null) {
  root.replaceChildren();
  const valid=(numbers||[]).filter(n=>Number.isInteger(n)&&n>=1&&n<=45);
  const hasBonus=Number.isInteger(bonus)&&bonus>=1&&bonus<=45;
  const winning=Number.isInteger(outcome?.prize_rank)&&outcome.prize_rank>=1&&outcome.prize_rank<=5;
  const matchedMain=new Set((outcome?.matched_main_numbers||[]).filter(n=>Number.isInteger(n)&&n>=1&&n<=45));
  const matchedBonus=winning&&Number.isInteger(outcome?.matched_bonus_number)?outcome.matched_bonus_number:null;
  root.dataset.winning=String(winning);
  const missed=winning?valid.filter(n=>!matchedMain.has(n)&&n!==matchedBonus):[];
  const aria=[`번호 ${valid.join(', ')}`];
  if(hasBonus)aria.push(`보너스 ${bonus}`);
  if(winning){
    if(matchedMain.size)aria.push(`당첨번호 일치 ${[...matchedMain].sort((a,b)=>a-b).join(', ')}`);
    if(matchedBonus!==null)aria.push(`보너스 일치 ${matchedBonus}`);
    if(missed.length)aria.push(`미일치 ${missed.join(', ')}`);
  }
  root.setAttribute('role','img');root.setAttribute('aria-label',aria.join('; '));
  const ball=n=>{const el=document.createElement('span');el.className='ball';el.dataset.band=String(Math.ceil(n/10));if(winning)el.dataset.hit=matchedMain.has(n)?'main':n===matchedBonus?'bonus':'miss';el.textContent=n;el.setAttribute('aria-hidden','true');return el;};
  valid.forEach(n=>root.append(ball(n)));
  if(hasBonus){const group=document.createElement('span');group.className='bonus-group';group.setAttribute('aria-hidden','true');const plus=document.createElement('span');plus.className='plus';plus.textContent='+';const wrap=document.createElement('span');wrap.className='bonus-label';const text=document.createElement('span');text.className='bonus-caption';text.textContent='보너스';wrap.append(ball(bonus),text);group.append(plus,wrap);root.append(group);}
}

export function ticketRows(root, games, limit=Infinity) {
  root.replaceChildren();root.setAttribute('role','list');
  if(!games?.length){root.removeAttribute('role');const empty=document.createElement('div');empty.className='empty';empty.innerHTML=`${icons.ticket}<strong>아직 보관한 복권이 없어요.</strong><p>복권 등록을 눌러 QR이나 사진으로 가져오세요.<br>번호를 직접 입력해도 좋아요.</p>`;root.append(empty);return;}
  for(const g of games.slice(0,limit)) {const row=document.createElement('div');row.className='ticket-row';row.setAttribute('role','listitem');const slot=document.createElement('span');slot.className='game-label';slot.textContent=g.slot||'';slot.setAttribute('aria-label',`${g.slot||''} 게임`);const nums=document.createElement('span');nums.className='ticket-balls result-balls';const isWinner=Number.isInteger(g.prize_rank)&&g.prize_rank>=1&&g.prize_rank<=5;numberBalls(nums,g.numbers||g.recommended_numbers||[],null,isWinner?g:null);const prize=document.createElement('span');prize.className='prize';prize.textContent=g.prize||'추첨 대기';prize.dataset.winning=String(isWinner);row.append(slot,nums,prize);root.append(row);}
}
'''
replace_once(view, old, new)

marker = 'export function renderRows(root, rows, headers, empty) {\n'
custom = '''export function renderPredictionRows(root, rows, empty) {
  root.replaceChildren();
  if(!rows.length){renderRows(root,[],['추첨 공식','번호','결과'],empty);return;}
  for(const row of rows){
    const tr=document.createElement('tr');tr.setAttribute('role','row');
    const isWinner=Number.isInteger(row.prize_rank)&&row.prize_rank>=1&&row.prize_rank<=5;tr.dataset.winning=String(isWinner);tr.className='prediction-row';
    const method=document.createElement('td');method.setAttribute('role','cell');method.dataset.label='추첨 공식';method.textContent=row.sensor_name||row.method_id||'—';
    const numberCell=document.createElement('td');numberCell.setAttribute('role','cell');numberCell.dataset.label='번호';const balls=document.createElement('span');balls.className='ticket-balls result-balls';numberBalls(balls,row.recommended_numbers||[],null,isWinner?row:null);numberCell.append(balls);
    if(isWinner){const detail=document.createElement('span');detail.className='result-detail';const main=(row.matched_main_numbers||[]).join(', ');detail.textContent=`일치 ${row.main_match_count}개${main?` · ${main}`:''}${row.bonus_match?` · 보너스 ${row.matched_bonus_number}`:''}`;numberCell.append(detail);}
    const result=document.createElement('td');result.setAttribute('role','cell');result.dataset.label='결과';const prize=document.createElement('span');prize.className='prize';prize.dataset.winning=String(isWinner);prize.textContent=row.prize||'판정 대기';result.append(prize);
    tr.append(method,numberCell,result);root.append(tr);
  }
}

''' + marker
replace_once(view, marker, custom)

core = 'custom_components/lotto_645/www/lotto-panel-core.js'
replace_once(
    core,
    "    this.rows('predictions',(w?.results||[]).filter(g=>g.source!=='purchased').map(g=>[g.sensor_name,(g.recommended_numbers||[]).join(', '),g.prize]));",
    "    renderPredictionRows(this.node('predictions'),(w?.results||[]).filter(g=>g.source!=='purchased'),['대조할 추천번호를 기다리고 있어요.','추첨 전에 저장한 추천이 있으면 결과 발표 후 표시됩니다.']);",
)

smoke = 'scripts/smoke_ticket_panel.py'
needle = """        assert '생성시각' in await page.locator('#reviewstatus').text_content()
        assert await page.locator('#game_a').input_value() == '2, 3, 4, 5, 6, 7'
        await page.locator('#close-editor').click()
"""
insert = """        assert '생성시각' in await page.locator('#reviewstatus').text_content()
        assert await page.locator('#game_a').input_value() == '2, 3, 4, 5, 6, 7'
        await page.evaluate(\"\"\"async()=>{
            const base=el._hass.callWS;
            el._hass.callWS=async msg=>({...await base(msg),result_round:1241,
                draw:{numbers:[7,24,30,31,32,42],bonus:9},result_verification:{status:'official_confirmed'},
                winning:{status:'evaluated',round:1241,winning_game_count:2,highest_prize:'2등',
                    winning_numbers:[7,24,30,31,32,42],bonus_number:9,results:[
                      {method_id:'public_ensemble',sensor_name:'공개 공식 · 종합 앙상블',source:'local',recommended_numbers:[7,13,15,24,38,42],prize:'5등',prize_rank:5,main_match_count:3,matched_main_numbers:[7,24,42],bonus_match:false,matched_bonus_number:null},
                      {method_id:'weighted_frequency',sensor_name:'공개 공식 · 가중 빈도',source:'local',recommended_numbers:[7,9,24,30,31,32],prize:'2등',prize_rank:2,main_match_count:5,matched_main_numbers:[7,24,30,31,32],bonus_match:true,matched_bonus_number:9}
                    ]}});
            await el.refreshStatus();
        }\"\"\")
        await page.locator('#tab-review').click()
        winning_rows=page.locator('#predictions tr[data-winning=\"true\"]')
        assert await winning_rows.count()==2
        first=winning_rows.nth(0)
        assert await first.locator('.ball[data-hit=\"main\"]').count()==3
        assert await first.locator('.ball[data-hit=\"miss\"]').count()==3
        label=await first.locator('.result-balls').get_attribute('aria-label')
        assert '당첨번호 일치 7, 24, 42' in label and '미일치 13, 15, 38' in label
        assert float(await first.locator('.ball[data-hit=\"miss\"]').first.evaluate('n=>getComputedStyle(n).opacity')) < 0.5
        assert await first.locator('.ball[data-hit=\"main\"]').first.evaluate(\"n=>getComputedStyle(n).outlineStyle==='solid'\")
        second=winning_rows.nth(1)
        assert await second.locator('.ball[data-hit=\"bonus\"]').count()==1
        assert await second.locator('.ball[data-hit=\"bonus\"]').evaluate(\"n=>getComputedStyle(n).outlineStyle==='dashed'\")
        assert '보너스 9' in await second.locator('.result-detail').text_content()
        await page.locator('#close-editor').click()
"""
replace_once(smoke, needle, insert)

changelog = Path('CHANGELOG.md')
text = changelog.read_text()
assert text.startswith('# Changelog\n\n')
entry = '''# Changelog

## 1.12.2 — 2026-09-14

- 추천 리뷰에서 당첨된 게임의 본번호 일치를 굵은 테두리로 강조하고, 보너스 일치는 점선 테두리로 구분합니다.
- 당첨 게임의 미일치 번호는 색을 유지하되 채도·투명도를 낮춰 맞은 번호가 즉시 보이도록 합니다.
- 번호 묶음의 접근성 라벨에 당첨 본번호·보너스·미일치 번호를 텍스트로 제공하고, 일치 개수 요약을 함께 표시합니다.
- 내 복권의 당첨 게임에도 같은 번호 강조 규칙을 적용하며 미당첨/추첨 대기 게임은 기존 표시를 유지합니다.

'''
changelog.write_text(entry + text[len('# Changelog\n\n'):])

Path('tests/test_winning_number_highlight.py').write_text('''from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VIEW=(ROOT/'custom_components/lotto_645/www/lotto-panel-view.js').read_text()
CORE=(ROOT/'custom_components/lotto_645/www/lotto-panel-core.js').read_text()


def test_winning_review_uses_exact_result_metadata_and_accessible_states():
    assert 'export function renderPredictionRows' in VIEW
    assert 'matched_main_numbers' in VIEW and 'matched_bonus_number' in VIEW
    assert "el.dataset.hit=matchedMain.has(n)?'main':n===matchedBonus?'bonus':'miss'" in VIEW
    assert '당첨번호 일치' in VIEW and '보너스 일치' in VIEW and '미일치' in VIEW
    assert "renderPredictionRows(this.node('predictions')" in CORE


def test_only_winning_games_are_dimmed_or_outlined():
    assert 'Number.isInteger(outcome?.prize_rank)' in VIEW
    assert '.result-balls[data-winning="true"] .ball[data-hit="main"]' in VIEW
    assert '.result-balls[data-winning="true"] .ball[data-hit="bonus"]' in VIEW
    assert '.result-balls[data-winning="true"] .ball[data-hit="miss"]' in VIEW
    assert 'opacity:.38' in VIEW
    assert '@media(forced-colors:active)' in VIEW
''')
