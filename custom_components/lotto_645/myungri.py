"""Traditional East Asian calendrical/numerology helpers for Lotto 6/45.

This module implements a deterministic *traditional* heuristic, not a predictive
lottery model.  It combines the sexagenary day pillar (60 갑자) with the He Tu
(河圖) number/five-element correspondence.  The rules are historically
well-defined and reproducible, but they have no scientifically demonstrated
ability to improve lottery odds.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from statistics import fmean
from typing import Any, Final

ELEMENT_KO: Final = {
    "wood": "목",
    "fire": "화",
    "earth": "토",
    "metal": "금",
    "water": "수",
}

GENERATES: Final = {
    "wood": "fire",
    "fire": "earth",
    "earth": "metal",
    "metal": "water",
    "water": "wood",
}
CONTROLS: Final = {
    "wood": "earth",
    "earth": "water",
    "water": "fire",
    "fire": "metal",
    "metal": "wood",
}

STEMS: Final = (
    ("갑", "甲", "wood", "yang"),
    ("을", "乙", "wood", "yin"),
    ("병", "丙", "fire", "yang"),
    ("정", "丁", "fire", "yin"),
    ("무", "戊", "earth", "yang"),
    ("기", "己", "earth", "yin"),
    ("경", "庚", "metal", "yang"),
    ("신", "辛", "metal", "yin"),
    ("임", "壬", "water", "yang"),
    ("계", "癸", "water", "yin"),
)

BRANCHES: Final = (
    ("자", "子", "water", "yang"),
    ("축", "丑", "earth", "yin"),
    ("인", "寅", "wood", "yang"),
    ("묘", "卯", "wood", "yin"),
    ("진", "辰", "earth", "yang"),
    ("사", "巳", "fire", "yin"),
    ("오", "午", "fire", "yang"),
    ("미", "未", "earth", "yin"),
    ("신", "申", "metal", "yang"),
    ("유", "酉", "metal", "yin"),
    ("술", "戌", "earth", "yang"),
    ("해", "亥", "water", "yin"),
)

HETU_BY_LAST_DIGIT: Final = {
    1: "water",
    6: "water",
    2: "fire",
    7: "fire",
    3: "wood",
    8: "wood",
    4: "metal",
    9: "metal",
    5: "earth",
    0: "earth",
}


def parse_draw_date(value: str) -> date | None:
    """Parse the official draw date formats seen by the integration."""
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def julian_day_number(value: date) -> int:
    """Return the Gregorian Julian Day Number at civil noon."""
    a = (14 - value.month) // 12
    y = value.year + 4800 - a
    m = value.month + 12 * a - 3
    return (
        value.day
        + (153 * m + 2) // 5
        + 365 * y
        + y // 4
        - y // 100
        + y // 400
        - 32045
    )


def sexagenary_day(value: date) -> dict[str, Any]:
    """Return the sexagenary day-pillar context.

    1949-10-01 (JDN 2433191) is a 甲子 day; therefore
    ``(JDN + 49) % 60`` gives the zero-based 60-cycle index.
    """
    cycle_index = (julian_day_number(value) + 49) % 60
    stem_index = cycle_index % 10
    branch_index = cycle_index % 12
    stem_ko, stem_hanja, stem_element, stem_polarity = STEMS[stem_index]
    branch_ko, branch_hanja, branch_element, branch_polarity = BRANCHES[
        branch_index
    ]
    return {
        "cycle_index": cycle_index,
        "cycle_position": cycle_index + 1,
        "name": f"{stem_ko}{branch_ko}({stem_hanja}{branch_hanja})",
        "stem": f"{stem_ko}({stem_hanja})",
        "branch": f"{branch_ko}({branch_hanja})",
        "stem_element": stem_element,
        "stem_element_ko": ELEMENT_KO[stem_element],
        "branch_element": branch_element,
        "branch_element_ko": ELEMENT_KO[branch_element],
        "stem_polarity": stem_polarity,
        "branch_polarity": branch_polarity,
    }


def number_element(number: int) -> str:
    """Return the He Tu five-element group for a lotto number."""
    if number < 1 or number > 45:
        raise ValueError("Lotto number must be between 1 and 45")
    return HETU_BY_LAST_DIGIT[number % 10]


def number_polarity(number: int) -> str:
    """Use traditional odd/yang and even/yin numeric polarity."""
    return "yang" if number % 2 else "yin"


def _relation_score(day_element: str, candidate_element: str) -> float:
    """Score a candidate element relative to a Day Master element."""
    if candidate_element == day_element:
        return 1.00
    if GENERATES[candidate_element] == day_element:
        return 0.94
    if GENERATES[day_element] == candidate_element:
        return 0.78
    if CONTROLS[day_element] == candidate_element:
        return 0.62
    if CONTROLS[candidate_element] == day_element:
        return 0.48
    return 0.50


def build_myungri_context(latest_draw_date: str) -> dict[str, Any]:
    """Build deterministic day-pillar and He Tu scores for the next draw."""
    latest = parse_draw_date(latest_draw_date)
    number_elements = {number: number_element(number) for number in range(1, 46)}

    if latest is None:
        return {
            "status": "date_unavailable",
            "target_draw_date": None,
            "sexagenary_day": None,
            "day_master": None,
            "day_master_element": None,
            "day_master_element_ko": None,
            "day_branch": None,
            "day_branch_element": None,
            "day_branch_element_ko": None,
            "number_elements": number_elements,
            "number_resonance": {number: 0.5 for number in range(1, 46)},
            "notice": (
                "공식 추첨일을 해석할 수 없어 명리 점수는 중립값으로 처리했습니다."
            ),
        }

    target = latest + timedelta(days=7)
    day = sexagenary_day(target)
    stem_element = str(day["stem_element"])
    branch_element = str(day["branch_element"])
    stem_polarity = str(day["stem_polarity"])

    resonance: dict[int, float] = {}
    for number, element in number_elements.items():
        stem_relation = _relation_score(stem_element, element)
        branch_relation = _relation_score(branch_element, element)
        polarity_match = 1.0 if number_polarity(number) == stem_polarity else 0.0
        resonance[number] = (
            0.62 * stem_relation
            + 0.25 * branch_relation
            + 0.13 * polarity_match
        )

    return {
        "status": "ready",
        "target_draw_date": target.isoformat(),
        "sexagenary_day": day["name"],
        "cycle_position": day["cycle_position"],
        "day_master": day["stem"],
        "day_master_element": stem_element,
        "day_master_element_ko": day["stem_element_ko"],
        "day_master_polarity": stem_polarity,
        "day_branch": day["branch"],
        "day_branch_element": branch_element,
        "day_branch_element_ko": day["branch_element_ko"],
        "number_elements": number_elements,
        "number_resonance": resonance,
        "notice": (
            "60갑자 일진과 하도 수리오행을 재현 가능한 전통 규칙으로 계산합니다. "
            "이는 명리 체계 내부의 해석 규칙이며 로또 당첨 확률 상승이 과학적으로 "
            "검증됐다는 의미는 아닙니다."
        ),
    }


def combo_myungri_score(combo: tuple[int, ...], context: dict[str, Any]) -> float:
    """Return the combination-level traditional five-element balance score."""
    elements = [context["number_elements"][number] for number in combo]
    counts = Counter(elements)
    resonance = fmean(context["number_resonance"][number] for number in combo)
    element_diversity = min(len(counts) / 5.0, 1.0)
    max_count = max(counts.values(), default=0)
    concentration = 1.0 if max_count <= 2 else max(0.0, 1.0 - (max_count - 2) / 4)
    yang_count = sum(number % 2 for number in combo)
    polarity_balance = max(0.0, 1.0 - abs(yang_count - 3) / 3)

    return (
        0.45 * resonance
        + 0.25 * element_diversity
        + 0.20 * polarity_balance
        + 0.10 * concentration
    )


def combo_myungri_details(
    combo: tuple[int, ...], context: dict[str, Any]
) -> dict[str, Any]:
    """Return user-facing details for a metaphysics recommendation."""
    element_by_number = {
        str(number): ELEMENT_KO[context["number_elements"][number]]
        for number in combo
    }
    counts = Counter(context["number_elements"][number] for number in combo)
    return {
        "traditional_method": "60갑자 일진(日柱) + 하도(河圖) 수리오행",
        "target_draw_date": context.get("target_draw_date"),
        "sexagenary_day": context.get("sexagenary_day"),
        "day_master": context.get("day_master"),
        "day_master_element": context.get("day_master_element_ko"),
        "day_branch": context.get("day_branch"),
        "day_branch_element": context.get("day_branch_element_ko"),
        "number_five_elements": element_by_number,
        "five_element_counts": {
            ELEMENT_KO[element]: counts.get(element, 0)
            for element in ("wood", "fire", "earth", "metal", "water")
        },
        "yang_count": sum(number % 2 for number in combo),
        "yin_count": sum(number % 2 == 0 for number in combo),
        "traditional_notice": context.get("notice"),
    }
