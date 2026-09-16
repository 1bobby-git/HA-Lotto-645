"""Isolated, prefix-only historical simulations; never a prediction/review ledger.

The target draw is used only by evaluate_ticket AFTER a fresh analysis has been
built. No live tickets, score summaries, exclusion cache or generation nonce are
inputs. Current formula definitions are replayed, not historical code versions.
"""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
import secrets
from typing import Any

from .ai_formula import AI_BASE_FORMULA, make_ai_ticket
from .analysis import build_analysis
from .consensus import refresh_consensus, valid_ticket
from .const import AI_METHOD_ID, VERSION
from .constraints import ConstraintError
from .methods import METHODS_BY_ID, METHOD_MYUNGRI_HETU, METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE, consensus_source_ids
from .models import LottoDraw
from .result_evaluator import evaluate_ticket
from .sampling import FORMULA_VERSION

MIN_TARGET_ROUND = 31  # Same minimum 30-draw history as the production engine.
NOTICE = (
    "현재 버전의 추첨 공식을 당시 이전 데이터로 다시 실행한 검증용 시뮬레이션입니다. "
    "그때 실제로 생성·저장했던 추천이 아니며 실제 추천번호·당첨 기록·리뷰 점수에 반영하지 않습니다. "
    "여러 번 검증해 좋은 결과만 고르는 것은 예측력의 근거가 아닙니다."
)


