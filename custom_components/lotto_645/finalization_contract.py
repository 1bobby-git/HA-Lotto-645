"""Bounded public ticket-set DTOs; never store provider/debug or private fields."""
from __future__ import annotations
from copy import deepcopy
import json
import re
from .service_contract import ContractError, identifier, numbers, positive, timestamp

CAPABILITY='post_generation_ticket_set_v1'
FINALIZER_ID='candidate_covering_recombination'
INPUT_STATES={'not_configured','waiting_sources','blocked','ready','closed'}
JOB_STATES={'queued','running','completed','failed','cancelled'}
READINESS_FIELDS=('capability','input_state','source_batch_id','source_selection_revision','source_core_version',
 'source_context_hash','source_completed_at','target_round','based_on_round','expected_count','completed_count',
 'pending_count','source_formula_ids','input_snapshot_hash','candidate_numbers','candidate_count','requested_game_count',
 'min_game_count','max_game_count','default_game_count','default_requires_choice','newer_input_available',
 'latest_complete_batch','draw_cutoff','evaluation_mode','job_status')
RESULT_FIELDS=('contract_version','capability','execution_stage','trigger','output_kind','finalizer_id','finalizer_version',
 'finalizer_core_version','finalization_run_id','bundle_generation_id','request_key','job_status','requested_at',
 'result_committed_at','requested_game_count','actual_game_count','execution_sequence','evaluation_mode','review_eligible',
 'review_policy','newer_input_available','input_snapshot_hash','error','source_batch_id','source_selection_revision',
 'source_core_version','source_context_hash','source_completed_at','target_round','based_on_round','candidate_numbers',
 'optimization_status','termination_reason','notice')

def bounded(value):
    try:
        if not isinstance(value,dict) or len(json.dumps(value,allow_nan=False))>500000:
            raise ValueError()
    except (ValueError,TypeError,RecursionError) as error:
        raise ContractError('invalid_finalization_payload') from error

def pick(value,fields):
    if not isinstance(value,dict):raise ContractError('invalid_finalization_object')
    return {key:deepcopy(value[key]) for key in fields if key in value}

def snapshot_hash(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value):
        raise ContractError('invalid_snapshot_hash')
    return value

def references(raw):
    rows=raw.get('source_result_refs',[])
    if not isinstance(rows,list) or len(rows)>128:raise ContractError('invalid_source_references')
    result=[]
    for row in rows:
        if not isinstance(row,dict):raise ContractError('invalid_source_references')
        result.append({key:identifier(row.get(key)) for key in ('source_generation_id','formula_id','result_id')})
    if len({tuple(row.values()) for row in result})!=len(result):raise ContractError('duplicate_source_reference')
    return result

def parse_readiness(raw):
    bounded(raw)
    if raw.get('capability')!=CAPABILITY or raw.get('input_state') not in INPUT_STATES:
        raise ContractError('unsupported_finalization_readiness')
    result=pick(raw,READINESS_FIELDS)
    if raw['input_state']=='not_configured':return result
    identifier(raw.get('source_batch_id'));identifier(raw.get('source_selection_revision'))
    snapshot_hash(raw.get('input_snapshot_hash'))
    n,done=raw.get('expected_count'),raw.get('completed_count')
    if type(n) is not int or not 1<=n<=128 or type(done) is not int or not 0<=done<=n:
        raise ContractError('invalid_source_counts')
    ids=raw.get('source_formula_ids',[])
    if not isinstance(ids,list) or len(ids)!=n:raise ContractError('invalid_source_selection')
    ids=[identifier(item) for item in ids]
    if len(set(ids))!=n:raise ContractError('invalid_source_selection')
    if raw['input_state']=='ready' and (done!=n or raw.get('blocked_sources') or n<2):
        raise ContractError('incomplete_ready_source')
    positive(raw.get('target_round'))
    if raw.get('based_on_round')!=raw['target_round']-1:raise ContractError('mixed_source_round')
    result['blocked_sources']=[pick(row,('formula_id','reason')) for row in raw.get('blocked_sources',[])]
    result['source_result_refs']=references(raw)
    result['source_formula_versions']={identifier(k):identifier(v) for k,v in raw.get('source_formula_versions',{}).items()}
    return result

METRIC_FIELDS=('scope','exact_or_estimated','sample_count','coverage_3','coverage_4','coverage_3_interval_95',
 'coverage_4_interval_95','triple_subsets','quad_subsets','candidate_count','unique_games','game_count',
 'max_number_usage','number_usage_concentration','scope_notice','evaluations','iterations','initial_coverage_3',
 'selected_coverage_3','original_direct_comparison','original_admissible','constrained_random_is_uniform',
 'audit_delta_coverage_3','audit_delta_interval_95','audit_worsened','selected_on_audit')

