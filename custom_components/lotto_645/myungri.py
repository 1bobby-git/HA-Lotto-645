"""Personal Saju number selection with a traceable, source-aligned rule layer.

Calendar facts, prompt-derived classifications and the modern lottery mapping
are distinct. No rule claims to increase the chance of a winning combination.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from statistics import fmean
from typing import Any
from zoneinfo import ZoneInfo

from .const import (
    CONF_SAJU_BIRTH_DATE, CONF_SAJU_BIRTH_PLACE, CONF_SAJU_BIRTH_TIME,
    CONF_SAJU_CALENDAR, CONF_SAJU_GENDER, CONF_SAJU_LONGITUDE,
    CONF_SAJU_LUNAR_LEAP_MONTH, CONF_SAJU_TIMEZONE, CONF_SAJU_TRUE_SOLAR_TIME,
    SAJU_NOTICE, SAJU_PRIVACY_NOTICE,
)
from .saju_calendar import SajuProfileError, resolve_birth, pillars_at, luck_cycles
from .saju_rules import (
    BRANCH_ELEMENT, ELEMENTS, KO, STEM_ELEMENT, STEM_KO, STEMS, HETU, GODS,
    GOD_GROUP, GENERATED_BY, GENERATES, CONTROLS, CONTROLLED_BY,
    favorable_analysis, interaction_adjustments, interactions, number_stem,
    pillar_record, shensha, structural_analysis, ten_god,
)

ELEMENT_KO = KO
PILLAR_LABELS = ("년주", "월주", "일주", "시주")
SOURCE_RULESET = "saju_master_prompt_v2_audited_1"
NUMBER_WEIGHTS = {"보완오행": .40, "십신분포": .20, "운계층": .24, "합충형파해": .12, "음양": .04}
LAYER_WEIGHTS = {"대운": .30, "세운": .25, "월운": .20, "일운": .15, "시운": .10}


def parse_draw_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    return None


def number_element(number: int) -> str:
    return STEM_ELEMENT[number_stem(number)]


def number_polarity(number: int) -> str:
    number_stem(number)  # range/type validation
    return "yang" if number % 2 else "yin"


def extract_saju_profile(options: dict[str, Any]) -> dict[str, Any]:
    """Keep pre-existing storage keys and add an explicit lunar-calendar standard."""
    return {
        "calendar": str(options.get(CONF_SAJU_CALENDAR, "solar")),
        "birth_date": str(options.get(CONF_SAJU_BIRTH_DATE, "") or "").strip(),
        "birth_time": str(options.get(CONF_SAJU_BIRTH_TIME, "") or "").strip(),
        "lunar_leap_month": bool(options.get(CONF_SAJU_LUNAR_LEAP_MONTH, False)),
        "gender": str(options.get(CONF_SAJU_GENDER, "") or ""),
        "birth_place": str(options.get(CONF_SAJU_BIRTH_PLACE, "") or "").strip(),
        "timezone": str(options.get(CONF_SAJU_TIMEZONE, "Asia/Seoul") or "Asia/Seoul"),
        "true_solar_time": bool(options.get(CONF_SAJU_TRUE_SOLAR_TIME, False)),
        "longitude": options.get(CONF_SAJU_LONGITUDE),
        # Existing lunar profiles keep their old Chinese conversion until the
        # user explicitly chooses Korean. Newly configured profiles use Korean.
        "lunar_standard": str(options.get("saju_lunar_standard", "chinese" if options.get(CONF_SAJU_CALENDAR) == "lunar" else "korean")),
    }


def validate_saju_profile(profile: dict[str, Any]) -> None:
    resolve_birth(profile)


def has_complete_saju_profile(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    try:
        resolve_birth(profile)
    except (SajuProfileError, TypeError, ValueError):
        return False
    return True


def build_myungri_context(latest_draw_date: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    latest = parse_draw_date(latest_draw_date)
    number_elements = {n: number_element(n) for n in range(1, 46)}
    if not profile:
        return {"status": "profile_required", "target_draw_date": (latest + timedelta(days=7)).isoformat() if latest else None,
                "number_elements": number_elements, "number_resonance": {n: .5 for n in range(1, 46)},
                "notice": "명리 추천 전에 개인 사주정보를 입력하세요", "privacy_notice": SAJU_PRIVACY_NOTICE}
    if latest is None or latest.weekday() != 5:
        raise SajuProfileError("다음 추첨일 계산에 유효한 토요일 회차 날짜가 필요합니다")
    birth, effective, metadata = resolve_birth(profile)
    target = datetime.combine(latest + timedelta(days=7), datetime.min.time()).replace(hour=20, minute=35, tzinfo=ZoneInfo("Asia/Seoul"))
    if birth > target:
        raise SajuProfileError("출생일 이전 회차를 개인 사주로 분석할 수 없습니다")
    known = metadata["birth_time_known"]
    natal = pillars_at(birth, effective, known)
    day_stem = natal["day"]["stem"]
    day_element = STEM_ELEMENT[day_stem]
    structure = structural_analysis(natal)
    favorable = favorable_analysis(day_element, structure, natal["month"]["branch"])
    target_pillars = pillars_at(target, reference_day_stem=day_stem)
    luck = luck_cycles(birth, natal, profile["gender"], target, known)
    native_events = interactions(natal)
    layers = {}
    current = luck.get("current")
    source_layers = {"세운": target_pillars["year"], "월운": target_pillars["month"],
                     "일운": target_pillars["day"], "시운": target_pillars["time"]}
    if current:
        source_layers = {"대운": pillar_record(current["ganzhi"], day_stem), **source_layers}
    for name, pillar in source_layers.items():
        events = interactions(natal, {name: pillar})
        layers[name] = {"pillar": pillar, "weight": LAYER_WEIGHTS[name], "relations": events,
                        "element_adjustments": interaction_adjustments(events, favorable["scores"])}
    # Distinguish luck-to-luck interactions as their own layer, not fake natal relations.
    luck_pillars = {name: value["pillar"] for name, value in layers.items()}
    inter_luck = interactions(luck_pillars)
    events_all = [*native_events, *inter_luck]
    for value in layers.values():
        events_all.extend(value["relations"])
    adjustment = interaction_adjustments(events_all, favorable["scores"])
    god_mass = structure["ten_god_distribution"]
    god_total = sum(god_mass.values()) or 1
    scores, traces, gods_by_number = {}, {}, {}
    layer_total = sum(item["weight"] for item in layers.values())
    for number, element in number_elements.items():
        god = ten_god(day_stem, number_stem(number))
        gods_by_number[number] = god
        # Source requires ten-god distinctions; this numerical balancing policy
        # is explicitly an application heuristic, not 偏財 => lottery success.
        ten_balance = max(0, min(1, .55 + .30 * (favorable["scores"][element] - .5) - .20 * god_mass[god] / god_total))
        layer_parts = {}
        for name, layer in layers.items():
            pillar = layer["pillar"]
            stem_e, branch_e = STEM_ELEMENT[pillar["stem"]], BRANCH_ELEMENT[pillar["branch"]]
            active = .5
            for incoming_e in (stem_e, branch_e):
                if element == GENERATED_BY[incoming_e] or element == GENERATES[incoming_e]:
                    active += .08
                if element == incoming_e:
                    active += .04
            layer_parts[name] = min(1, active + layer["element_adjustments"][element])
        parts = {"보완오행": favorable["scores"][element], "십신분포": ten_balance,
                 "운계층": sum(layer_parts[name] * layers[name]["weight"] for name in layers) / layer_total,
                 "합충형파해": .5 + adjustment[element],
                 "음양": .55 if number % 2 != (1 if STEMS.index(day_stem) % 2 == 0 else 0) else .5}
        scores[number] = sum(parts[key] * NUMBER_WEIGHTS[key] for key in NUMBER_WEIGHTS)
        traces[number] = {"element": KO[element], "ten_god": god,
                          "parts": parts, "weighted_total": scores[number], "luck_layers": layer_parts}
    interaction_summary = {
        "stem_harmony": [e for e in events_all if e["type"] == "천간합"],
        "stem_clash": [e for e in events_all if e["type"] == "천간충"],
        "branch_harmony": [e for e in events_all if e["type"] in ("육합", "삼합", "방합")],
        "branch_clash_harm_punishment": [e for e in events_all if e["type"] in ("육충", "육해", "파", "자형", "삼형", "자묘형")],
    }
    return {"status": "ready", "profile": metadata, "natal_pillars": natal,
            "day_master": f"{STEM_KO[day_stem]}({day_stem})", "day_master_element": day_element,
            "day_master_element_ko": KO[day_element], "day_master_polarity": "yang" if STEMS.index(day_stem) % 2 == 0 else "yin",
            "strength": structure["strength"], "support_ratio": structure["support_ratio"],
            "element_balance": {KO[e]: round(v, 6) for e, v in structure["balance"].items()},
            "structural_analysis": structure, "favorable_analysis": favorable,
            "favorable_elements": favorable["favorable_elements"],
            "favorable_elements_ko": [KO[e] for e in favorable["favorable_elements"]],
            "avoid_elements": [], "avoid_elements_ko": [],
            "ten_god_element_roles": {k: KO[v] for k, v in favorable["roles"].items()},
            "luck_cycle": luck, "luck_layers": layers, "inter_luck_relations": inter_luck,
            "target_draw_date": target.date().isoformat(), "target_draw_time": "20:35",
            "target_timezone": "Asia/Seoul", "target_time_basis": "예정 시각 가정; 실제 공 추출 시각 아님",
            "target_pillars": target_pillars, "target_day": target_pillars["day"]["ganzhi"],
            "interactions": interaction_summary, "native_interactions": native_events,
            "number_elements": number_elements, "number_roles": gods_by_number,
            "number_resonance": scores, "number_score_trace": traces,
            "number_score_weights": NUMBER_WEIGHTS, "shensha": shensha(natal),
            "rule_version": SOURCE_RULESET,
            "rule_sources": {"ten_gods": "프롬프트 §1.2.4", "hidden_stems": "§1.2.9", "growth_stages": "§1.2.10", "relations": "§1.2.14", "pattern_and_favorable": "§1.2.15", "luck_cycles": "§1.2.16", "number_mapping": "§1.2.3 + 끝자리/음양 반복배속은 현대 응용"},
            "calculation_warnings": ["프롬프트 §1.2.11 일진 기준일표 오류는 KASI 2000-01-01 무오 기준으로 교정", "亥 지장간 戊23/甲17/壬60은 제공 프롬프트 학파 기준", "지지 십신 조견표와 지장간 정기 십신이 다른 항목은 둘 다 표시하고 점수에는 지장간 정기를 사용", "성립 조건 미정의 종격·화격은 확정하지 않음", "신살·납음·12운성은 참고 분류이며 당첨 가산점 아님"],
            "notice": SAJU_NOTICE, "privacy_notice": SAJU_PRIVACY_NOTICE}


def combo_myungri_score(combo: tuple[int, ...], context: dict[str, Any]) -> float:
    if context.get("status") != "ready":
        return .5
    elements = [context["number_elements"][n] for n in combo]
    counts = Counter(elements)
    resonance = fmean(context["number_resonance"][n] for n in combo)
    favorable = set(context["favorable_elements"])
    return (.45 * resonance + .20 * sum(e in favorable for e in elements) / len(elements)
            + .15 * len(counts) / 5 + .10 * (1 - abs(sum(n % 2 for n in combo) - 3) / 3)
            + .10 * max(0, 1 - max(0, max(counts.values()) - 2) / 4))


def combo_myungri_details(combo: tuple[int, ...], context: dict[str, Any]) -> dict[str, Any]:
    if context.get("status") != "ready":
        return {"saju_profile_status": "설정 필요", "traditional_notice": context.get("notice")}
    labels = dict(zip(("year", "month", "day", "time"), PILLAR_LABELS, strict=True))
    counts = Counter(context["number_elements"][n] for n in combo)
    # Do not replicate raw birth input in recommendation/summary/history attributes.
    clock_keys = ("lunar_standard", "birth_time_known", "true_solar_time", "true_solar_correction_minutes", "year_month_clock", "day_hour_rule")
    return {"saju_profile_status": "준비됨", "traditional_method": "개인 사주 원국·격국 후보·억부/조후/통관/병약·대운/세운/월운/일시운·하도 응용",
            "four_pillars": {labels[k]: p["ganzhi"] for k, p in context["natal_pillars"].items()},
            "pillar_details": context["natal_pillars"], "day_master": context["day_master"],
            "day_master_element": context["day_master_element_ko"], "day_master_strength": context["strength"],
            "support_ratio": context["support_ratio"], "five_element_balance": context["element_balance"],
            "ten_god_element_roles": context["ten_god_element_roles"],
            "favorable_elements": context["favorable_elements_ko"], "avoid_elements": [],
            "current_daewoon": context["luck_cycle"], "target_draw_date": context["target_draw_date"],
            "target_draw_time": context["target_draw_time"], "target_timezone": context["target_timezone"],
            "target_draw_four_pillars": {labels[k]: p["ganzhi"] for k, p in context["target_pillars"].items()},
            "target_interactions": context["interactions"], "structural_analysis": context["structural_analysis"],
            "favorable_analysis": context["favorable_analysis"], "luck_layers": context["luck_layers"],
            "number_five_elements": {str(n): KO[context["number_elements"][n]] for n in combo},
            "number_ten_god_roles": {str(n): context["number_roles"][n] for n in combo},
            "number_score_trace": {str(n): context["number_score_trace"][n] for n in combo},
            "number_score_weights": context["number_score_weights"],
            "five_element_counts": {KO[e]: counts[e] for e in ELEMENTS},
            "favorable_number_count": sum(context["number_elements"][n] in context["favorable_elements"] for n in combo),
            "yang_count": sum(n % 2 for n in combo), "yin_count": sum(n % 2 == 0 for n in combo),
            "calendar_rules": {k: context["profile"][k] for k in clock_keys},
            "shensha": context["shensha"], "rule_version": SOURCE_RULESET, "rule_sources": context["rule_sources"],
            "calculation_warnings": context["calculation_warnings"],
            "traditional_notice": SAJU_NOTICE, "privacy_notice": SAJU_PRIVACY_NOTICE}


def saju_profile_sensor_attributes(profile: dict[str, Any] | None, latest_draw_date: str) -> dict[str, Any]:
    context = build_myungri_context(latest_draw_date, profile)
    if context.get("status") != "ready":
        return {"status": "profile_required", "message": "구성 → 명리 사주정보 입력·수정에서 저장하세요", "privacy_notice": SAJU_PRIVACY_NOTICE}
    details = combo_myungri_details((1, 2, 3, 4, 5, 6), context)
    for key in ("number_five_elements", "number_ten_god_roles", "number_score_trace", "favorable_number_count", "five_element_counts", "yang_count", "yin_count"):
        details.pop(key, None)
    return {"status": "ready", **details}
