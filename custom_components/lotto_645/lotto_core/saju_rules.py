"""Auditable interpretation of the supplied Saju prompt (sections 1.2.3–1.2.16).

Tables are source rules. Numerical aggregation is an explicitly versioned local
heuristic, NOT a classical standard, a medical assessment or lottery probability.
No implicit 합화: recognizing a combination does not prove transformation.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from lunar_python.util import LunarUtil

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = ("wood", "fire", "earth", "metal", "water")
KO = dict(zip(ELEMENTS, ("목", "화", "토", "금", "수"), strict=True))
STEM_KO = dict(zip(STEMS, "갑을병정무기경신임계", strict=True))
BRANCH_KO = dict(zip(BRANCHES, "자축인묘진사오미신유술해", strict=True))
STEM_ELEMENT = {stem: ELEMENTS[i // 2] for i, stem in enumerate(STEMS)}
BRANCH_ELEMENT = dict(zip(BRANCHES, ("water", "earth", "wood", "wood", "earth", "fire", "fire", "earth", "metal", "metal", "earth", "water"), strict=True))
GENERATES = dict(zip(ELEMENTS, ELEMENTS[1:] + ELEMENTS[:1], strict=True))
CONTROLS = dict(zip(ELEMENTS, ("earth", "metal", "water", "wood", "fire"), strict=True))
GENERATED_BY = {v: k for k, v in GENERATES.items()}
CONTROLLED_BY = {v: k for k, v in CONTROLS.items()}

# Named-stem ratios from prompt §1.2.9; 亥 includes 戊 by that source's school.
# This differs from lunar_python's 壬/甲 table; it is deliberately disclosed.
HIDDEN = {
    "子": {"癸": 1.0}, "丑": {"癸": .30, "辛": .10, "己": .60},
    "寅": {"戊": .23, "丙": .23, "甲": .54}, "卯": {"乙": 1.0},
    "辰": {"乙": .30, "癸": .10, "戊": .60},
    "巳": {"戊": .23, "庚": .23, "丙": .54}, "午": {"己": .30, "丁": .70},
    "未": {"丁": .30, "乙": .10, "己": .60},
    "申": {"戊": .23, "壬": .23, "庚": .54}, "酉": {"辛": 1.0},
    "戌": {"辛": .30, "丁": .10, "戊": .60},
    "亥": {"戊": .23, "甲": .17, "壬": .60},
}
STAGES = ("장생", "목욕", "관대", "건록", "제왕", "쇠", "병", "사", "묘", "절", "태", "양")
# §1.2.10 table, forward for yang stems, reverse for yin stems.
STAGE_START = dict(zip(STEMS, ("亥", "午", "寅", "酉", "寅", "酉", "巳", "子", "申", "卯"), strict=True))
GODS = ("비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인")
GOD_GROUP = dict(zip(GODS, ("companion", "companion", "output", "output", "wealth", "wealth", "officer", "officer", "resource", "resource"), strict=True))
HETU = {1: "water", 6: "water", 2: "fire", 7: "fire", 3: "wood", 8: "wood", 4: "metal", 9: "metal", 5: "earth", 0: "earth"}

# The prompt's direct branch lookup differs from its hidden-stem main-qi
# rules for some branches. Preserve both instead of silently overwriting one.
PROMPT_BRANCH_GODS = [
    "정인 정재 비견 겁재 편재 상관 식신 정재 편관 정관 편재 편인".split(),
    "편인 편재 겁재 비견 정재 식신 상관 편재 정관 편관 정재 정인".split(),
    "정관 상관 편인 정인 식신 비견 겁재 상관 편재 정재 식신 편관".split(),
    "편관 식신 정인 편인 상관 겁재 비견 식신 정재 편재 상관 정관".split(),
    "정재 비견 편관 정관 겁재 편인 정인 비견 식신 상관 겁재 편재".split(),
    "편재 겁재 정관 편관 비견 정인 편인 겁재 상관 식신 비견 정재".split(),
    "상관 정인 편재 정재 편인 편관 정관 정인 비견 겁재 편인 식신".split(),
    "식신 편인 정재 편재 정인 정관 편관 편인 겁재 비견 정인 상관".split(),
    "겁재 정관 식신 상관 편관 정재 편재 정관 편인 정인 편관 비견".split(),
    "비견 편관 상관 식신 정관 편재 정재 편관 정인 편인 정관 겁재".split(),
]


def ten_god(day_stem: str, other_stem: str) -> str:
    """All 100 stem pairs; five generating/controlling roles plus yin/yang."""
    day, other = STEM_ELEMENT[day_stem], STEM_ELEMENT[other_stem]
    same = STEMS.index(day_stem) % 2 == STEMS.index(other_stem) % 2
    if day == other:
        return "비견" if same else "겁재"
    if GENERATES[day] == other:
        return "식신" if same else "상관"
    if CONTROLS[day] == other:
        return "편재" if same else "정재"
    if CONTROLS[other] == day:
        return "편관" if same else "정관"
    return "편인" if same else "정인"


def number_stem(number: int) -> str:
    """Modern extension: Hetu last digit + odd/yang, even/yin; not stem index."""
    if type(number) is not int or not 1 <= number <= 45:
        raise ValueError("번호는 1~45의 정수여야 합니다")
    return STEMS[2 * ELEMENTS.index(HETU[number % 10]) + (0 if number % 2 else 1)]


def pillar_record(ganzhi: str, day_stem: str) -> dict[str, Any]:
    stem, branch = ganzhi
    start = BRANCHES.index(STAGE_START[day_stem])
    direction = 1 if STEMS.index(day_stem) % 2 == 0 else -1
    stage = STAGES[((BRANCHES.index(branch) - start) * direction) % 12]
    ordered = sorted(HIDDEN[branch], key=lambda item: -HIDDEN[branch][item])
    return {
        "ganzhi": ganzhi, "stem": stem, "branch": branch,
        "stem_display": f"{STEM_KO[stem]}({stem})", "branch_display": f"{BRANCH_KO[branch]}({branch})",
        "stem_element": KO[STEM_ELEMENT[stem]], "branch_element": KO[BRANCH_ELEMENT[branch]],
        "hidden_stems": ordered, "hidden_stem_weights": HIDDEN[branch],
        "hidden_stem_rule": "제공 프롬프트 §1.2.9 (亥의 戊 포함)",
        "wuxing": KO[STEM_ELEMENT[stem]] + KO[BRANCH_ELEMENT[branch]],
        "nayin": LunarUtil.NAYIN[ganzhi],
        "ten_god_stem": ten_god(day_stem, stem),
        "ten_gods_branch": [ten_god(day_stem, hidden) for hidden in ordered],
        "prompt_branch_ten_god": PROMPT_BRANCH_GODS[STEMS.index(day_stem)][BRANCHES.index(branch)],
        "hidden_main_ten_god": ten_god(day_stem, ordered[0]),
        "branch_ten_god_policy": "직접 지지 조견표는 참고 표시; 점수는 명시된 지장간 비율과 천간 십신표를 사용",
        "growth_stage": stage,
    }


def structural_analysis(pillars: dict[str, Any]) -> dict[str, Any]:
    """Expose season/roots/exposure separately instead of one hidden percentage."""
    day_stem = pillars["day"]["stem"]
    day_element = STEM_ELEMENT[day_stem]
    resource = GENERATED_BY[day_element]
    visible = Counter()
    weighted = {e: 0.0 for e in ELEMENTS}
    exposed = {p["stem"] for p in pillars.values()}
    roots, exposures = [], []
    support_by_branch = []
    gods = {god: 0.0 for god in GODS}
    for position, pillar in pillars.items():
        stem, branch = pillar["stem"], pillar["branch"]
        visible.update((STEM_ELEMENT[stem], BRANCH_ELEMENT[branch]))
        weighted[STEM_ELEMENT[stem]] += 1
        if position != "day":  # day master is 本元, not an extra companion
            gods[ten_god(day_stem, stem)] += 1
        supporting = 0.0
        for hidden, ratio in HIDDEN[branch].items():
            # One branch contributes one unit. Do not count main branch twice.
            weighted[STEM_ELEMENT[hidden]] += ratio
            gods[ten_god(day_stem, hidden)] += ratio
            if STEM_ELEMENT[hidden] in (day_element, resource):
                supporting += ratio
            if STEM_ELEMENT[hidden] == day_element:
                roots.append({"pillar": position, "stem": hidden, "share": ratio})
            if hidden in exposed:
                exposures.append({"pillar": position, "stem": hidden, "share": ratio})
        support_by_branch.append(supporting)
    total = sum(weighted.values())
    balance = {e: weighted[e] / total for e in ELEMENTS}
    month_branch = pillars["month"]["branch"]
    month_support = sum(ratio for stem, ratio in HIDDEN[month_branch].items()
                        if STEM_ELEMENT[stem] in (day_element, resource))
    root_support = sum(support_by_branch) / len(pillars)
    surface = [p["stem"] for key, p in pillars.items() if key != "day"]
    peer_support = sum(STEM_ELEMENT[s] in (day_element, resource) for s in surface) / len(surface)
    mass_support = balance[day_element] + balance[resource]
    # Versioned developer heuristic. Source supplies concepts, not these weights.
    components = {"월령": month_support, "지지통근": root_support,
                  "천간세력": peer_support, "오행질량": mass_support}
    weights = {"월령": .40, "지지통근": .25, "천간세력": .20, "오행질량": .15}
    support = sum(components[k] * weights[k] for k in weights)
    strength = "신강" if support >= .60 else "신약" if support <= .40 else "중화"
    main_stem = max(HIDDEN[month_branch], key=HIDDEN[month_branch].get)
    month_god = ten_god(day_stem, main_stem)
    if pillars["month"]["growth_stage"] == "건록":
        pattern = "건록격 후보"
    elif month_branch == dict(zip(STEMS, "卯寅午巳午巳酉申子亥", strict=True))[day_stem]:
        pattern = "양인격 후보"
    elif month_god not in ("비견", "겁재"):
        pattern = f"{month_god}격 후보"
    else:
        pattern = "월령 비겁형 · 별도 격국 검토 필요"
    return {"balance": balance, "visible_counts": {KO[e]: visible[e] for e in ELEMENTS},
            "strength": strength, "support_ratio": round(support, 6),
            "strength_components": components, "strength_weights": weights,
            "strength_rule": "source_prompt_v2_local_model_v1; 임계 0.40/0.60은 구현 가정",
            "roots": roots, "exposed_hidden_stems": exposures,
            "ten_god_distribution": gods,
            "pattern": {"name": pattern, "month_main_stem": main_stem,
                        "month_ten_god": month_god, "exposed": main_stem in exposed,
                        "certainty": "후보", "special_patterns": "종격·화격은 성립 조건 미정의로 확정하지 않음"}}


def favorable_analysis(day_element: str, structure: dict[str, Any], month_branch: str) -> dict[str, Any]:
    """Four source principles, with explicit rule evidence and bounded weights."""
    balance, strength = structure["balance"], structure["strength"]
    roles = {"companion": day_element, "resource": GENERATED_BY[day_element],
             "output": GENERATES[day_element], "wealth": CONTROLS[day_element],
             "officer": CONTROLLED_BY[day_element]}
    votes = {e: .5 for e in ELEMENTS}
    evidence: list[dict[str, Any]] = []
    picks = ([roles["resource"], roles["companion"]] if strength == "신약" else
             [roles["output"], roles["wealth"], roles["officer"]] if strength == "신강" else [])
    for e in picks:
        votes[e] += .24
    evidence.append({"principle": "억부", "elements": [KO[e] for e in picks],
                     "reason": f"{strength}에 따른 부조/억제 후보; 종격·화격 예외는 미확정"})
    season = "water" if month_branch in "巳午未" else "fire" if month_branch in "亥子丑" else None
    if season:
        votes[season] += .16
    evidence.append({"principle": "조후", "elements": [KO[season]] if season else [],
                     "reason": "여름 수·겨울 화의 계절 조절 원칙; 일간별 고전 조후표 전체를 구현한 것은 아님"})
    bridges = []
    for controller, controlled in CONTROLS.items():
        if min(balance[controller], balance[controlled]) >= .20:
            bridge = GENERATES[controller]
            votes[bridge] += .08
            bridges.append(KO[bridge])
    evidence.append({"principle": "통관", "elements": sorted(set(bridges)),
                     "reason": "상극 양측 질량이 각각 20% 이상일 때 중재 오행 후보 (20%는 구현 임계)"})
    dominant = max(balance, key=balance.get)
    remedy = []
    if balance[dominant] >= .45:
        remedy = [GENERATES[dominant], CONTROLLED_BY[dominant]]
        for e in remedy:
            votes[e] += .06
    evidence.append({"principle": "병약", "elements": [KO[e] for e in remedy],
                     "reason": "한 오행 45% 이상 편중의 설기·제어 후보만 적용; 고전 병약론 전체 판정이 아님"})
    scores = {e: min(.95, value) for e, value in votes.items()}
    favorable = sorted((e for e in ELEMENTS if scores[e] > .5), key=lambda e: (-scores[e], e))
    if not favorable:
        favorable = [roles["output"]]  # neutral tie policy, explicitly disclosed
        evidence.append({"principle": "중립 동점 처리", "elements": [KO[roles["output"]]],
                         "reason": "후보가 없을 때 식상 계열을 참고 후보로 표시하는 구현 정책"})
    return {"scores": scores, "favorable_elements": favorable, "avoid_elements": [],
            "roles": roles, "evidence": evidence,
            "notice": "용신·희신 확정이 아닌 보완오행 후보; 가산값은 개발자 휴리스틱"}

# Relations from §1.2.14. Result elements are candidates, never asserted 化.
STEM_HARMONY = {"甲己": "earth", "乙庚": "metal", "丙辛": "water", "丁壬": "wood", "戊癸": "fire"}
STEM_CLASH = ("甲庚", "乙辛", "丙壬", "丁癸")
BRANCH_HARMONY = {"子丑": "earth", "寅亥": "wood", "卯戌": "fire", "辰酉": "metal", "巳申": "water", "午未": None}
BRANCH_CLASH = ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")
BRANCH_HARM = ("子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌")
BRANCH_BREAK = ("子酉", "午卯", "寅亥", "申巳", "辰丑", "戌未")
TRIPLES = {"申子辰": "water", "亥卯未": "wood", "寅午戌": "fire", "巳酉丑": "metal"}
DIRECTIONS = {"寅卯辰": "wood", "巳午未": "fire", "申酉戌": "metal", "亥子丑": "water"}


def interactions(pillars: dict[str, Any], incoming: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Only distinct positions, preserve repeats for 自刑, require incoming membership."""
    natal = [(f"원국:{key}", p) for key, p in pillars.items()]
    added = [(f"운:{key}", p) for key, p in (incoming or {}).items()]
    items = natal + added
    events: list[dict[str, Any]] = []
    def emit(kind: str, group: tuple, element: str | None = None) -> None:
        events.append({"type": kind, "positions": [p[0] for p in group],
                       "characters": [p[1]["ganzhi"] for p in group],
                       "element_candidate": element, "transformation_confirmed": False})
    for a, b in combinations(items, 2):
        if incoming is not None and not any(x[0].startswith("운:") for x in (a, b)):
            continue
        for key, table, kind in (("stem", STEM_HARMONY, "천간합"), ("branch", BRANCH_HARMONY, "육합")):
            for chars, element in table.items():
                if {a[1][key], b[1][key]} == set(chars):
                    emit(kind, (a, b), element)
        for key, table, kind in (("stem", STEM_CLASH, "천간충"), ("branch", BRANCH_CLASH, "육충"),
                                ("branch", BRANCH_HARM, "육해"), ("branch", BRANCH_BREAK, "파"),
                                ("branch", ("子卯",), "자묘형")):
            if any({a[1][key], b[1][key]} == set(chars) for chars in table):
                emit(kind, (a, b))
        if a[1]["branch"] == b[1]["branch"] and a[1]["branch"] in "辰午酉亥":
            emit("자형", (a, b))
    for group in combinations(items, 3):
        if incoming is not None and not any(item[0].startswith("운:") for item in group):
            continue
        branches = {p[1]["branch"] for p in group}
        for table, kind in ((TRIPLES, "삼합"), (DIRECTIONS, "방합")):
            for chars, element in table.items():
                if branches == set(chars):
                    emit(kind, group, element)
        if branches in (set("寅巳申"), set("丑戌未")):
            emit("삼형", group)
    return events