def public_metrics(value):
    result=pick(value,('elapsed_ms','cached_games'))
    for section in ('search','comparison'):
        result[section]=pick(value.get(section,{}),METRIC_FIELDS)
    result['audit']={key:pick(row,METRIC_FIELDS) for key,row in value.get('audit',{}).items()
                     if key in ('original','constrained_random','final','uniform_full45')}
    return result

def public_evaluation(value):
    if value is None:return None
    result=pick(value,('target_round','winning_numbers','bonus','original_direct_comparison',
        'evaluation_mode','separate_bundle_ranking','synthetic_samples_are_rounds','evaluated_at'))
    result['comparison']={}
    for key,row in value.get('comparison',{}).items():
        if key not in ('original','constrained_random','final','uniform_full45'):continue
        safe=pick(row,('included_main_count','bonus_in_candidates','best_main_matches','mean_main_matches','game_count'))
        safe['games']=[pick(g,('matches','bonus_match','prize_rank')) for g in row.get('games',[])]
        safe['prize_counts']=pick(row.get('prize_counts',{}),('1','2','3','4','5'))
        safe['at_least']=pick(row.get('at_least',{}),('3','4','5'))
        result['comparison'][key]=safe
    return result

def parse_finalization(raw, *, expected_run_id=None, expected_snapshot=None):
    bounded(raw)
    if raw.get('capability')!=CAPABILITY or type(raw.get('contract_version')) is not int or raw['contract_version']!=1:
        raise ContractError('unsupported_finalization_contract')
    if raw.get('execution_stage')!='post_generation' or raw.get('trigger')!='manual' or raw.get('output_kind')!='ticket_set':
        raise ContractError('invalid_finalization_stage')
    if raw.get('finalizer_id')!=FINALIZER_ID or raw.get('job_status') not in JOB_STATES:
        raise ContractError('invalid_finalization_status')
    run=identifier(raw.get('finalization_run_id'));identifier(raw.get('source_batch_id'))
    if raw.get('bundle_generation_id')!=run or expected_run_id and run!=expected_run_id:
        raise ContractError('wrong_finalization_job')
    snapshot_hash(raw.get('input_snapshot_hash'))
    if expected_snapshot and raw['input_snapshot_hash']!=expected_snapshot:
        raise ContractError('wrong_finalization_snapshot')
    target=positive(raw.get('target_round'))
    if raw.get('based_on_round')!=target-1:raise ContractError('wrong_finalization_round')
    count=raw.get('requested_game_count');games=raw.get('games')
    if type(count) is not int or not 1<=count<=20 or not isinstance(games,list):
        raise ContractError('invalid_ticket_set')
    sequence=raw.get('execution_sequence',0)
    if type(sequence) is not int or not 0<=sequence<=99:raise ContractError('invalid_execution_sequence')
    result=pick(raw,RESULT_FIELDS)
    result['source_result_refs']=references(raw)
    result['source_formula_versions']={identifier(k):identifier(v) for k,v in raw.get('source_formula_versions',{}).items()}
    result['games']=[];result['source_games']=[]
    originals=raw.get('source_games',[])
    if not isinstance(originals,list) or len(originals)>128:raise ContractError('source_evidence_missing')
    for row in originals:
        if not isinstance(row,dict):raise ContractError('invalid_source_evidence')
        result['source_games'].append({'formula_id':identifier(row.get('formula_id')),'numbers':list(numbers(row.get('numbers')))})
    if raw['job_status']=='completed':
        if len(games)!=count or raw.get('actual_game_count')!=count:raise ContractError('incomplete_ticket_set')
        timestamp(raw.get('result_committed_at'))
        ids=[];rows=[]
        for game in games:
            if not isinstance(game,dict):raise ContractError('invalid_final_game')
            game_id=identifier(game.get('game_id'));row=numbers(game.get('numbers'))
            ids.append(game_id);rows.append(row)
            result['games'].append({'game_id':game_id,'numbers':list(row)})
        if len(set(ids))!=count or len(set(rows))!=count:raise ContractError('duplicate_final_game')
        candidates=raw.get('candidate_numbers')
        if not isinstance(candidates,list) or any(type(n) is not int for n in candidates):
            raise ContractError('candidate_union_changed')
        if candidates!=sorted(set(candidates)) or set(candidates)!={n for row in rows for n in row}:
            raise ContractError('candidate_union_changed')
        if len(originals)<2 or {n for g in result['source_games'] for n in g['numbers']}!=set(candidates):
            raise ContractError('source_evidence_missing')
    elif games or raw.get('actual_game_count')!=0:
        raise ContractError('uncommitted_final_games')
    if 'metrics' in raw:result['metrics']=public_metrics(raw['metrics'])
    if 'evaluation' in raw:result['evaluation']=public_evaluation(raw['evaluation'])
    return result
