"""Personal Four Pillars (사주명리) helpers for Lotto 6/45.

The implementation uses ``lunar_python`` for solar/lunar conversion, exact
sexagenary year/month/day/hour pillars, hidden stems, Ten Gods, NaYin and luck
cycles.  The scoring layer is deliberately described as a reproducible
*traditional/cultural heuristic*, not a scientifically validated lottery model.

Raw birth input stays in the user's Home Assistant config entry.  This module
returns derived Four Pillars context to the local analysis engine; it never
sends birth data to the shared lottery mirror or to Home Assistant AI Tasks.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import math
from statistics import fmean
from typing import Any, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lunar_python import Lunar, Solar

from .const import (
    CONF_SAJU_BIRTH_DATE,
    CONF_SAJU_BIRTH_PLACE,
    CONF_SAJU_BIRTH_TIME,
    CONF_SAJU_CALENDAR,
    CONF_SAJU_GENDER,
    CONF_SAJU_LONGITUDE,
    CONF_SAJU_LUNAR_LEAP_MONTH,
    CONF_SAJU_TIMEZONE,
    CONF_SAJU_TRUE_SOLAR_TIME,
    DEFAULT_SAJU_CALENDAR,
    DEFAULT_SAJU_TIMEZONE,
    DEFAULT_SAJU_TRUE_SOLAR_TIME,
    SAJU_NOTICE,
    SAJU_PRIVACY_NOTICE,
)


class SajuProfileError(ValueError):
    """Raised when a required personal Saju profile value is invalid."""


ELEMENT_KO: Final = {
    "wood": "목",
    "fire": "화",
    "earth": "토",
    "metal": "금",
    "water": "수",
}
ELEMENT_HANJA: Final = {
    "wood": "木",
    "fire": "火",
    "earth": "土",
    "metal": "金",
    "water": "水",
}
ELEMENT_FROM_HANJA: Final = {value: key for key, value in ELEMENT_HANJA.items()}

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
GENERATED_BY: Final = {value: key for key, value in GENERATES.items()}
CONTROLLED_BY: Final = {value: key for key, value in CONTROLS.items()}

STEM_INFO: Final = {
    "甲": ("갑", "wood", "yang"),
    "乙": ("을", "wood", "yin"),
    "丙": ("병", "fire", "yang"),
    "丁": ("정", "fire", "yin"),
    "戊": ("무", "earth", "yang"),
    "己": ("기", "earth", "yin"),
    "庚": ("경", "metal", "yang"),
    "辛": ("신", "metal", "yin"),
    "壬": ("임", "water", "yang"),
    "癸": ("계", "water", "yin"),
}
BRANCH_INFO: Final = {
    "子": ("자", "water", "yang"),
    "丑": ("축", "earth", "yin"),
    "寅": ("인", "wood", "yang"),
    "卯": ("묘", "wood", "yin"),
    "辰": ("진", "earth", "yang"),
    "巳": ("사", "fire", "yin"),
    "午": ("오", "fire", "yang"),
    "未": ("미", "earth", "yin"),
    "申": ("신", "metal", "yang"),
    "酉": ("유", "metal", "yin"),
    "戌": ("술", "earth", "yang"),
    "亥": ("해", "water", "yin"),
}

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

STEM_COMBINATIONS: Final = {
    frozenset(("甲", "己")): "갑기합토",
    frozenset(("乙", "庚")): "을경합금",
    frozenset(("丙", "辛")): "병신합수",
    frozenset(("丁", "壬")): "정임합목",
    frozenset(("戊", "癸")): "무계합화",
}
STEM_CLASHES: Final = {
    frozenset(("甲", "庚")): "갑경충",
    frozenset(("乙", "辛")): "을신충",
    frozenset(("丙", "壬")): "병임충",
    frozenset(("丁", "癸")): "정계충",
}
BRANCH_COMBINATIONS: Final = {
    frozenset(("子", "丑")): "자축합",
    frozenset(("寅", "亥")): "인해합",
    frozenset(("卯", "戌")): "묘술합",
    frozenset(("辰", "酉")): "진유합",
    frozenset(("巳", "申")): "사신합",
    frozenset(("午", "未")): "오미합",
}
BRANCH_CLASHES: Final = {
    frozenset(("子", "午")): "자오충",
    frozenset(("丑", "未")): "축미충",
    frozenset(("寅", "申")): "인신충",
    frozenset(("卯", "酉")): "묘유충",
    frozenset(("辰", "戌")): "진술충",
    frozenset(("巳", "亥")): "사해충",
}
BRANCH_HARMS: Final = {
    frozenset(("子", "未")): "자미해",
    frozenset(("丑", "午")): "축오해",
    frozenset(("寅", "巳")): "인사해",
    frozenset(("卯", "辰")): "묘진해",
    frozenset(("申", "亥")): "신해해",
    frozenset(("酉", "戌")): "유술해",
}
THREE_HARMONIES: Final = {
    frozenset(("申", "子", "辰")): "신자진 수국",
    frozenset(("亥", "卯", "未")): "해묘미 목국",
    frozenset(("寅", "午", "戌")): "인오술 화국",
    frozenset(("巳", "酉", "丑")): "사유축 금국",
}
THREE_PUNISHMENTS: Final = {
    frozenset(("寅", "巳", "申")): "인사신 삼형",
    frozenset(("丑", "戌", "未")): "축술미 삼형",
}

PILLAR_LABELS: Final = ("년주", "월주", "일주", "시주")


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


def number_element(number: int) -> str:
    """Return the He Tu five-element group for a Lotto number."""
    if number < 1 or number > 45:
        raise ValueError("Lotto number must be between 1 and 45")
    return HETU_BY_LAST_DIGIT[number % 10]


def number_polarity(number: int) -> str:
    """Use traditional odd/yang and even/yin numeric polarity."""
    return "yang" if number % 2 else "yin"


def extract_saju_profile(options: dict[str, Any]) -> dict[str, Any]:
    """Extract a normalized personal profile from a config-entry options dict."""
    return {
        "calendar": str(options.get(CONF_SAJU_CALENDAR, DEFAULT_SAJU_CALENDAR)),
        "birth_date": str(options.get(CONF_SAJU_BIRTH_DATE, "") or ""),
        "birth_time": str(options.get(CONF_SAJU_BIRTH_TIME, "") or ""),
        "lunar_leap_month": bool(options.get(CONF_SAJU_LUNAR_LEAP_MONTH, False)),
        "gender": str(options.get(CONF_SAJU_GENDER, "") or ""),
        "birth_place": str(options.get(CONF_SAJU_BIRTH_PLACE, "") or ""),
        "timezone": str(options.get(CONF_SAJU_TIMEZONE, DEFAULT_SAJU_TIMEZONE) or DEFAULT_SAJU_TIMEZONE),
        "true_solar_time": bool(options.get(CONF_SAJU_TRUE_SOLAR_TIME, DEFAULT_SAJU_TRUE_SOLAR_TIME)),
        "longitude": options.get(CONF_SAJU_LONGITUDE),
    }


def has_complete_saju_profile(profile: dict[str, Any] | None) -> bool:
    """Return whether the mandatory personal birth fields are present and valid."""
    if not profile:
        return False
    required = ("birth_date", "birth_time", "gender", "birth_place", "timezone")
    if any(not str(profile.get(key, "")).strip() for key in required):
        return False
    if str(profile.get("calendar")) not in {"solar", "lunar"}:
        return False
    if str(profile.get("gender")) not in {"male", "female"}:
        return False
    if bool(profile.get("true_solar_time")) and profile.get("longitude") in (None, ""):
        return False
    try:
        _parse_date(str(profile["birth_date"]))
        _parse_time(str(profile["birth_time"]))
        ZoneInfo(str(profile["timezone"]))
        if profile.get("longitude") not in (None, ""):
            longitude = float(profile["longitude"])
            if longitude < -180 or longitude > 180:
                return False
    except (ValueError, ZoneInfoNotFoundError):
        return False
    return True


def validate_saju_profile(profile: dict[str, Any]) -> None:
    """Raise a user-facing error when a personal Saju profile is invalid."""
    if not has_complete_saju_profile(profile):
        raise SajuProfileError(
            "명리 권장을 사용하려면 생년월일·출생시간·양/음력·성별·출생지·시간대를 모두 입력해야 합니다. "
            "진태양시 보정을 사용하면 출생지 경도도 필요합니다."
        )
    try:
        _solar_from_profile(profile)
    except Exception as err:  # lunar_python raises generic Exception for invalid lunar dates.
        raise SajuProfileError(f"사주 출생정보를 계산할 수 없습니다: {err}") from err


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except ValueError as err:
        raise SajuProfileError("생년월일 형식이 올바르지 않습니다") from err


def _parse_time(value: str) -> tuple[int, int]:
    text = value.strip()
    try:
        hour, minute = (int(part) for part in text[:5].split(":"))
    except (ValueError, TypeError) as err:
        raise SajuProfileError("출생시간 형식이 올바르지 않습니다") from err
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise SajuProfileError("출생시간 범위가 올바르지 않습니다")
    return hour, minute


def _equation_of_time_minutes(value: date) -> float:
    """Return a standard approximation of the equation of time in minutes."""
    n = value.timetuple().tm_yday
    b = 2.0 * math.pi * (n - 81) / 364.0
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def _true_solar_adjustment(local_dt: datetime, timezone: str, longitude: float) -> tuple[datetime, float]:
    """Apply longitude + equation-of-time correction to local civil time.

    This is an optional advanced setting because Korean/Chinese schools differ on
    whether civil standard time or true solar time should be used for the hour
    pillar.  The correction is disclosed in sensor attributes.
    """
    tz = ZoneInfo(timezone)
    aware = local_dt.replace(tzinfo=tz)
    offset = aware.utcoffset()
    if offset is None:
        raise SajuProfileError("출생 시간대의 UTC 오프셋을 계산할 수 없습니다")
    standard_meridian = (offset.total_seconds() / 3600.0) * 15.0
    correction = 4.0 * (longitude - standard_meridian) + _equation_of_time_minutes(local_dt.date())
    return local_dt + timedelta(minutes=correction), correction


def _solar_from_profile(profile: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Convert configured solar/lunar birth input to a Solar instance."""
    birth_date = _parse_date(str(profile["birth_date"]))
    hour, minute = _parse_time(str(profile["birth_time"]))
    calendar = str(profile.get("calendar", DEFAULT_SAJU_CALENDAR))

    if calendar == "lunar":
        lunar_month = -birth_date.month if bool(profile.get("lunar_leap_month")) else birth_date.month
        lunar = Lunar.fromYmdHms(birth_date.year, lunar_month, birth_date.day, hour, minute, 0)
        solar = lunar.getSolar()
    else:
        solar = Solar.fromYmdHms(birth_date.year, birth_date.month, birth_date.day, hour, minute, 0)
        lunar = solar.getLunar()

    civil_dt = datetime(
        solar.getYear(), solar.getMonth(), solar.getDay(), solar.getHour(), solar.getMinute(), 0
    )
    correction = 0.0
    effective_dt = civil_dt
    if bool(profile.get("true_solar_time")):
        effective_dt, correction = _true_solar_adjustment(
            civil_dt,
            str(profile.get("timezone", DEFAULT_SAJU_TIMEZONE)),
            float(profile["longitude"]),
        )
        solar = Solar.fromYmdHms(
            effective_dt.year,
            effective_dt.month,
            effective_dt.day,
            effective_dt.hour,
            effective_dt.minute,
            0,
        )
        lunar = solar.getLunar()

    meta = {
        "input_calendar": calendar,
        "birth_place": str(profile.get("birth_place", "")),
        "birth_timezone": str(profile.get("timezone", DEFAULT_SAJU_TIMEZONE)),
        "birth_solar": civil_dt.strftime("%Y-%m-%d %H:%M"),
        "birth_lunar": lunar.toString(),
        "effective_birth_time": effective_dt.strftime("%Y-%m-%d %H:%M"),
        "true_solar_time": bool(profile.get("true_solar_time")),
        "true_solar_correction_minutes": round(correction, 2),
        "longitude": float(profile["longitude"]) if profile.get("longitude") not in (None, "") else None,
    }
    return solar, meta


