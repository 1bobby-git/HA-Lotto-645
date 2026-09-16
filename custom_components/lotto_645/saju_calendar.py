"""Public date/time input normalization; no calendar calculation."""
import re

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


def date_parts(value):
    value=normalize_birth_date(value)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",value):raise SajuProfileError("invalid_birth_date")
    year,month,day=map(int,value.split("-"))
    if not 1900<=year<=2050 or not 1<=month<=12 or not 1<=day<=31:raise SajuProfileError("invalid_birth_date")
    return year,month,day

def birth_clock(value):
    value=normalize_birth_time(value)
    if value in ("미상","unknown",""):return None
    if not re.fullmatch(r"[0-9]{2}:[0-9]{2}",value):raise SajuProfileError("invalid_birth_time")
    hour,minute=map(int,value.split(":"))
    if not 0<=hour<=23 or not 0<=minute<=59:raise SajuProfileError("invalid_birth_time")
    return hour,minute
