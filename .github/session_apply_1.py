"""Temporary plaintext source migration; no secrets, live HA, or network access."""
from pathlib import Path
import ast,json,re
R=Path(__file__).resolve().parents[1]; C=R/'custom_components/lotto_645'
p=C/'methods.py';s=p.read_text(); tree=ast.parse(s)
retired={'METHOD_PHASE_RESIDUAL','METHOD_TRANSITION_GAP','METHOD_MULTISCALE_RESONANCE','METHOD_TRIPLET_COOCCURRENCE','METHOD_CYCLE_RHYTHM'}
node=next(n for n in tree.body if isinstance(n,ast.AnnAssign) and getattr(n.target,'id','')=='METHODS')
lines=s.splitlines(keepends=True); labels={}
constants={n.target.id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.AnnAssign) and isinstance(n.value,ast.Constant)}
for call in reversed(node.value.elts):
 if call.args[0].id in retired:
  labels[constants[call.args[0].id]]=ast.literal_eval(call.args[1])
  del lines[call.lineno-1:call.end_lineno]
s=''.join(lines)
s=s.replace('METHODS_BY_ID: Final =', 'RETIRED_METHOD_LABELS: Final = '+repr(labels)+'\n\nMETHODS_BY_ID: Final =')
s=s.replace('    METHOD_UNIFORM_FLOYD,\n    METHOD_UNIFORM_REJECTION,\n    METHOD_UNIFORM_SEQUENTIAL,\n    METHOD_CALIBRATED_STRATIFIED,\n','')
s=s.replace('def method_selector_options() -> list[dict[str, str]]:', '''# Same-distribution implementations and frequency variants belong in advanced
# settings. Saved IDs remain stable; existing selections are not silently merged.
ADVANCED_METHOD_IDS: Final = (
    METHOD_UNIFORM_FLOYD, METHOD_UNIFORM_REJECTION, METHOD_UNIFORM_SEQUENTIAL,
    METHOD_CALIBRATED_STRATIFIED, METHOD_UNIFORM_COMBINATION_RANK,
    METHOD_HOT_NUMBERS, METHOD_RECENCY_DECAY,
)
BASIC_METHOD_IDS: Final = tuple(key for key in METHODS_BY_ID if key not in ADVANCED_METHOD_IDS)


def method_selector_options(*, advanced: bool = False) -> list[dict[str, str]]:''')
s=s.replace('        for method in METHODS\n    ]\n\n\ndef method_catalog', '        for method in METHODS\n        if (method.method_id in ADVANCED_METHOD_IDS) == advanced\n    ]\n\n\ndef method_catalog')
s=s.replace('            "category": method.category,\n', '            "category": method.category,\n            "selection_group": "advanced" if method.method_id in ADVANCED_METHOD_IDS else "basic",\n')
s=s.replace('"공개 공식 · 핫넘버"','"빈도 프리셋 · 핫넘버"').replace('"공개 공식 · 지수감쇠 최근성"','"빈도 프리셋 · 지수감쇠 최근성"')
s=s.replace('"공개 공식 · 종합 앙상블"','"복합 공식 · 공개 지표 종합"').replace('"추천 공개 분석식",','"공개 분석식",').replace('합의 점수로 결합한 권장안입니다.', '복합 선호 점수로 결합합니다.')
p.write_text(s)
p=C/'coordinator.py';s=p.read_text();start=s.index('        configured = self.configured_method_ids',s.index('    def selected_method_ids'));end=s.index('\n    @property',start)
s=s[:start]+'''        configured = self.configured_method_ids
        active = tuple(key for key in configured if self.saju_profile_ready or key != METHOD_MYUNGRI_HETU)
        # Retiring profiles must not make startup fail. The aggregate will wait
        # for two available sources, without silently adding purchase games.
        return active
''' + s[end:];p.write_text(s)
p=C/'analysis.py';s=p.read_text();old='''    if (METHOD_SELECTED_MEDIAN in selected_method_ids
            and len(consensus_source_ids(selected_method_ids)) < 2):
        raise ValueError("선택 공식 중앙값은 다른 로컬 추첨 공식을 2개 이상 함께 선택해야 합니다")
''';assert old in s;s=s.replace(old,'');p.write_text(s)
p=C/'config_flow.py';s=p.read_text().replace('    METHODS_BY_ID,','    METHODS_BY_ID,\n    ADVANCED_METHOD_IDS,')
s=s.replace('def _method_selector() -> selector.SelectSelector:', 'def _method_selector(*, advanced: bool = False) -> selector.SelectSelector:').replace('options=method_selector_options(),','options=method_selector_options(advanced=advanced),')
s=s.replace('vol.Required(CONF_SELECTED_METHODS, default=selected): _method_selector(),', '''vol.Required(CONF_SELECTED_METHODS, default=[key for key in selected if key not in ADVANCED_METHOD_IDS]): _method_selector(),
            vol.Optional("advanced_methods", default=[key for key in selected if key in ADVANCED_METHOD_IDS]): _method_selector(advanced=True),''')
