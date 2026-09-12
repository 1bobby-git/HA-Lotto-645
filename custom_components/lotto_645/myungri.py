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
from datetime import UTC, date, datetime, timedelta, timezone as fixed_timezone
import math
import re
from statistics import fmean
from typing import Any, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lunar_python import Lunar, Solar
from lunar_python.util import LunarUtil
from korean_lunar_calendar import KoreanLunarCalendar

from . import saju_rules as rules

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
        _parse_birth_parts(str(profile["birth_date"]), str(profile.get("calendar", "solar")))
        _parse_time(str(profile["birth_time"]))
        ZoneInfo(str(profile["timezone"]))
        if profile.get("longitude") not in (None, ""):
            longitude = float(profile["longitude"])
            if not math.isfinite(longitude) or longitude < -180 or longitude > 180:
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


def _parse_birth_parts(value: str, calendar: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise SajuProfileError("생년월일은 YYYY-MM-DD로 입력하세요")
    year, month, day = map(int, value.split("-"))
    if not 1900 <= year <= 2050:
        raise SajuProfileError("지원 출생연도는 1900~2050입니다")
    if calendar == "solar":
        date(year, month, day)
    elif not (1 <= month <= 12 and 1 <= day <= 30):
        raise SajuProfileError("음력 월일 범위가 올바르지 않습니다")
    return year, month, day


def _parse_time(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"[0-9]{2}:[0-9]{2}(?::00)?", value):
        raise SajuProfileError("출생시간은 HH:MM으로 입력하세요")
    hour, minute = map(int, value.split(":")[:2])
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise SajuProfileError("출생시간 범위가 올바르지 않습니다")
    return hour, minute


def _civil_aware(value: datetime, zone: str) -> datetime:
    """Reject nonexistent or ambiguous DST input rather than silently choosing."""
    tz = ZoneInfo(zone)
    candidates = []
    for fold in (0, 1):
        aware = value.replace(tzinfo=tz, fold=fold)
        restored = aware.astimezone(UTC).astimezone(tz).replace(tzinfo=None)
        if restored == value:
            candidates.append(aware)
    if not candidates:
        raise SajuProfileError("서머타임 전환으로 존재하지 않는 출생시각입니다")
    if len({item.utcoffset() for item in candidates}) > 1:
        raise SajuProfileError("서머타임 중복 시각입니다. 고정 UTC 오프셋 시간대를 지정하세요")
    return candidates[0]


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
    """Korean lunar conversion; solar-term and civil clocks stay separate."""
    calendar = str(profile.get("calendar", DEFAULT_SAJU_CALENDAR))
    year, month, day = _parse_birth_parts(str(profile["birth_date"]), calendar)
    hour, minute = _parse_time(str(profile["birth_time"]))
    converter = KoreanLunarCalendar()
    if calendar == "lunar":
        leap = bool(profile.get("lunar_leap_month"))
        if not converter.setLunarDate(year, month, day, leap) or converter.isIntercalation != leap:
            raise SajuProfileError("존재하지 않는 한국 음력 날짜 또는 윤달입니다")
        year, month, day = converter.solarYear, converter.solarMonth, converter.solarDay
    elif not converter.setSolarDate(year, month, day):
        raise SajuProfileError("지원하지 않는 양력 날짜입니다")
    civil_dt = datetime(year, month, day, hour, minute)
    zone = str(profile.get("timezone", DEFAULT_SAJU_TIMEZONE))
    aware = _civil_aware(civil_dt, zone)
    if aware > datetime.now(UTC):
        raise SajuProfileError("미래 출생일은 사용할 수 없습니다")
    correction = 0.0
    effective_dt = civil_dt
    if bool(profile.get("true_solar_time")):
        effective_dt, correction = _true_solar_adjustment(civil_dt, zone, float(profile["longitude"]))
    solar = Solar.fromYmdHms(effective_dt.year, effective_dt.month, effective_dt.day,
                             effective_dt.hour, effective_dt.minute, effective_dt.second)
    return solar, {
        "input_calendar": calendar, "calendar_basis": "한국 음력 (korean_lunar_calendar 0.3.1)",
        "birth_place": str(profile.get("birth_place", "")), "birth_timezone": zone,
        "birth_solar": civil_dt.strftime("%Y-%m-%d %H:%M"),
        "birth_lunar": converter.LunarIsoFormat(),
        "effective_birth_time": effective_dt.isoformat(timespec="seconds"),
        "true_solar_time": bool(profile.get("true_solar_time")),
        "true_solar_correction_minutes": round(correction, 2),
        "longitude": float(profile["longitude"]) if profile.get("longitude") not in (None, "") else None,
        "calendar_warnings": ["진태양시 균시차는 근사식이며 경계 수분 이내는 별도 검산 권장"],
    }


def _pillar_from_ganzhi(ganzhi: str, day_stem: str) -> dict[str, Any]:
    stem, branch = ganzhi
    hidden = rules.HIDDEN[branch]
    # Same growth-cycle table as supplied section 1.2.10, in branch order.
    offsets = {"甲": 1, "乙": 6, "丙": 10, "丁": 9, "戊": 10, "己": 9, "庚": 7, "辛": 0, "壬": 4, "癸": 3}
    stages = ("장생", "목욕", "관대", "건록", "제왕", "쇠", "병", "사", "묘", "절", "태", "양")
    direction = 1 if rules.STEMS.index(day_stem) % 2 == 0 else -1
    stage = stages[(offsets[day_stem] + direction * rules.BRANCHES.index(branch)) % 12]
    return {
        "ganzhi": ganzhi, "stem": stem, "stem_display": _stem_display(stem),
        "stem_element": ELEMENT_KO[_element_from_stem(stem)],
        "branch": branch, "branch_display": _branch_display(branch),
        "branch_element": ELEMENT_KO[_element_from_branch(branch)],
        "hidden_stems": list(hidden), "hidden_stem_ratios": dict(hidden),
        "wuxing": ELEMENT_HANJA[_element_from_stem(stem)] + ELEMENT_HANJA[_element_from_branch(branch)],
        "nayin": LunarUtil.NAYIN.get(ganzhi), "ten_god_stem": rules.ten_god(day_stem, stem),
        "ten_gods_branch": [rules.ten_god(day_stem, item) for item in hidden], "growth_stage": stage,
    }


def _clock_pillars(civil: datetime, effective: datetime, zone: str) -> tuple[dict[str, Any], Any]:
    """UTC+8 astronomy clock for year/month; local/solar clock for day/hour."""
    astronomical = _civil_aware(civil, zone).astimezone(fixed_timezone(timedelta(hours=8)))
    term_lunar = Solar.fromYmdHms(astronomical.year, astronomical.month, astronomical.day,
                                  astronomical.hour, astronomical.minute, astronomical.second).getLunar()
    day_lunar = Solar.fromYmdHms(effective.year, effective.month, effective.day,
                                 effective.hour, effective.minute, effective.second).getLunar()
    day = day_lunar.getDayInGanZhiExact2()
    # The source explicitly selects same-day day pillar at 23h. Apply that day
    # stem to hour DunGan too, instead of library's next-day hour stem at 23h.
    branch_index = ((effective.hour + 1) // 2) % 12
    hour_stem_index = ((rules.STEMS.index(day[0]) % 5) * 2 + branch_index) % 10
    ganzhi = {"year": term_lunar.getYearInGanZhiExact(), "month": term_lunar.getMonthInGanZhiExact(),
              "day": day, "time": rules.STEMS[hour_stem_index] + rules.BRANCHES[branch_index]}
    return {key: _pillar_from_ganzhi(value, day[0]) for key, value in ganzhi.items()}, term_lunar


def _element_from_stem(stem: str) -> str:
    return STEM_INFO[stem][1]


def _element_from_branch(branch: str) -> str:
    return BRANCH_INFO[branch][1]


def _stem_display(stem: str) -> str:
    return f"{STEM_INFO[stem][0]}({stem})"


def _branch_display(branch: str) -> str:
    return f"{BRANCH_INFO[branch][0]}({branch})"


def _luck_cycle(pillars: dict[str, Any], term_lunar: Any, civil: datetime, zone: str, gender: str, target: date) -> dict[str, Any]:
    """Source section 1.2.16: Jie interval /3, half-up rounded starting age."""
    forward = (rules.STEMS.index(pillars["year"]["stem"]) % 2 == 0) == (gender == "male")
    jie = term_lunar.getNextJie() if forward else term_lunar.getPrevJie()
    jie_dt = datetime.fromisoformat(jie.getSolar().toYmdHms()).replace(tzinfo=fixed_timezone(timedelta(hours=8)))
    birth = _civil_aware(civil, zone)
    elapsed_days = abs((jie_dt - birth).total_seconds()) / 86400
    age = int(math.floor(elapsed_days / 3 + .5))
    ganzhi_cycle = [rules.STEMS[i % 10] + rules.BRANCHES[i % 12] for i in range(60)]
    month_index = ganzhi_cycle.index(pillars["month"]["ganzhi"])
    timeline = []
    current = None
    for index in range(12):
        start_year = civil.year + age + 10 * index
        start = date(start_year, civil.month, min(civil.day, 28) if civil.month == 2 and civil.day == 29 else civil.day)
        end_year = start_year + 10
        end = date(end_year, start.month, start.day)
        item = {"ganzhi": ganzhi_cycle[(month_index + (index + 1) * (1 if forward else -1)) % 60],
                "start_age": age + 10 * index, "end_age": age + 10 * index + 9,
                "start_date": start.isoformat(), "end_exclusive": end.isoformat(),
                "start_year": start_year, "end_year": end_year,
                "birthday_policy": "2월29일은 해당 경계연도 2월28일"}
        timeline.append(item)
        if start <= target < end:
            current = item
    return {"direction": "순행" if forward else "역행", "current": current, "timeline": timeline,
            "status": "대운 전" if current is None and target < date.fromisoformat(timeline[0]["start_date"]) else "계산됨",
            "start_after": {"years": age, "months": 0, "days": 0},
            "calculation": {"rule": "제공 문서 1.2.16: 절(Jie)까지 실제 일수 /3, 0.5 올림",
                "jie": jie.getName(), "jie_at_birth_timezone": jie_dt.astimezone(ZoneInfo(zone)).isoformat(),
                "interval_days": round(elapsed_days, 8), "unrounded_start_age": round(elapsed_days / 3, 8),
                "both_stem_and_branch_active": True}}


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
    if latest is None:
        raise SajuProfileError("추첨일을 확인할 수 없어 명리 추천을 생성하지 않습니다")
    validate_saju_profile(profile or {})
    solar, birth_meta = _solar_from_profile(profile or {})
    civil = datetime.fromisoformat(birth_meta["birth_solar"])
    effective = datetime.fromisoformat(birth_meta["effective_birth_time"])
    zone = str(profile.get("timezone", DEFAULT_SAJU_TIMEZONE))
    natal_pillars, term_lunar = _clock_pillars(civil, effective, zone)
    day_stem = natal_pillars["day"]["stem"]
    day_element = _element_from_stem(day_stem)
    day_polarity = STEM_INFO[day_stem][2]
    evaluation = rules.analyze_natal(natal_pillars, day_stem)
    balance, strength = evaluation["balance"], evaluation["strength"]
    roles = evaluation["roles"]
    target = latest + timedelta(days=7)
    # Scheduled reference, not a claim that a particular draw happened at 20:35.
    target_clock = datetime(target.year, target.month, target.day, 20, 35)
    target_pillars, _ = _clock_pillars(target_clock, target_clock, "Asia/Seoul")
    luck = _luck_cycle(natal_pillars, term_lunar, civil, zone, str(profile["gender"]), target)
    layers, layer_scores = rules.evaluate_layers(natal_pillars, target_pillars, luck, evaluation["element_preference"])
    events = [event for layer in layers.values() for event in layer["relations"]]
    interactions = {
        "stem_harmony": [str(e["positions"]) + e["symbols"] for e in events if e["kind"] == "천간합"],
        "stem_clash": [str(e["positions"]) + e["symbols"] for e in events if e["kind"] == "천간충"],
        "branch_harmony": [str(e["positions"]) + e["symbols"] for e in events if e["kind"] in {"육합", "삼합", "방합"}],
        "branch_clash_harm_punishment": [str(e["positions"]) + e["symbols"] for e in events if e["kind"] in {"육충", "파", "해", "자묘형", "자형", "삼형"}],
    }
    favorable, avoid = evaluation["favorable_elements"], evaluation["avoid_elements"]
    element_to_role = {element: role for role, element in roles.items()}
    number_gods, role_by_number, resonance, breakdown = {}, {}, {}, {}
    god_values = evaluation["ten_god_distribution"]
    max_god = max(god_values.values()) or 1.0
    for number, element in number_elements.items():
        god = rules.ten_god(day_stem, rules.number_stem(element, number_polarity(number)))
        number_gods[number] = god
        role_by_number[number] = element_to_role[element]
        preference = evaluation["element_preference"][element]
        # The polarity-specific God affects the ranking; no special 'windfall' promise.
        god_score = preference * (.75 + .25 * (1 - god_values[god] / max_god))
        parts = {"보완오행합의": .55 * preference, "십신10종": .20 * god_score,
                 "대운세운월운일시진": .25 * layer_scores[element]}
        resonance[number] = sum(parts.values())
        breakdown[number] = {key: round(value, 6) for key, value in parts.items()}
    return {
        "status": "ready", "profile": birth_meta, "gender": str(profile["gender"]),
        "natal_pillars": natal_pillars, "day_master": _stem_display(day_stem),
        "day_master_element": day_element, "day_master_element_ko": ELEMENT_KO[day_element],
        "day_master_polarity": day_polarity,
        "element_balance": {ELEMENT_KO[e]: round(v, 5) for e, v in balance.items()},
        "strength": strength, "support_ratio": evaluation["support_ratio"],
        "ten_god_element_roles": {role: ELEMENT_KO[element] for role, element in roles.items()},
        "favorable_elements": favorable, "favorable_elements_ko": [ELEMENT_KO[e] for e in favorable],
        "avoid_elements": avoid, "avoid_elements_ko": [ELEMENT_KO[e] for e in avoid],
        "luck_cycle": luck, "target_draw_date": target.isoformat(), "target_draw_time": "20:35",
        "target_timezone": "Asia/Seoul", "target_time_basis": "예정시각 가정; 실제 추첨시각 미검증",
        "target_pillars": target_pillars, "target_day": target_pillars["day"]["ganzhi"],
        "interactions": interactions, "natal_interactions": rules.relations(natal_pillars),
        "luck_layers": layers, "number_elements": number_elements, "number_roles": role_by_number,
        "number_ten_gods": number_gods, "number_resonance": resonance, "number_score_breakdown": breakdown,
        "natal_evaluation": {k: v for k, v in evaluation.items() if k not in {"balance", "roles"}},
        "calculation_policy": {"version": rules.SOURCE_RULE_VERSION,
            "day_boundary": "23시 당일 일주 및 당일 일간으로 시주 계산 (문서 1.2.8 선택 규칙)",
            "solar_terms": "UTC+8 절기 시각과 출생 절대시각 비교; 연월주/일시주 시계 분리",
            "source_day_anchor_table": "오류로 미적용; 독립 역법 검산 일진 사용",
            "scoring_notice": rules.APPLICATION_NOTICE},
        "notice": SAJU_NOTICE, "privacy_notice": SAJU_PRIVACY_NOTICE,
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
        "traditional_method": "문서 기반 개인 사주·대운·세운·월운·일시진 + 하도 수리오행 응용",
        "calculation_policy": context.get("calculation_policy"),
        "natal_evaluation": context.get("natal_evaluation"),
        "natal_interactions": context.get("natal_interactions"),
        "luck_layers": context.get("luck_layers"),
        "target_time_basis": context.get("target_time_basis"),
        "number_ten_gods": {str(n): context["number_ten_gods"][n] for n in combo},
        "number_score_breakdown": {str(n): context["number_score_breakdown"][n] for n in combo},
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
        "number_ten_gods",
        "number_score_breakdown",
        "number_ten_god_roles",
        "favorable_number_count",
        "five_element_counts",
        "yang_count",
        "yin_count",
    ):
        details.pop(key, None)
    details["status"] = "ready"
    return details