def _element_from_stem(stem: str) -> str:
    return STEM_INFO[stem][1]


def _element_from_branch(branch: str) -> str:
    return BRANCH_INFO[branch][1]


def _stem_display(stem: str) -> str:
    return f"{STEM_INFO[stem][0]}({stem})"


def _branch_display(branch: str) -> str:
    return f"{BRANCH_INFO[branch][0]}({branch})"


def _pillar_dict(eight_char: Any) -> dict[str, Any]:
    """Return full Four Pillars metadata from lunar_python EightChar."""
    pillars = [
        (
            "year",
            eight_char.getYear(),
            eight_char.getYearGan(),
            eight_char.getYearZhi(),
            list(eight_char.getYearHideGan()),
            eight_char.getYearWuXing(),
            eight_char.getYearNaYin(),
            eight_char.getYearShiShenGan(),
            list(eight_char.getYearShiShenZhi()),
            eight_char.getYearDiShi(),
        ),
        (
            "month",
            eight_char.getMonth(),
            eight_char.getMonthGan(),
            eight_char.getMonthZhi(),
            list(eight_char.getMonthHideGan()),
            eight_char.getMonthWuXing(),
            eight_char.getMonthNaYin(),
            eight_char.getMonthShiShenGan(),
            list(eight_char.getMonthShiShenZhi()),
            eight_char.getMonthDiShi(),
        ),
        (
            "day",
            eight_char.getDay(),
            eight_char.getDayGan(),
            eight_char.getDayZhi(),
            list(eight_char.getDayHideGan()),
            eight_char.getDayWuXing(),
            eight_char.getDayNaYin(),
            eight_char.getDayShiShenGan(),
            list(eight_char.getDayShiShenZhi()),
            eight_char.getDayDiShi(),
        ),
        (
            "time",
            eight_char.getTime(),
            eight_char.getTimeGan(),
            eight_char.getTimeZhi(),
            list(eight_char.getTimeHideGan()),
            eight_char.getTimeWuXing(),
            eight_char.getTimeNaYin(),
            eight_char.getTimeShiShenGan(),
            list(eight_char.getTimeShiShenZhi()),
            eight_char.getTimeDiShi(),
        ),
    ]
    result: dict[str, Any] = {}
    for key, ganzhi, stem, branch, hidden, wuxing, nayin, ten_stem, ten_branch, stage in pillars:
        result[key] = {
            "ganzhi": ganzhi,
            "stem": stem,
            "stem_display": _stem_display(stem),
            "stem_element": ELEMENT_KO[_element_from_stem(stem)],
            "branch": branch,
            "branch_display": _branch_display(branch),
            "branch_element": ELEMENT_KO[_element_from_branch(branch)],
            "hidden_stems": hidden,
            "wuxing": wuxing,
            "nayin": nayin,
            "ten_god_stem": ten_stem,
            "ten_gods_branch": ten_branch,
            "growth_stage": stage,
        }
    return result