s=s.replace('''                normalized = _normalize_submitted_methods(
                    user_input.get(CONF_SELECTED_METHODS)
                )''','''                main = user_input.get(CONF_SELECTED_METHODS, [])
                advanced = user_input.get("advanced_methods", [])
                combined = list(main) + list(advanced) if isinstance(main, (list, tuple)) and isinstance(advanced, (list, tuple)) else None
                normalized = _normalize_submitted_methods(combined)''')
s=s.replace('pending[CONF_SELECTED_METHODS] = list(normalized)','pending[CONF_SELECTED_METHODS] = list(normalized)\n                    pending.pop("advanced_methods", None)');p.write_text(s)
p=C/'ticket_panel.py';s=p.read_text().replace('MIN_TARGET_ROUND, MAX_SEED, HistoricalValidationError','MIN_TARGET_ROUND, HistoricalValidationError')
s=s.replace('from .methods import METHODS_BY_ID', 'from .methods import METHODS_BY_ID, RETIRED_METHOD_LABELS')
s=s.replace("else 'Home Assistant AI 추천' if method_id == AI_METHOD_ID else method_id", "else 'Home Assistant AI 추천' if method_id == AI_METHOD_ID else RETIRED_METHOD_LABELS.get(method_id, method_id)")
s=s.replace("                'default_seed': 0,\n",'').replace("    vol.Optional('seed', default=0): vol.All(_strict_int, vol.Range(min=0, max=MAX_SEED)),\n",'').replace("msg['method_ids'], msg['seed'])","msg['method_ids'])");p.write_text(s)
p=C/'panel_metadata.py';s=p.read_text().replace('from .methods import method_catalog','from .methods import method_catalog, RETIRED_METHOD_LABELS')
s=s.replace('return {"method_catalog": catalog,', 'return {"archived_method_catalog": [{"method_id": key, "name": label + " · 종료된 공식"} for key, label in RETIRED_METHOD_LABELS.items()], "method_catalog": catalog,');p.write_text(s)
p=C/'www/lotto-panel-tools.js';s=p.read_text().replace('(data.method_catalog || []).filter', '[...(data.method_catalog || []), ...(data.archived_method_catalog || [])].filter');p.write_text(s)
p=C/'historical_validation.py';s=p.read_text().replace('import random','import secrets').replace('MAX_SEED = 2**32 - 1\n','').replace('from .analysis import build_analysis','from .analysis import build_analysis\nfrom .consensus import refresh_consensus, valid_ticket')
s=s.replace('''    seed: int = 0, saju_profile: dict[str, Any] | None = None,
''','''    saju_profile: dict[str, Any] | None = None, *, previous_tickets: Sequence[tuple[int, ...]] = (), rng=None,
''')
s=s.replace('''    Fixed seeds provide repeatable simulations, not production CSPRNG draws.
    The seed also selects the heuristic candidate variant; it is never derived
    from target/future numbers or a live generation counter. Call in executor.''','''    Every production request uses fresh OS randomness. Only unit tests may
    inject a random generator; no seed is accepted or returned by the UI/API.
    Previous simulations for this target can be excluded without reading any
    target numbers or live recommendation state. Call in executor.''')
s=s.replace('''    if type(seed) is not int or not 0 <= seed <= MAX_SEED:
        raise HistoricalValidationError('invalid_seed', f'검증 시드는 0~{MAX_SEED} 사이의 정수여야 합니다.')
''','')
s=s.replace('    rng = random.Random(seed)', '''    rng = rng if rng is not None else secrets.SystemRandom()
    generation_variant = rng.randrange(1, 2**32)
    blocked = set()
    if len(previous_tickets) > len(METHODS_BY_ID) + 1:
        raise HistoricalValidationError('invalid_previous', '이전 검증 결과가 올바르지 않습니다.')
    for value in previous_tickets:
        ticket = valid_ticket(value)
        if ticket is None:
            raise HistoricalValidationError('invalid_previous', '이전 검증 결과가 올바르지 않습니다.')
        blocked.add(ticket)''')
