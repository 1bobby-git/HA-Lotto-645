"""Local profile syntax only. Actual calendar calculation is server-side."""
from datetime import date
from zoneinfo import ZoneInfo
from typing import Any
from .const import *
from .saju_calendar import SajuProfileError, normalize_birth_date, normalize_birth_time

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



def validate_saju_profile(profile):
    if profile.get("calendar") not in ("solar","lunar") or profile.get("gender") not in ("male","female"):
        raise SajuProfileError("양력/음력과 성별을 확인하세요")
    raw = normalize_birth_date(profile.get("birth_date", ""))
    try:
        year,month,day = map(int,raw.split("-"))
        if not 1900<=year<=2050 or not 1<=month<=12 or not 1<=day<=31:
            raise ValueError()
        if profile.get("calendar") == "solar": date(year,month,day)
        ZoneInfo(profile.get("timezone","Asia/Seoul"))
    except (TypeError,ValueError,KeyError):
        raise SajuProfileError("생년월일과 시간대를 확인하세요") from None
    clock=normalize_birth_time(profile.get("birth_time", ""))
    if clock not in ("미상", "unknown"):
        try:
            h,m=map(int,clock.split(":")); valid=0<=h<=23 and 0<=m<=59
        except (TypeError,ValueError): valid=False
        if not valid: raise SajuProfileError("출생시간을 확인하세요")
    if not profile.get("birth_place"): raise SajuProfileError("출생지를 입력하세요")


def has_complete_saju_profile(profile):
    try: validate_saju_profile(profile or {}); return True
    except (ValueError,TypeError,KeyError): return False