def _weighted_element_balance(pillars: dict[str, Any]) -> dict[str, float]:
    """Estimate element strength with month branch and hidden stems emphasized."""
    counts = {element: 0.0 for element in ELEMENT_KO}
    for key in ("year", "month", "day", "time"):
        pillar = pillars[key]
        stem = str(pillar["stem"])
        branch = str(pillar["branch"])
        counts[_element_from_stem(stem)] += 1.0
        counts[_element_from_branch(branch)] += 1.65 if key == "month" else 1.0
        for index, hidden in enumerate(pillar["hidden_stems"]):
            if hidden not in STEM_INFO:
                continue
            weights = (0.42, 0.24, 0.12)
            counts[_element_from_stem(hidden)] += weights[min(index, 2)]
    total = sum(counts.values()) or 1.0
    return {element: counts[element] / total for element in counts}


def _day_master_roles(day_element: str) -> dict[str, str]:
    return {
        "companion": day_element,
        "resource": GENERATED_BY[day_element],
        "output": GENERATES[day_element],
        "wealth": CONTROLS[day_element],
        "officer": CONTROLLED_BY[day_element],
    }


def _strength_and_favorable(day_element: str, balance: dict[str, float]) -> dict[str, Any]:
    roles = _day_master_roles(day_element)
    support = balance[roles["companion"]] + balance[roles["resource"]]
    if support >= 0.54:
        strength = "신강"
        favorable = [roles["output"], roles["wealth"], roles["officer"]]
        avoid = [roles["companion"], roles["resource"]]
    elif support <= 0.46:
        strength = "신약"
        favorable = [roles["resource"], roles["companion"]]
        avoid = [roles["wealth"], roles["officer"]]
    else:
        strength = "중화"
        least = sorted(ELEMENT_KO, key=lambda element: (balance[element], element))
        favorable = least[:2] + [roles["output"]]
        favorable = list(dict.fromkeys(favorable))
        avoid = []
    return {
        "strength": strength,
        "support_ratio": round(support, 4),
        "roles": roles,
        "favorable_elements": favorable,
        "avoid_elements": avoid,
    }