s=s.replace('analysis = build_analysis(training, local_ids, seed, deepcopy(saju_profile), rng=rng)', '''analysis = build_analysis(training, local_ids, generation_variant, deepcopy(saju_profile),
                                  excluded_combinations=tuple(blocked), rng=rng)
        if METHOD_SELECTED_MEDIAN in local_ids and blocked:
            analysis = refresh_consensus(analysis, local_ids, training, excluded_combinations=blocked)''')
s=s.replace('ticket = make_ai_ticket(training, analysis.recommendations, rng=rng)', 'ticket = make_ai_ticket(training, analysis.recommendations, rng=rng, excluded_combinations=blocked)')
s=s.replace("'generated_at': datetime.now(UTC).isoformat(), 'seed': seed,\n        'rng': 'seeded_simulation_prng', 'generation_sequence': seed,", "'generated_at': datetime.now(UTC).isoformat(),\n        'rng': 'system_csprng' if isinstance(rng, secrets.SystemRandom) else 'injected_test_rng',\n        'previous_simulation_excluded': bool(blocked),");p.write_text(s)
p=C/'consensus.py';s=p.read_text().replace('*, updated_at: str | None = None,','*, updated_at: str | None = None, excluded_combinations: Iterable[tuple[int, ...]] = (),')
s=s.replace('    signature = sha256', '    extra_blocked = set(excluded_combinations)\n    signature = sha256').replace("'sources': sorted(sources.items()), 'past': sorted(past),", "'sources': sorted(sources.items()), 'past': sorted(past | extra_blocked),").replace('past | set(sources.values()))', 'past | set(sources.values()) | extra_blocked)')
s=s.replace('''        # Previous consensus tickets are NOT excluded: this is a derived value,
        # not an independently regenerated random game.''','''        # Live consensus keeps identical inputs stable. An isolated historical
        # rerun may explicitly exclude its prior simulation, never live records.''');p.write_text(s)
p=C/'ai_formula.py';s=p.read_text().replace('previous=None, *, rng=None):','previous=None, *, rng=None, excluded_combinations=()):').replace('    if previous is not None:', '    blocked.update(excluded_combinations)\n    if previous is not None:');p.write_text(s)
p=C/'historical_validation_runtime.py';s=p.read_text().replace("TIMEOUT_SECONDS = 180", "TIMEOUT_SECONDS = 180\nLAST_KEY = 'lotto_645_last_historical_validation'").replace('method_ids, seed=0):','method_ids):')
s=s.replace('    worker = hass.async_add_executor_job', '''    # One bounded prior batch per entry, held only in memory. A reload or target
    # change discards it. This is not a live recommendation/review cache.
    previous = hass.data.get(LAST_KEY, {}).get(key)
    blocked = previous[2] if previous and previous[0] is coordinator and previous[1] == target_round else ()
    worker = hass.async_add_executor_job''')
s=s.replace('run_historical_validation, history, target_round, tuple(method_ids), seed, profile,', 'run_historical_validation, history, target_round, tuple(method_ids), profile, previous_tickets=blocked,')
s=s.replace('''            return await asyncio.shield(worker)''','''            result = await asyncio.shield(worker)
        hass.data.setdefault(LAST_KEY, {})[key] = (coordinator, target_round, tuple(
            tuple(row['recommended_numbers']) for row in result['results']
            if row.get('generation_status') == 'generated'
        ))
        return result''');p.write_text(s)
p=C/'__init__.py';s=p.read_text().replace('    if unloaded:\n', '''    if unloaded:
        from .historical_validation_runtime import LAST_KEY
        hass.data.get(LAST_KEY, {}).pop(entry.entry_id, None)
''');p.write_text(s)
p=C/'www/lotto-panel-view.js';s=p.read_text();s=re.sub(r'<div><label for="validation-seed">.*?</div>(?=</div>)','',s,count=1)
s=s.replace('const matchedMain=new Set((outcome?.matched_main_numbers||[]).filter(n=>Number.isInteger(n)&&n>=1&&n<=45));', '''const evaluated=Number.isInteger(outcome?.main_match_count)&&Array.isArray(outcome?.matched_main_numbers)&&outcome.generation_status!=='unavailable';
  const matchedMain=new Set((outcome?.matched_main_numbers||[]).filter(n=>valid.includes(n)));''')