class HistoricalValidationError(ValueError):
    """A bounded, user-safe error, without raw personal configuration."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_method_ids(value: object) -> tuple[str, ...]:
    """Unlike saved-option normalization, a test must not silently change IDs."""
    if (not isinstance(value, (list, tuple)) or not 1 <= len(value) <= len(METHODS_BY_ID) + 1
            or any(not isinstance(key, str) or key not in (*METHODS_BY_ID, AI_METHOD_ID) for key in value)
            or len(set(value)) != len(value)):
        raise HistoricalValidationError('invalid_formulas', '검증할 추첨 공식을 1개 이상 선택하세요. 중복·알 수 없는 공식은 사용할 수 없습니다.')
    ids = tuple(value)
    if any(k in ids for k in (METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE)) and len(consensus_source_ids(ids)) < 2:
        raise HistoricalValidationError('consensus_sources_required', '합의 추천은 다른 로컬 추첨 공식을 2개 이상 함께 선택해야 합니다. AI는 합의에 포함되지 않습니다.')
    return ids


def run_historical_validation(
    history: Sequence[LottoDraw], target_round: int, method_ids: Sequence[str],
    saju_profile: dict[str, Any] | None = None, *, previous_tickets: Sequence[tuple[int, ...]] = (), rng=None, formula_options=None,
) -> dict[str, Any]:
    """Generate once from [1, R-1], then compare to R, returning ephemeral JSON.

    Every production request uses fresh OS randomness. Only unit tests may
    inject a random generator; no seed is accepted or returned by the UI/API.
    Previous simulations for this target can be excluded without reading any
    target numbers or live recommendation state. Call in executor.
    """
    if type(target_round) is not int or not MIN_TARGET_ROUND <= target_round <= 999999:
        raise HistoricalValidationError('invalid_round', '과거 회차 검증은 최소 30회 이력이 필요한 31회부터 가능합니다.')
    ids = validate_method_ids(method_ids)
    target_rows = [d for d in history if d.round == target_round]
    if len(target_rows) != 1:
        raise HistoricalValidationError('round_unavailable', '해당 회차의 공식 당첨 결과가 없습니다. 속보·미래 회차는 검증할 수 없습니다.')
    # Split before feature extraction, ranking, excluded-combination creation,
    # calendar context, consensus, or any sampling. Future draws never enter it.
    training = sorted((d for d in history if d.round < target_round), key=lambda d: d.round)
    if [d.round for d in training] != list(range(1, target_round)):
        raise HistoricalValidationError('history_incomplete', '1회부터 선택 회차 직전까지 연속된 공식 이력이 필요합니다.')
    if METHOD_MYUNGRI_HETU in ids and not saju_profile:
        raise HistoricalValidationError('profile_required', '명리 추첨 공식은 통합 설정에서 개인 사주정보를 먼저 완성해야 합니다.')
    # Only this prefix is fingerprinted. Changing R or R+1 cannot change the RNG.
    fingerprint = sha256(json.dumps(
        [(d.round, d.draw_date, d.numbers, d.bonus) for d in training],
        separators=(',', ':'), ensure_ascii=False,
    ).encode()).hexdigest()
    rng = rng if rng is not None else secrets.SystemRandom()
    generation_variant = rng.randrange(1, 2**32)
    blocked = set()
    if len(previous_tickets) > len(METHODS_BY_ID) + 1:
        raise HistoricalValidationError('invalid_previous', '이전 검증 결과가 올바르지 않습니다.')
    for value in previous_tickets:
        ticket = valid_ticket(value)
        if ticket is None:
            raise HistoricalValidationError('invalid_previous', '이전 검증 결과가 올바르지 않습니다.')
        blocked.add(ticket)
    local_ids = tuple(key for key in ids if key != AI_METHOD_ID)
    try:
        analysis = build_analysis(training, local_ids, generation_variant, deepcopy(saju_profile),
                                  excluded_combinations=tuple(blocked), rng=rng, formula_options=deepcopy(formula_options))
        if any(k in local_ids for k in (METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE)) and blocked:
            analysis = refresh_consensus(analysis, local_ids, training, excluded_combinations=blocked)
    except ConstraintError as err:
        raise HistoricalValidationError(err.code, str(err)) from err
    except ValueError as err:
        raise HistoricalValidationError('generation_failed', '선택한 공식으로 검증번호를 만들 수 없습니다. 이력과 사주 설정, 합의 참여 공식을 확인하세요.') from err
    if analysis.based_on_round != target_round - 1 or analysis.target_round != target_round:
        raise HistoricalValidationError('cutoff_mismatch', '검증 기준 회차가 일치하지 않아 결과를 폐기했습니다.')
    # Do not expose Saju details, nor call an AI provider with historical targets.
    generated = {r.method_id: {
        'method_id': r.method_id, 'formula_id': r.method_id, 'sensor_name': r.label,
        'formula_version': METHODS_BY_ID[r.method_id].formula_version,
        'recommended_numbers': list(r.numbers), 'source': 'historical_validation',
        'generation_status': 'generated',
    } for r in analysis.recommendations}
    if AI_METHOD_ID in ids:
        ticket = make_ai_ticket(training, analysis.recommendations, rng=rng, excluded_combinations=blocked)
        generated[AI_METHOD_ID] = {
            'method_id': AI_METHOD_ID, 'formula_id': AI_METHOD_ID,
            'sensor_name': 'Home Assistant AI 추천 · CCSS 번호만 검증',
            'formula_version': FORMULA_VERSION, 'base_formula_id': AI_BASE_FORMULA,
            'recommended_numbers': list(ticket), 'source': 'historical_validation',
            'generation_status': 'generated', 'ai_called': False,
        }
    # Only now may the target's numbers influence anything: the comparison.
    target = target_rows[0]
    results = []
    for key in ids:
        row = generated.get(key)
        if row is None:
            # A strict +/-1 consensus may have no candidate. Never fake a ticket,
            # silently expand its tolerance or present it as a losing game.
            results.append({
                'method_id': key, 'formula_id': key, 'sensor_name': METHODS_BY_ID[key].label,
                'formula_version': METHODS_BY_ID[key].formula_version,
                'source': 'historical_validation', 'generation_status': 'unavailable',
                'recommended_numbers': [], 'status': '판정 불가', 'prize': '생성 불가',
                'prize_rank': None, 'reason': '선택한 합의 규칙과 제외 조건을 만족하는 조합이 없습니다.',
            })
            continue
        results.append({**row, **evaluate_ticket(tuple(row['recommended_numbers']), target)})
    compared = [r for r in results if r['generation_status'] == 'generated']
    winners = [r for r in compared if r['prize_rank'] is not None]
    return {
        'mode': 'historical_validation', 'simulation': True,
        'counts_toward_reviews': False, 'persisted': False, 'ai_called': False,
        'component_version': VERSION, 'formula_policy': 'current_version_replay',
        'target_round': target_round, 'based_on_round': target_round - 1,
        'training_first_round': 1, 'training_last_round': target_round - 1,
        'training_draw_count': len(training), 'training_sha256': fingerprint,
        'target_and_future_used_for_generation': False,
        'generated_at': datetime.now(UTC).isoformat(),
        'rng': 'system_csprng' if isinstance(rng, secrets.SystemRandom) else 'injected_test_rng',
        'previous_simulation_excluded': bool(blocked),
        'uses_current_saju_profile': METHOD_MYUNGRI_HETU in ids,
        'uses_current_formula_options': any(k in ids for k in ('constraint_uniform', 'personal_lucky')),
        'method_ids': list(ids), 'results': results,
        'draw': {'round': target.round, 'draw_date': target.draw_date,
                 'numbers': list(target.numbers), 'bonus': target.bonus},
        'checked_game_count': len(compared), 'unavailable_game_count': len(results) - len(compared),
        'winning_game_count': len(winners),
        'highest_prize': min(winners, key=lambda r: r['prize_rank'])['prize'] if winners else None,
        'notice': NOTICE,
    }