def _interaction_summary(birth: dict[str, Any], target: dict[str, Any]) -> dict[str, list[str]]:
    """Compare natal pillars with target draw pillars using common 명리 relations."""
    stem_positive: list[str] = []
    stem_negative: list[str] = []
    branch_positive: list[str] = []
    branch_negative: list[str] = []
    birth_items = [(PILLAR_LABELS[i], birth[key]) for i, key in enumerate(("year", "month", "day", "time"))]
    target_items = [(f"추첨{PILLAR_LABELS[i]}", target[key]) for i, key in enumerate(("year", "month", "day", "time"))]

    for birth_label, bp in birth_items:
        for target_label, tp in target_items:
            stem_pair = frozenset((str(bp["stem"]), str(tp["stem"])))
            if stem_pair in STEM_COMBINATIONS:
                stem_positive.append(f"{birth_label}-{target_label} {STEM_COMBINATIONS[stem_pair]}")
            if stem_pair in STEM_CLASHES:
                stem_negative.append(f"{birth_label}-{target_label} {STEM_CLASHES[stem_pair]}")
            branch_pair = frozenset((str(bp["branch"]), str(tp["branch"])))
            if branch_pair in BRANCH_COMBINATIONS:
                branch_positive.append(f"{birth_label}-{target_label} {BRANCH_COMBINATIONS[branch_pair]}")
            if branch_pair in BRANCH_CLASHES:
                branch_negative.append(f"{birth_label}-{target_label} {BRANCH_CLASHES[branch_pair]}")
            if branch_pair in BRANCH_HARMS:
                branch_negative.append(f"{birth_label}-{target_label} {BRANCH_HARMS[branch_pair]}")

    all_branches = {str(item[1]["branch"]) for item in birth_items + target_items}
    for group, name in THREE_HARMONIES.items():
        if group <= all_branches:
            branch_positive.append(name)
    for group, name in THREE_PUNISHMENTS.items():
        if group <= all_branches:
            branch_negative.append(name)

    return {
        "stem_harmony": sorted(set(stem_positive)),
        "stem_clash": sorted(set(stem_negative)),
        "branch_harmony": sorted(set(branch_positive)),
        "branch_clash_harm_punishment": sorted(set(branch_negative)),
    }