s=s.replace('const matchedBonus=winning&&Number.isInteger(outcome?.matched_bonus_number)?outcome.matched_bonus_number:null;', 'const matchedBonus=evaluated&&outcome?.bonus_match===true&&valid.includes(outcome?.matched_bonus_number)?outcome.matched_bonus_number:null;')
s=s.replace('root.dataset.winning=String(winning);','root.dataset.winning=String(winning);root.dataset.evaluated=String(evaluated);root.dataset.hasMatches=String(matchedMain.size>0||matchedBonus!==null);')
s=s.replace('const missed=winning?', 'const missed=evaluated?').replace('  if(winning){','  if(evaluated){').replace('if(winning)el.dataset.hit=', 'if(evaluated)el.dataset.hit=')
s=s.replace('null,isWinner?g:null)', 'null,g)').replace('null,isWinner?row:null)', 'null,row)').replace('if(isWinner){const detail=', 'if(balls.dataset.evaluated===\'true\'){const detail=')
s=s.replace('.result-balls[data-winning="true"]', '.result-balls[data-evaluated="true"]').replace('outline:3px solid var(--green);outline-offset:3px', 'outline:3px solid var(--green);outline-offset:-3px').replace('outline:3px dashed var(--green);outline-offset:3px', 'outline:3px dashed var(--green);outline-offset:-3px')
marker='\n</style>';assert marker in s
s=s.replace(marker, '''
/* Match marks stay inside their ball. Gaps survive narrow-table overrides. */
.ticket-balls.result-balls{gap:8px;row-gap:8px;flex-wrap:wrap;min-width:0;max-width:100%;box-sizing:border-box}
.ticket-balls.result-balls .ball[data-hit="main"]{outline:3px solid var(--green);outline-offset:-3px;box-shadow:none}
.ticket-balls.result-balls .ball[data-hit="bonus"]{outline:3px dashed var(--green);outline-offset:-3px;box-shadow:none}
.ticket-balls.result-balls[data-has-matches="false"] .ball{opacity:1;filter:none}
.mobile-table .result-detail{grid-column:2;white-space:normal;overflow-wrap:anywhere}
@media(forced-colors:active){.ticket-balls.result-balls .ball[data-hit="main"],.ticket-balls.result-balls .ball[data-hit="bonus"]{outline-color:Highlight}.ticket-balls.result-balls .ball{opacity:1;filter:none}}
</style>''',1);p.write_text(s)
p=C/'www/lotto-panel-validation.js';s=p.read_text().replace("for (const id of ['validation-round', 'validation-seed']) this.node(id).oninput", "for (const id of ['validation-round']) this.node(id).oninput").replace("this.node('validation-seed').value = '0'; ",'')
s=s.replace("const round = Number(this.node('validation-round').value), seed = Number(this.node('validation-seed').value), method_ids = this.ids();", "const round = Number(this.node('validation-round').value), method_ids = this.ids();").replace('{round, method_ids, seed}', '{round, method_ids}').replace(' · 시드 ${data.seed}', '').replace('검증용 시드 난수', '매 실행 새 번호 생성')
s=s.replace('''      for (const method of catalog) {''', '''      const advanced = document.createElement('details'); advanced.className = 'validation-advanced';
      const heading = document.createElement('summary'); heading.textContent = '고급 선택 · 균등 알고리즘과 빈도 프리셋'; advanced.append(heading);
      for (const method of catalog) {''')
s=s.replace('label.append(input, text); root.append(label);', "label.append(input, text); (method.selection_group === 'advanced' ? advanced : root).append(label);\n        if (input.checked && method.selection_group === 'advanced') advanced.open = true;")
s=s.replace('''      if (prior) this.changed();''','''      if (advanced.children.length > 1) root.append(advanced);
      if (prior) this.changed();''').replace('.validation-choice{', '.validation-advanced{grid-column:1/-1}\n.validation-choice{');p.write_text(s)
for p in [C/'strings.json',*sorted((C/'translations').glob('*.json'))]:
 data=json.loads(p.read_text()); step=data['options']['step']['recommendations'];ko=p.stem=='ko'
 step['data']['advanced_methods']='고급 선택 · 균등 알고리즘 / 빈도 프리셋 (선택 사항)' if ko else 'Advanced: uniform algorithms / frequency presets (optional)'
 step['data_description']['advanced_methods']='기본 공식과 목적이 같은 구현·세부 설정입니다. 기존 선택은 유지됩니다. 별도의 당첨 전략이나 확률 향상을 뜻하지 않습니다.' if ko else 'Alternative implementations/presets of existing families, not better winning strategies. Existing selections are preserved.'
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
for p in [C/'const.py',C/'manifest.json',*(C/'www').glob('lotto-panel*.js')]:
 s=p.read_text().replace('1.14.0','1.15.0');p.write_text(s)
