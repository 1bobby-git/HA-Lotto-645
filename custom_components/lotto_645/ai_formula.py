"""AI explains an immutable backend ticket; it is never the random source."""
from __future__ import annotations

import json

from .const import DISCLAIMER, FIRST_PRIZE_ODDS
from .service_contract import numbers as validate_fixed
FORMULA_VERSION = "server"

AI_BASE_FORMULA = "calibrated_stratified"


def explanation_prompt(numbers, target_round, cutoff_round, attempt=1):
    """Only actual public execution facts. No birth profile or invented scores."""
    facts = {
        "task": "explain_backend_formula", "formula_id": AI_BASE_FORMULA,
        "formula_version": FORMULA_VERSION, "target_round": target_round,
        "history_cutoff_round": cutoff_round, "numbers": list(numbers),
        "rng": "system_csprng", "history_used_for_weighting": False,
        "exclusions": "past_winning_combinations_and_duplicate_tickets",
        "uniformity": "uniform_over_allowed_combinations",
        "predictive_claim": False, "first_prize_odds": FIRST_PRIZE_ODDS,
    }
    return (
        '당신은 HA-Lotto-645의 추첨 공식 설명자입니다. 당첨번호 예측기가 아닙니다.\n'
        '번호는 백엔드 CCSS 엔진이 이미 확정했습니다. 번호를 생성·수정·재선택하지 마세요.\n'
        '구간 배분을 조합 개수로 보정한 조건부 균등 추첨임을 설명하세요. '
        '구간별 개수를 똑같이 강제했다거나 과거 제외가 확률을 높인다고 주장하지 마세요.\n'
        '빈도·통계·p-value·정확도·확률 개선율을 만들지 마세요. '
        '과거 패턴과 AI가 다음 회차를 예측한다는 주장은 금지합니다.\n'
        '번호 필드는 반환하지 마세요. formula_id는 calibrated_stratified, '
        'reason은 실제 실행 정보에만 근거한 180자 이내 한국어 설명으로 반환하세요.\n'
        '개인 사주 정보는 제공하지 않습니다. 이를 추정하지 마세요.\n'
        + ('이전 설명의 형식이 거절되었습니다. 지정된 필드만 반환하세요.\n' if attempt > 1 else '')
        + json.dumps(facts, ensure_ascii=False) + '\n' + DISCLAIMER
    )


def validate_explanation(data):
    if not isinstance(data, dict) or set(data) - {"formula_id", "reason", "basis"}:
        raise ValueError("AI는 번호가 아닌 공식 설명만 반환해야 합니다")
    if data.get("formula_id") != AI_BASE_FORMULA:
        raise ValueError("AI가 백엔드의 추첨 공식을 변경했습니다")
    reason = data.get("reason")
    basis = data.get("basis", "")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 300:
        raise ValueError("AI 설명은 1~300자 문자열이어야 합니다")
    if not isinstance(basis, str) or len(basis) > 500:
        raise ValueError("AI 근거 형식이 올바르지 않습니다")
    return reason.strip(), basis.strip()


def validate_backend_ticket(numbers, analysis, history):
    ticket = validate_fixed(numbers)
    if len(ticket) != 6 or not history or analysis.based_on_round != history[-1].round:
        raise ValueError("추천 생성 중 기준 회차가 바뀌었습니다")
    if ticket in {d.numbers for d in history} | {r.numbers for r in analysis.recommendations}:
        raise ValueError("추첨 공식 결과가 제외 조합과 중복됩니다")
    return ticket