def _luck_cycle(eight_char: Any, gender: str, target_year: int) -> dict[str, Any]:
    """Return current DaYun plus its start metadata when calculable."""
    gender_value = 1 if gender == "male" else 0
    try:
        yun = eight_char.getYun(gender_value)
        selected = None
        for dayun in yun.getDaYun(12):
            start = int(dayun.getStartYear())
            end = int(dayun.getEndYear()) if hasattr(dayun, "getEndYear") else start + 9
            if start <= target_year <= end:
                selected = dayun
                break
        return {
            "direction": "순행" if yun.isForward() else "역행",
            "start_after": {
                "years": int(yun.getStartYear()),
                "months": int(yun.getStartMonth()),
                "days": int(yun.getStartDay()),
            },
            "current": (
                {
                    "ganzhi": selected.getGanZhi(),
                    "start_year": int(selected.getStartYear()),
                    "end_year": int(selected.getEndYear()) if hasattr(selected, "getEndYear") else int(selected.getStartYear()) + 9,
                    "start_age": int(selected.getStartAge()),
                    "end_age": int(selected.getEndAge()) if hasattr(selected, "getEndAge") else int(selected.getStartAge()) + 9,
                }
                if selected is not None
                else None
            ),
        }
    except Exception:
        return {"direction": None, "start_after": None, "current": None}


