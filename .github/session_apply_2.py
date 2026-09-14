"""Temporary reviewed regression/documentation migration, applied after phase 1."""
from pathlib import Path
import json,re,subprocess,ast,importlib.util,sys
R=Path(__file__).resolve().parents[1];C=R/'custom_components/lotto_645'
for rel in ['custom_components/lotto_645/coordinator.py','custom_components/lotto_645/www/lotto-panel-design.js']:
 (R/rel).write_bytes(subprocess.check_output(['git','show','HEAD:'+rel],cwd=R))
p=C/'www/lotto-panel-shell.js';s=p.read_text().replace('./lotto-panel-design.js?v=1.15.0','./lotto-panel-design.js?v=1.14.0');p.write_text(s)
p=C/'www/lotto-panel-view.js';s=p.read_text().replace('outline-offset:2px;transform:scale(1.06)','outline-offset:-3px;transform:none').replace('.ticket-balls.result-balls{gap:8px;', '.ticket-balls.result-balls,.mobile-table td .ticket-balls.result-balls{gap:8px;').replace('outline:3px dashed var(--green);outline-offset:-3px;box-shadow:none','outline:3px dashed var(--blue);outline-offset:-3px;box-shadow:none').replace('Array.isArray(outcome?.matched_main_numbers)&&outcome.generation_status', 'outcome.main_match_count>=0&&outcome.main_match_count<=6&&Array.isArray(outcome?.matched_main_numbers)&&outcome.generation_status');p.write_text(s)
p=C/'historical_validation_runtime.py';s=p.read_text();a=s.index('    def finished(future):');b=s.index('    worker.add_done_callback',a)
s=s[:a]+'''    def finished(future):
        if not future.cancelled() and future.exception() is None:
            result = future.result()
            if (result.get('mode') == 'historical_validation'
                    and getattr(coordinator.entry, 'runtime_data', coordinator) is coordinator):
                hass.data.setdefault(LAST_KEY, {})[key] = (coordinator, target_round, tuple(
                    tuple(row['recommended_numbers']) for row in result['results']
                    if row.get('generation_status') == 'generated'
                ))
        if workers.get(key) is future:
            workers.pop(key, None)

''' + s[b:]
a=s.index('            result = await asyncio.shield(worker)');b=s.index('    except TimeoutError',a)
s=s[:a]+'            return await asyncio.shield(worker)\n'+s[b:];p.write_text(s)
p=R/'tests/test_historical_validation.py';s=p.read_text().replace('repeatability','fresh regeneration').replace('rows,61,ids,17)', 'rows,61,ids,rng=random.Random(17))').replace('changed,61,ids,17)', 'changed,61,ids,rng=random.Random(17))')
s=s.replace("assert 'excluded_combinations' not in captured['options']", "assert captured['options']['excluded_combinations']==()").replace("assert captured['nonce']==0", "assert captured['nonce']>0")
a=s.index('def test_minimum_valid_round_and_seed_replay');b=s.index("@pytest.mark.parametrize('ids'",a)
s=s[:a]+'''def test_minimum_valid_round_and_test_only_rng_injection():
    rows=history();ids=('uniform_floyd',)
    a=v.run_historical_validation(rows,31,ids,rng=random.Random(5))
    b=v.run_historical_validation(rows,31,ids,rng=random.Random(5))
    c=v.run_historical_validation(rows,31,ids,rng=random.Random(6))
    assert a['training_last_round']==30 and numbers(a)==numbers(b)
    assert numbers(a)!=numbers(c)
    assert a['rng']=='injected_test_rng' and 'seed' not in a
    assert a['generated_at']>a['draw']['draw_date']


def test_fresh_rng_and_previous_simulation_exclusion():
    rows=history();ids=('uniform_fisher_yates','ac_range_filter','selected_median_consensus','home_assistant_ai')
    prior=()
    for _ in range(5):
        result=v.run_historical_validation(rows,61,ids,previous_tickets=prior)
        current=tuple(tuple(r['recommended_numbers']) for r in result['results'] if r['generation_status']=='generated')
        assert set(current).isdisjoint(prior)
        assert len(current)==len(set(current))
        assert result['rng']=='system_csprng' and 'seed' not in result
        prior=current


def test_previous_exclusion_changes_even_identical_test_rng():
    rows=history();ids=('weighted_frequency', 'uniform_floyd')
    a=v.run_historical_validation(rows,61,ids,rng=random.Random(15))
    prior=tuple(tuple(r['recommended_numbers']) for r in a['results'])
    b=v.run_historical_validation(rows,61,ids,previous_tickets=prior,rng=random.Random(15))
    assert set(tuple(r['recommended_numbers']) for r in b['results']).isdisjoint(prior)


@pytest.mark.parametrize('bad', [(1,2,3), (1,1,2,3,4,5), (True,2,3,4,5,6)])
def test_malformed_prior_simulations_fail_closed(bad):
    with pytest.raises(v.HistoricalValidationError):
        v.run_historical_validation(history(),61,('uniform_floyd',),previous_tickets=(bad,))


''' + s[b:]
s=s.replace("rt.async_validate_history(hass,obj,61,('uniform_floyd',),9)","rt.async_validate_history(hass,obj,61,('uniform_floyd',))")
s=s.replace("assert 'sequence !== this.sequence' in js", "assert 'sequence !== this.sequence' in js\n    assert 'validation-seed' not in js and 'data.seed' not in js\n    assert \"vol.Optional('seed'\" not in endpoint")
s+='''\n\ndef test_runtime_two_clicks_exclude_previous_and_keep_one_bounded_batch():
    async def run():
        loop=asyncio.get_running_loop()
        hass=SimpleNamespace(data={},async_add_executor_job=lambda fn:loop.run_in_executor(None,fn))
        obj=SimpleNamespace(entry=SimpleNamespace(entry_id='one'),history=history(),saju_profile_ready=False)
        a=await rt.async_validate_history(hass,obj,61,('uniform_floyd',))
        b=await rt.async_validate_history(hass,obj,61,('uniform_floyd',))
        assert numbers(a)!=numbers(b) and b['previous_simulation_excluded']
        c=await rt.async_validate_history(hass,obj,62,('uniform_floyd',))
        assert not c['previous_simulation_excluded']
        assert len(hass.data[rt.LAST_KEY])==1
        replacement=SimpleNamespace(entry=obj.entry,history=obj.history,saju_profile_ready=False)
        d=await rt.async_validate_history(hass,replacement,62,('uniform_floyd',))
        assert not d['previous_simulation_excluded']
    asyncio.run(run())
''';p.write_text(s)
p=R/'tests/test_winning_number_highlight.py';s=p.read_text().replace('test_only_winning_games_are_dimmed_or_outlined','test_all_evaluated_games_are_marked_without_awarding_losing_games').replace('[data-winning="true"]','[data-evaluated="true"]')
s+='''\n\ndef test_marks_do_not_expand_into_neighbor_cells():
    assert 'transform:scale(1.06)' not in VIEW
    assert 'outline-offset:-3px' in VIEW
    assert '.mobile-table td .ticket-balls.result-balls{gap:8px' in VIEW
    assert "null,isWinner?row:null" not in VIEW
    assert "null,isWinner?g:null" not in VIEW
''';p.write_text(s)
p=R/'tests/test_analysis_engine.py';s=p.read_text().replace('len(methods.METHODS) == 24','len(methods.METHODS) == 19').replace('len(methods.PUBLIC_METHOD_IDS) == 12','len(methods.PUBLIC_METHOD_IDS) == 10').replace('methods.METHOD_PHASE_RESIDUAL','methods.METHOD_WEIGHTED_FREQUENCY');p.write_text(s)
p=R/'tests/test_panel_metadata.py';s=p.read_text().replace('== 24','== 19').replace('== 25','== 20').replace("{'method_catalog', 'draw_schedule'}","{'method_catalog', 'archived_method_catalog', 'draw_schedule'}").replace("assert set(item) == {'method_id','name','category','description','requirements'}","assert {'method_id','name','category','description','requirements'} <= set(item)");p.write_text(s)
p=R/'tests/test_method_docs.py';s=p.read_text().replace('24종','19종').replace('== 24','== 19').replace("== {m['id'] for m in CATALOG}","== {m['id'] for m in CATALOG} | {'cycle_rhythm','phase_residual_graph','transition_gap_phase','multiscale_resonance','triplet_cooccurrence'}");p.write_text(s)
p=R/'scripts/smoke_historical_validation.py';s=p.read_text().replace("assert valid['seed']==0 and valid['round']==61","assert 'seed' not in valid and valid['round']==61").replace("[('round',True),('round',31.5),('seed',False),('seed',-1)]","[('round',True),('round',31.5),('seed',0),('seed',-1)]").replace("'method_ids':['uniform_floyd'],'seed':0,key:bad}","'method_ids':['uniform_floyd'],key:bad}").replace("'method_ids':['uniform_floyd','uniform_fisher_yates','selected_median_consensus','home_assistant_ai'],\n            'seed':10}","'method_ids':['uniform_floyd','uniform_fisher_yates','selected_median_consensus','home_assistant_ai']}");p.write_text(s)
p=R/'scripts/smoke_panel_validation.py';s=p.read_text().replace('default_seed:0,','').replace("component_version:'1.14.0',seed:0,","component_version:'1.15.0',").replace("req['seed']==0", "'seed' not in req")
s=s.replace("    assert await page.locator('#validation-round').input_value()=='1241'", "    assert await page.locator('#validation-round').input_value()=='1241'\n    assert await page.locator('#validation-seed').count()==0")
s=s.replace("await page.wait_for_function('validationCalls.length===2 && !el._historicalValidation.busy')", "await page.wait_for_function('validationCalls.length===2 && !el._historicalValidation.busy')\n    assert 'seed' not in await page.evaluate('validationCalls[1]')");p.write_text(s)
(R/'tests/test_formula_cleanup.py').write_text('''"""Current catalogue and legacy-safe option projection."""
import importlib.util
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cleanup_methods',ROOT/'custom_components/lotto_645/methods.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)


def test_retired_profiles_are_not_selectable_or_generated():
    assert len(m.RETIRED_METHOD_LABELS)==5
    assert not set(m.RETIRED_METHOD_LABELS)&set(m.METHODS_BY_ID)
    assert m.normalize_method_ids(list(m.RETIRED_METHOD_LABELS))==m.DEFAULT_METHOD_IDS
    assert m.normalize_method_ids(['cycle_rhythm','ac_range_filter','uniform_floyd'])==('ac_range_filter','uniform_floyd')


def test_base_menu_and_advanced_variants_form_exact_catalogue():
    basic={row['value'] for row in m.method_selector_options()}
    advanced={row['value'] for row in m.method_selector_options(advanced=True)}
    assert len(basic)==12 and len(advanced)==7
    assert basic.isdisjoint(advanced) and basic|advanced==set(m.METHODS_BY_ID)
    assert m.DEFAULT_METHOD_IDS==('uniform_fisher_yates',)
    assert m.METHOD_MYUNGRI_HETU in basic and m.METHOD_SELECTED_MEDIAN in basic
    assert m.METHOD_CALIBRATED_STRATIFIED in advanced
    assert '권장' not in m.METHODS_BY_ID[m.METHOD_PUBLIC_ENSEMBLE].description
''')
spec=importlib.util.spec_from_file_location('docs_current_methods',C/'methods.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
for p in [R/'README.md',R/'docs/FORMULAS.md']:
 s=p.read_text();prefix='docs/methods/' if p.name=='README.md' else 'methods/'
 pat=r'\d+\. \[[^\]]+\]\('+re.escape(prefix)+r'[a-z_]+\.md\)'
 matches=list(re.finditer(pat,s));assert len(matches)==24
 lines='\n'.join(f'{i}. [{mth.label}]({prefix}{mth.method_id}.md)' for i,mth in enumerate(m.METHODS,1))
 s=s[:matches[0].start()]+lines+s[matches[-1].end():]
 s=s.replace('24종','19종').replace('24개','19개').replace('검증용 공식 선택과 시드는 실제 통합 설정을 바꾸지 않습니다.','버튼을 누를 때마다 새 번호를 생성하며 별도의 난수 설정은 없습니다. 검증용 공식 선택은 실제 통합 설정을 바꾸지 않습니다.').replace('계산 경계·시드·합의·AI','계산 경계·새 번호 생성·합의·AI')
 s=s.replace('부분 Fisher–Yates, Floyd, 중복거부, 순차 포함, CCSS입니다.', '부분 Fisher–Yates 한 개입니다. 기본 메뉴는 12개이며 대체 균등 알고리즘 5개와 빈도 프리셋 2개는 고급 선택으로 모았습니다.').replace('기존 사용자가 저장한 공식 선택은 자동으로 바꾸지 않습니다.','종료된 5개 공식은 새 생성에서 제외하며, 나머지 기존 선택·저장 ID·과거 결과는 유지합니다.');p.write_text(s)
for p in (R/'docs/methods').glob('*.md'):
 s=p.read_text().replace('24개 공식 목록','추첨 공식 목록').replace('추첨-공식-24종','추첨-공식-19종')
 if p.stem in m.METHODS_BY_ID:s=re.sub(r'^# .*', '# '+m.METHODS_BY_ID[p.stem].label,s,count=1)
 else:s=s.replace('\n\n','\n\n> v1.15.0부터 새 생성에서 제외된 공식입니다. 이전 결과의 설명을 위해 이 문서를 보존합니다.\n\n',1)
 p.write_text(s);(C/'www/methods'/p.name).write_text(s)
p=R/'docs/AI_RECOMMENDATION.md';s=p.read_text().replace('24종','19종').replace('24개','19개');p.write_text(s);(C/'www/methods/home_assistant_ai.md').write_text(s)
p=R/'docs/HISTORICAL_VALIDATION.md';s=p.read_text();a=s.index('## 재현 정보와 해석');b=s.index('이 기능은 **현재 버전',a)
s=s[:a]+'''## 매 실행 새 번호와 해석

버튼을 누를 때마다 운영체제 난수로 새 후보를 생성합니다. 사용자가 입력하거나 고정할 난수 설정은 없습니다. 점수형 공식도 상위 후보를 순환하며 직전 같은 회차의 검증 조합은 다시 선택하지 않습니다. 난수 공식·AI 번호 생성부·합의 결과에도 이전 검증 제외를 적용합니다. 불가능한 합의는 기준을 바꾸지 않고 생성 불가로 표시합니다.

번호 일부가 이전과 겹칠 수는 있지만 직전 검증의 여섯 번호 조합을 그대로 재사용하지 않습니다. 이 제외 목록은 통합별 직전 한 배치만 메모리에 보관하고, 다른 회차를 검증하거나 통합을 다시 불러오면 초기화됩니다. 실제 추천·구매·리뷰 저장소와 분리됩니다.

화면에 기준 회차, 사용 이력 수, 실행 버전, 생성시각과 입력 이력의 SHA-256을 제공합니다. 추가 설정 없이 회차와 공식만 선택하면 됩니다.

''' +s[b:]
s=s.replace('여러 시드·공식을','여러 번 공식을').replace('공식·회차·시드 엄격 검증','공식·회차 엄격 검증 및 종료된 공식 거부').replace('재현, 최소 이력','새 결과·직전 조합 제외, 테스트 난수 주입, 최소 이력');p.write_text(s)
p=R/'docs/FORMULA_SELECTION_REVIEW.md';s=p.read_text().replace('# 공개 공식 추가와 기존 공식 정리 검토','# 공개 공식 추가와 기존 공식 정리 검토\n\n## v1.15.0 적용 결과\n\n이전 검토에서 권고했던 재등장 주기·독창 패턴 3개·삼중 동반출현을 신규 생성 목록에서 제거했습니다. 활성 엔진 19개 중 기본 선택은 12개, 중복 균등 구현 5개와 빈도 프리셋 2개는 고급 선택으로 통합했습니다. 기존 고급 선택은 그대로 읽고 저장합니다. 새 설치 기본값은 대표 균등 공식 한 개입니다. 종료된 공식의 과거 리뷰·구매 기록·문서는 삭제하지 않습니다. 원본 부족 시 중앙값은 대기하며 게임을 자동 추가하지 않습니다.\n\n이하 내용은 v1.13.0 당시 검토 기록으로 보존합니다.');p.write_text(s)
p=R/'CHANGELOG.md';s=p.read_text().replace('# Changelog\n\n', '''# Changelog

## 1.15.0 — 2026-09-14

- 검증 화면의 시드 입력·고정 재현 옵션을 제거하고, 버튼을 누를 때마다 새 검증번호를 생성합니다. 직전 같은 회차 검증 조합의 재사용을 난수·점수·AI 생성부·합의 경로에서 차단합니다.
- 종료 대상 5개 공식(재등장 주기, 독창 패턴 3개, 삼중 동반출현)을 신규 생성에서 제거합니다. 기본 메뉴 12개와 고급 균등 알고리즘/빈도 프리셋 7개로 정리하며 기존 고급 선택과 과거 기록은 보존합니다.
- 일치번호 강조선은 공 내부에 배치하고 공 사이 간격을 확보합니다. 좁은 화면은 줄바꿈하며 인접 번호·레이블·결과 영역을 침범하지 않습니다.
- 본번호 1~2개 및 보너스만 일치해도 표시합니다. 미당첨/등수 판정은 바꾸지 않으며 추첨 대기·생성 불가에는 강조하지 않습니다.
- 원본 부족한 중앙값은 통합 전체 실패 대신 대기합니다. AC·개인 사주·원본 변경에 따른 중앙값 자동 집계·AI 백엔드 생성 경계를 유지합니다.
- 검증 요청은 관리자 전용·단일 실행·미래 데이터 차단을 유지하며 실제 추천/리뷰/구매 파일을 변경하지 않습니다. 이전 검증 한 배치만 메모리에 보관합니다.

''',1);p.write_text(s)
