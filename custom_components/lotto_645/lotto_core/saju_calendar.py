"""Calendar/clock layer, kept separate from cultural number scoring.

JieQi instants in lunar_python use UTC+08:00. Compare the absolute birth instant
on that clock for year/month; use the configured local (or apparent-solar)
calendar day for day/hour. The supplied prompt's inconsistent day anchor table
is not used: 2000-01-01 戊午 is checked against KASI's 2000 almanac.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from korean_lunar_calendar import KoreanLunarCalendar
from lunar_python import Lunar, Solar
from lunar_python.util import LunarUtil

from .saju_rules import STEMS, BRANCHES, pillar_record

LIBRARY_CLOCK = timezone(timedelta(hours=8))
UNKNOWN_TIME = {"미상", "unknown"}


class SajuProfileError(ValueError):
    """Invalid, unsupported or ambiguous personal birth input."""


def normalize_birth_date(value: object) -> str:
    """Normalize compact YYYYMMDD input to the canonical YYYY-MM-DD form."""
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def normalize_birth_time(value: object) -> str:
    """Normalize compact HHMM input to the canonical HH:MM form."""
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}", text):
        return f"{text[:2]}:{text[2:4]}"
    return text


def date_parts(value: str) -> tuple[int, int, int]:
    text = normalize_birth_date(value)
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match is None:
        raise SajuProfileError("생년월일은 YYYY-MM-DD 또는 YYYYMMDD 형식으로 입력하세요")
    year, month, day = map(int, match.groups())
    if not 1900 <= year <= 2050 or not 1 <= month <= 12 or not 1 <= day <= 31:
        raise SajuProfileError("지원 출생연도는 1900~2050년이며 유효한 월·일이 필요합니다")
    return year, month, day


def birth_clock(value: str) -> tuple[int, int] | None:
    text = normalize_birth_time(value)
    if text.casefold() in UNKNOWN_TIME:
        return None
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        raise SajuProfileError("출생시간은 HH:MM, HHMM 또는 '미상'으로 입력하세요")
    hour, minute = map(int, text.split(":"))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise SajuProfileError("출생시간 범위는 00:00~23:59입니다")
    return hour, minute


def localize(value: datetime, zone: ZoneInfo) -> datetime:
    """Reject DST gaps/folds rather than silently choosing a different instant."""
    candidates = []
    for fold in (0, 1):
        candidate = value.replace(tzinfo=zone, fold=fold)
        if candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == value:
            candidates.append(candidate)
    if not candidates:
        raise SajuProfileError("출생시간이 해당 시간대의 서머타임 전환으로 존재하지 않습니다")
    if len({item.utcoffset() for item in candidates}) > 1:
        raise SajuProfileError("출생시간이 서머타임 종료로 두 번 존재합니다. 확정된 표준시 시간대로 입력하세요")
    return candidates[0]


def as_solar(value: datetime) -> Solar:
    return Solar.fromYmdHms(value.year, value.month, value.day, value.hour, value.minute, value.second)


def from_solar(value: Solar, tz: timezone = LIBRARY_CLOCK) -> datetime:
    return datetime(value.getYear(), value.getMonth(), value.getDay(), value.getHour(),
                    value.getMinute(), value.getSecond(), tzinfo=tz)


def equation_of_time(value: date) -> float:
    b = 2 * math.pi * (value.timetuple().tm_yday - 81) / 364
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def resolve_birth(profile: dict[str, Any]) -> tuple[datetime, datetime, dict[str, Any]]:
    """Return civil absolute instant, pillar clock, and explicit calculation metadata."""
    if profile.get("calendar", "solar") not in ("solar", "lunar"):
        raise SajuProfileError("양력/음력을 선택하세요")
    if profile.get("gender") not in ("male", "female"):
        raise SajuProfileError("대운 순역 계산에 사용할 성별을 선택하세요")
    if not str(profile.get("birth_place", "")).strip():
        raise SajuProfileError("출생지를 입력하세요")
    try:
        zone = ZoneInfo(str(profile.get("timezone", "")))
    except (ValueError, ZoneInfoNotFoundError) as err:
        raise SajuProfileError("유효한 시간대가 필요합니다. 예: Asia/Seoul") from err
    y, m, d = date_parts(profile.get("birth_date", ""))
    clock = birth_clock(profile.get("birth_time", ""))
    standard = str(profile.get("lunar_standard", "korean"))
    if standard not in ("korean", "chinese"):
        raise SajuProfileError("음력 기준을 한국력 또는 중국력으로 선택하세요")
    lunar_date_text = None
    if profile.get("calendar") == "lunar":
        leap = bool(profile.get("lunar_leap_month", False))
        if standard == "korean":
            converter = KoreanLunarCalendar()
            if not converter.setLunarDate(y, m, d, leap) or bool(converter.isIntercalation) != leap:
                raise SajuProfileError("존재하지 않는 한국 음력 날짜 또는 윤달입니다")
            lunar_date_text = converter.LunarIsoFormat()
            y, m, d = converter.solarYear, converter.solarMonth, converter.solarDay
        else:
            try:
                lunar = Lunar.fromYmd(y, -m if leap else m, d)
                solar = lunar.getSolar()
                lunar_date_text = lunar.toString()
                y, m, d = solar.getYear(), solar.getMonth(), solar.getDay()
            except Exception as err:
                raise SajuProfileError("존재하지 않는 중국 음력 날짜 또는 윤달입니다") from err
    elif profile.get("lunar_leap_month"):
        raise SajuProfileError("양력에는 음력 윤달 옵션을 적용할 수 없습니다")
    try:
        # Noon is used only to calculate time-invariant 3-pillar values. It is
        # never emitted as a known birth hour and no hour pillar is fabricated.
        civil = datetime(y, m, d, *(clock or (12, 0)))
    except ValueError as err:
        raise SajuProfileError("존재하지 않는 양력 날짜입니다") from err
    aware = localize(civil, zone)
    if civil.date() > datetime.now(zone).date():
        raise SajuProfileError("출생일이 현재 날짜보다 미래입니다")
    longitude = profile.get("longitude")
    if longitude not in (None, ""):
        try:
            longitude = float(longitude)
        except (TypeError, ValueError) as err:
            raise SajuProfileError("경도는 숫자로 입력하세요") from err
        if not math.isfinite(longitude) or not -180 <= longitude <= 180:
            raise SajuProfileError("경도는 -180~180 사이의 유한한 숫자여야 합니다")
    correction = 0.0
    effective = civil
    if profile.get("true_solar_time"):
        if clock is None or longitude in (None, ""):
            raise SajuProfileError("진태양시 보정에는 확정된 출생시간과 경도가 필요합니다")
        correction = 4 * float(longitude) + equation_of_time(civil.date()) - aware.utcoffset().total_seconds() / 60
        effective += timedelta(minutes=correction)
    if clock is None:
        before = localize(civil.replace(hour=0), zone)
        after = localize(civil.replace(hour=23, minute=59), zone)
        if year_month(before) != year_month(after):
            raise SajuProfileError("절입일 경계에 태어나 출생시간 없이는 연·월주를 확정할 수 없습니다")
    if lunar_date_text is None:
        converter = KoreanLunarCalendar()
        if standard == "korean" and converter.setSolarDate(y, m, d):
            lunar_date_text = converter.LunarIsoFormat()
        else:
            lunar_date_text = as_solar(civil).getLunar().toString()
    metadata = {
        "input_calendar": profile.get("calendar", "solar"), "lunar_standard": standard,
        "birth_place": profile["birth_place"], "birth_timezone": str(zone),
        "birth_solar": civil.strftime("%Y-%m-%d %H:%M") if clock else civil.strftime("%Y-%m-%d") + " 시각 미상",
        "birth_lunar": lunar_date_text,
        "effective_birth_time": effective.strftime("%Y-%m-%d %H:%M") if clock else "미상 (시주 제외)",
        "birth_time_known": clock is not None, "true_solar_time": bool(profile.get("true_solar_time")),
        "true_solar_correction_minutes": round(correction, 3), "longitude": longitude,
        "year_month_clock": "절기 절대시각 비교 (lunar_python UTC+08 기준 → 출생지 시간대)",
        "day_hour_rule": "자정 일자 교체, 23시 당일 일간으로 시간 둔간 (§1.2.8)",
        "solar_time_precision": "균시차 근사식; 초 단위 천문 정밀도를 보장하지 않음",
    }
    return aware, effective, metadata


def year_month(instant: datetime) -> tuple[str, str]:
    eight = as_solar(instant.astimezone(LIBRARY_CLOCK)).getLunar().getEightChar()
    return eight.getYear(), eight.getMonth()


def pillars_at(instant: datetime, local_pillar_time: datetime | None = None, time_known: bool = True,
               reference_day_stem: str | None = None) -> dict[str, Any]:
    local = local_pillar_time or instant.replace(tzinfo=None)
    year, month = year_month(instant)
    # Midnight-based day. Independent ordinal check anchors against KASI 2000.
    day_index = (54 + (local.date() - date(2000, 1, 1)).days) % 60
    day = LunarUtil.JIA_ZI[day_index]
    day_stem = reference_day_stem or day[0]
    values = {"year": year, "month": month, "day": day}
    if time_known:
        branch_index = ((local.hour + 1) // 2) % 12
        stem_index = (2 * (STEMS.index(day[0]) % 5) + branch_index) % 10
        values["time"] = STEMS[stem_index] + BRANCHES[branch_index]
    return {key: pillar_record(gz, day_stem) for key, gz in values.items()}


def add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # February 29 anniversary convention, disclosed below
        return value.replace(year=value.year + years, day=28)


def luck_cycles(birth: datetime, natal: dict[str, Any], gender: str, target: datetime, time_known: bool) -> dict[str, Any]:
    """Prompt §1.2.16: days/3, half-up rounded age, full anniversary boundaries."""
    forward = (gender == "male") == (STEMS.index(natal["year"]["stem"]) % 2 == 0)
    lunar = as_solar(birth.astimezone(LIBRARY_CLOCK)).getLunar()
    term = lunar.getNextJie() if forward else lunar.getPrevJie()
    term_instant = from_solar(term.getSolar()).astimezone(birth.tzinfo)
    delta_days = abs((term_instant.astimezone(timezone.utc) - birth.astimezone(timezone.utc)).total_seconds()) / 86400
    age = math.floor(delta_days / 3 + .5)
    if not time_known:
        candidates = []
        for hour, minute in ((0, 0), (23, 59)):
            edge = birth.replace(hour=hour, minute=minute)
            edge_lunar = as_solar(edge.astimezone(LIBRARY_CLOCK)).getLunar()
            edge_term = edge_lunar.getNextJie() if forward else edge_lunar.getPrevJie()
            gap = abs((from_solar(edge_term.getSolar()) - edge).total_seconds()) / 86400
            candidates.append(math.floor(gap / 3 + .5))
        if len(set(candidates)) != 1:
            return {"direction": "순행" if forward else "역행", "current": None,
                    "timeline": [], "start_after": None,
                    "calculation": {"method": "prompt_v2_days_div3_half_up_rounded_age",
                                    "rounded_age_range": [min(candidates), max(candidates)],
                                    "time_known": False,
                                    "notice": "출생시간 미상으로 대운 시작 나이가 달라져 대운 점수는 제외합니다"}}
    month_index = LunarUtil.JIA_ZI.index(natal["month"]["ganzhi"])
    timeline = []
    current = None
    for index in range(1, 13):
        start = add_years(birth, age + (index - 1) * 10)
        end = add_years(start, 10)
        if not time_known:
            start, end = start.replace(hour=0, minute=0), end.replace(hour=0, minute=0)
        entry = {"ganzhi": LunarUtil.JIA_ZI[(month_index + (index if forward else -index)) % 60],
                 "start": start.isoformat(), "end_exclusive": end.isoformat(),
                 "start_year": start.year, "end_year": end.year,
                 "start_age": age + (index - 1) * 10, "end_age": age + index * 10 - 1}
        timeline.append(entry)
        if start <= target < end:
            current = entry
    return {"direction": "순행" if forward else "역행", "current": current,
            "timeline": timeline, "start_after": {"years": age, "months": 0, "days": 0},
            "calculation": {"method": "prompt_v2_days_div3_half_up_rounded_age",
                            "term": term.getName(), "term_local": term_instant.isoformat(),
                            "interval_days": round(delta_days, 6), "unrounded_age": round(delta_days / 3, 6),
                            "rounded_age": age, "time_known": time_known,
                            "boundary": "반올림 나이의 생일 시각; 2월29일은 평년2월28일, 시각 미상은 자정",
                            "notice": "프롬프트 반올림 기산법. 절기 분 단위 환산 학파와 결과가 다를 수 있음"}}