def _relation_score(day_element: str, candidate_element: str) -> float:
    if candidate_element == day_element:
        return 0.82
    if GENERATED_BY[day_element] == candidate_element:
        return 0.90
    if GENERATES[day_element] == candidate_element:
        return 0.86
    if CONTROLS[day_element] == candidate_element:
        return 0.76
    if CONTROLLED_BY[day_element] == candidate_element:
        return 0.66
    return 0.50


def _element_from_ganzhi(ganzhi: str) -> tuple[str | None, str | None]:
    if len(ganzhi) < 2:
        return None, None
    stem = _element_from_stem(ganzhi[0]) if ganzhi[0] in STEM_INFO else None
    branch = _element_from_branch(ganzhi[1]) if ganzhi[1] in BRANCH_INFO else None
    return stem, branch


def build_myungri_context(
    latest_draw_date: str,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build personal natal + luck-cycle + target-draw Four Pillars context."""
    latest = parse_draw_date(latest_draw_date)
    number_elements = {number: number_element(number) for number in range(1, 46)}
    neutral = {number: 0.5 for number in range(1, 46)}

    if not has_complete_saju_profile(profile):
        return {
            "status": "profile_required",
            "target_draw_date": (latest + timedelta(days=7)).isoformat() if latest else None,
            "number_elements": number_elements,
            "number_resonance": neutral,
            "notice": "명리 권장 사용 전 개인 사주정보 입력이 필요합니다.",
            "privacy_notice": SAJU_PRIVACY_NOTICE,
        }
    validate_saju_profile(profile or {})
    solar, birth_meta = _solar_from_profile(profile or {})
    natal_lunar = solar.getLunar()
    eight_char = natal_lunar.getEightChar()
    eight_char.setSect(2)
    natal_pillars = _pillar_dict(eight_char)
    day_stem = str(eight_char.getDayGan())
    day_element = _element_from_stem(day_stem)
    day_polarity = STEM_INFO[day_stem][2]
    balance = _weighted_element_balance(natal_pillars)
    strength = _strength_and_favorable(day_element, balance)

    target = (latest + timedelta(days=7)) if latest else date.today()
    target_solar = Solar.fromYmdHms(target.year, target.month, target.day, 20, 35, 0)
    target_eight_char = target_solar.getLunar().getEightChar()
    target_eight_char.setSect(2)
    target_pillars = _pillar_dict(target_eight_char)
    interactions = _interaction_summary(natal_pillars, target_pillars)
    luck = _luck_cycle(eight_char, str(profile.get("gender")), target.year)

    favorable: list[str] = list(strength["favorable_elements"])
    avoid: list[str] = list(strength["avoid_elements"])
    min_balance = min(balance.values())
    max_balance = max(balance.values()) or 1.0
    luck_current = luck.get("current") or {}
    luck_stem_element, luck_branch_element = _element_from_ganzhi(str(luck_current.get("ganzhi", "")))
    target_day_element = _element_from_stem(str(target_pillars["day"]["stem"]))
    target_day_branch_element = _element_from_branch(str(target_pillars["day"]["branch"]))

    resonance: dict[int, float] = {}
    role_by_number: dict[int, str] = {}
    roles: dict[str, str] = dict(strength["roles"])
    role_scores = {
        "resource": 1.0 if strength["strength"] == "신약" else 0.68,
        "companion": 0.94 if strength["strength"] == "신약" else 0.62,
        "output": 0.96 if strength["strength"] != "신약" else 0.72,
        "wealth": 0.91 if strength["strength"] != "신약" else 0.64,
        "officer": 0.88 if strength["strength"] != "신약" else 0.62,
    }
    element_to_role = {element: role for role, element in roles.items()}

    for number, element in number_elements.items():
        role = element_to_role[element]
        role_by_number[number] = role
        if element in favorable:
            favorable_score = 1.0 - 0.08 * favorable.index(element)
        elif element in avoid:
            favorable_score = 0.42
        else:
            favorable_score = 0.68
        deficiency_score = 1.0 - max(0.0, (balance[element] - min_balance) / max(max_balance - min_balance, 0.001))
        draw_score = 0.56 * _relation_score(target_day_element, element) + 0.44 * _relation_score(target_day_branch_element, element)
        luck_parts = [
            _relation_score(luck_element, element)
            for luck_element in (luck_stem_element, luck_branch_element)
            if luck_element
        ]
        luck_score = fmean(luck_parts) if luck_parts else 0.5
        polarity_score = 0.78 if number_polarity(number) != day_polarity else 0.72
        resonance[number] = (
            0.34 * favorable_score
            + 0.22 * role_scores[role]
            + 0.18 * deficiency_score
            + 0.14 * draw_score
            + 0.08 * luck_score
            + 0.04 * polarity_score
        )

    return {
        "status": "ready",
        "profile": birth_meta,
        "gender": str(profile.get("gender")),
        "natal_pillars": natal_pillars,
        "day_master": _stem_display(day_stem),
        "day_master_element": day_element,
        "day_master_element_ko": ELEMENT_KO[day_element],
        "day_master_polarity": day_polarity,
        "element_balance": {ELEMENT_KO[element]: round(value, 4) for element, value in balance.items()},
        "strength": strength["strength"],
        "support_ratio": strength["support_ratio"],
        "ten_god_element_roles": {role: ELEMENT_KO[element] for role, element in roles.items()},
        "favorable_elements": favorable,
        "favorable_elements_ko": [ELEMENT_KO[element] for element in favorable],
        "avoid_elements": avoid,
        "avoid_elements_ko": [ELEMENT_KO[element] for element in avoid],
        "luck_cycle": luck,
        "target_draw_date": target.isoformat(),
        "target_draw_time": "20:35",
        "target_pillars": target_pillars,
        "target_day": target_pillars["day"]["ganzhi"],
        "interactions": interactions,
        "number_elements": number_elements,
        "number_roles": role_by_number,
        "number_resonance": resonance,
        "notice": SAJU_NOTICE,
        "privacy_notice": SAJU_PRIVACY_NOTICE,
    }


def combo_myungri_score(combo: tuple[int, ...], context: dict[str, Any]) -> float:
    """Score a combination against the personal natal/fortune context."""
    if context.get("status") != "ready":
        return 0.5
    elements = [context["number_elements"][number] for number in combo]
    counts = Counter(elements)
    resonance = fmean(context["number_resonance"][number] for number in combo)
    favorable = set(context.get("favorable_elements", []))
    favorable_share = sum(element in favorable for element in elements) / len(elements)
    element_diversity = min(len(counts) / 5.0, 1.0)
    max_count = max(counts.values(), default=0)
    concentration = 1.0 if max_count <= 2 else max(0.0, 1.0 - (max_count - 2) / 4)
    yang_count = sum(number % 2 for number in combo)
    polarity_balance = max(0.0, 1.0 - abs(yang_count - 3) / 3)
    return (
        0.45 * resonance
        + 0.20 * favorable_share
        + 0.15 * element_diversity
        + 0.10 * polarity_balance
        + 0.10 * concentration
    )


def combo_myungri_details(combo: tuple[int, ...], context: dict[str, Any]) -> dict[str, Any]:
    """Return detailed, user-facing personal Four Pillars rationale."""
    if context.get("status") != "ready":
        return {
            "saju_profile_status": "설정 필요",
            "traditional_notice": context.get("notice"),
            "privacy_notice": context.get("privacy_notice"),
        }
    element_by_number = {
        str(number): ELEMENT_KO[context["number_elements"][number]] for number in combo
    }
    role_by_number = {
        str(number): context["number_roles"][number] for number in combo
    }
    counts = Counter(context["number_elements"][number] for number in combo)
    favorable = set(context.get("favorable_elements", []))
    return {
        "saju_profile_status": "준비됨",
        "traditional_method": "개인 사주 원국 + 대운 + 추첨일 사주 + 하도 수리오행",
        "birth_profile": dict(context.get("profile", {})),
        "four_pillars": {
            label: context["natal_pillars"][key]["ganzhi"]
            for label, key in zip(PILLAR_LABELS, ("year", "month", "day", "time"), strict=True)
        },
        "pillar_details": context.get("natal_pillars"),
        "day_master": context.get("day_master"),
        "day_master_element": context.get("day_master_element_ko"),
        "day_master_strength": context.get("strength"),
        "support_ratio": context.get("support_ratio"),
        "five_element_balance": context.get("element_balance"),
        "ten_god_element_roles": context.get("ten_god_element_roles"),
        "favorable_elements": context.get("favorable_elements_ko"),
        "avoid_elements": context.get("avoid_elements_ko"),
        "current_daewoon": context.get("luck_cycle"),
        "target_draw_date": context.get("target_draw_date"),
        "target_draw_time": context.get("target_draw_time"),
        "target_draw_four_pillars": {
            label: context["target_pillars"][key]["ganzhi"]
            for label, key in zip(PILLAR_LABELS, ("year", "month", "day", "time"), strict=True)
        },
        "target_interactions": context.get("interactions"),
        "number_five_elements": element_by_number,
        "number_ten_god_roles": role_by_number,
        "favorable_number_count": sum(
            context["number_elements"][number] in favorable for number in combo
        ),
        "five_element_counts": {
            ELEMENT_KO[element]: counts.get(element, 0)
            for element in ("wood", "fire", "earth", "metal", "water")
        },
        "yang_count": sum(number % 2 for number in combo),
        "yin_count": sum(number % 2 == 0 for number in combo),
        "traditional_notice": context.get("notice"),
        "privacy_notice": context.get("privacy_notice"),
    }


def saju_profile_sensor_attributes(profile: dict[str, Any] | None, latest_draw_date: str) -> dict[str, Any]:
    """Build attributes for the dedicated Saju profile/status sensor."""
    context = build_myungri_context(latest_draw_date, profile)
    if context.get("status") != "ready":
        return {
            "status": "profile_required",
            "message": "명리 권장 기능을 사용하려면 통합 구성에서 개인 사주정보를 입력하세요.",
            "required_fields": [
                "양력/음력",
                "생년월일",
                "출생시간",
                "성별",
                "출생지",
                "시간대",
            ],
            "privacy_notice": SAJU_PRIVACY_NOTICE,
            "traditional_notice": SAJU_NOTICE,
        }
    details = combo_myungri_details((1, 2, 3, 4, 5, 6), context)
    for key in (
        "number_five_elements",
        "number_ten_god_roles",
        "favorable_number_count",
        "five_element_counts",
        "yang_count",
        "yin_count",
    ):
        details.pop(key, None)
    details["status"] = "ready"
    return details