def interaction_adjustments(events: list[dict[str, Any]], favorable_scores: dict[str, float]) -> dict[str, float]:
    """Small selection-model effect, not a fortune judgment: 합 is not always good."""
    changes = {e: 0.0 for e in ELEMENTS}
    for event in events:
        candidate = event["element_candidate"]
        if candidate:
            # Only an application preference conditional on the already-derived
            # candidate, never mutate the natal stems/branches into another element.
            changes[candidate] += .02 * (1 if favorable_scores[candidate] > .5 else -1)
        elif event["type"] in ("천간충", "육충", "육해", "파", "자묘형", "자형", "삼형"):
            for ganzhi in event["characters"]:
                changes[BRANCH_ELEMENT[ganzhi[1]]] -= .006
    return {e: max(-.08, min(.08, value)) for e, value in changes.items()}


def shensha(pillars: dict[str, Any]) -> dict[str, Any]:
    """Only supplied lookup tables; display-only, not bonus lottery points."""
    day = pillars["day"]["stem"]
    day_i = STEMS.index(day)
    noble = ("丑未", "子申", "亥酉", "亥酉", "丑未", "子申", "丑未", "寅午", "卯巳", "卯巳")[day_i]
    literary = "巳午申酉申酉亥子寅卯"[day_i]
    blade = "卯寅午巳午巳酉申子亥"[day_i]
    matches = []
    for position, pillar in pillars.items():
        branch = pillar["branch"]
        for name, chars in (("천을귀인", noble), ("문창귀인", literary), ("양인", blade)):
            if branch in chars:
                matches.append({"name": name, "position": position, "basis": "일간"})
    for reference in ("year", "day"):
        rb = pillars[reference]["branch"]
        for group, peach, travel, canopy in (("寅午戌", "卯", "申", "戌"), ("申子辰", "酉", "寅", "辰"),
                                             ("巳酉丑", "午", "亥", "丑"), ("亥卯未", "子", "巳", "未")):
            if rb in group:
                for position, pillar in pillars.items():
                    for name, target in (("도화", peach), ("역마", travel), ("화개", canopy)):
                        if pillar["branch"] == target:
                            matches.append({"name": name, "position": position, "basis": reference})
    ghost_pair = dict(zip("子丑寅卯辰巳午未申酉戌亥", "丑子未申巳辰亥寅卯戌酉午", strict=True))
    for position, pillar in pillars.items():
        if position != "day" and pillar["branch"] == ghost_pair[pillars["day"]["branch"]]:
            matches.append({"name": "귀문관", "position": position, "basis": "일지 (참고 분류)"})
    return {"matches": matches, "lottery_score_weight": 0,
            "not_implemented": ["천덕귀인", "월덕귀인", "학당귀인", "백호"],
            "notice": "조회표가 명시된 신살만 참고 표시. 표가 없는 신살 및 건강·재산 사건은 추정하지 않음"}
