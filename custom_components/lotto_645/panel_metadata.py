"""Read-only panel metadata; no I/O, recommendation generation or polling."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .const import AI_METHOD_ID
from .methods import method_catalog

KST = ZoneInfo("Asia/Seoul")
FIRST_DRAW_DATE = date(2002, 12, 7)
REGULAR_DRAW_TIME = time(20, 35)
SCHEDULE_SOURCE = "https://www.dhlottery.co.kr/guide/wnrGuide"
SCHEDULE_VERIFIED_ON = "2026-09-14"
PUBLISHED_STATES = frozenset({"official_history", "official_confirmed", "official_corrected", "provisional", "cross_checked"})


def draw_schedule(result_round: int | None = None, result_status: str = "waiting", *, now: datetime | None = None) -> dict:
    """Calculate the upcoming regular draw, NOT a live broadcast confirmation.

    Keep Saturday's elapsed deadline until a published result arrives or Sunday
    begins. Missing historical results must not pin the clock to an old round.
    All returned instants have an explicit Korean UTC offset.
    """
    current = now or datetime.now(KST)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(KST)
    day = current.date() + timedelta(days=(5 - current.weekday()) % 7)
    round_no = (day - FIRST_DRAW_DATE).days // 7 + 1
    if round_no < 1:
        raise ValueError("date precedes the first Lotto draw")
    # A published result settles this Saturday; advance the countdown only,
    # never recommendations or the currently displayed result/wallet round.
    if current.weekday() == 5 and result_status in PUBLISHED_STATES and type(result_round) is int and result_round >= round_no:
        day += timedelta(days=7)
        round_no += 1
    scheduled = datetime.combine(day, REGULAR_DRAW_TIME, KST)
    rollover = datetime.combine(day + timedelta(days=1), time.min, KST)
    return {
        "round": round_no,
        "scheduled_at": scheduled.isoformat(),
        "rollover_at": rollover.isoformat(),
        "server_now": current.isoformat(),
        "timezone": "Asia/Seoul",
        "basis": "regular_schedule",
        "source_url": SCHEDULE_SOURCE,
        "source_verified_on": SCHEDULE_VERIFIED_ON,
        "notice": "정규 일정 기준 · 회차별 방송 편성 변경은 자동 확인하지 않습니다.",
    }


def panel_metadata(result_round: int | None, result_status: str) -> dict:
    """Share only public method descriptions, never personal/AI profile data."""
    catalog = method_catalog()
    catalog.append({
        "method_id": AI_METHOD_ID,
        "name": "Home Assistant AI 추천",
        "category": "Home Assistant AI",
        "description": "Home Assistant에 설정된 AI가 추천한 번호를 형식·제외 규칙으로 검증합니다.",
        "requirements": "AI 추천 활성화 및 데이터 생성 AI 설정",
    })
    return {"method_catalog": catalog, "draw_schedule": draw_schedule(result_round, result_status)}
