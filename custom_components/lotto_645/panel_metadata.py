"""Read-only panel metadata; no I/O, recommendation generation or polling."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .const import AI_METHOD_ID
from .methods import method_catalog, RETIRED_METHOD_LABELS

KST = ZoneInfo("Asia/Seoul")
FIRST_DRAW_DATE = date(2002, 12, 7)
REGULAR_DRAW_TIME = time(20, 35)
NEXT_ROUND_SALES_TIME = time(6, 0)
SCHEDULE_SOURCE = "https://www.dhlottery.co.kr/lt645/intro"
SCHEDULE_VERIFIED_ON = "2026-09-14"


def draw_schedule(result_round: int | None = None, result_status: str = "waiting", *, now: datetime | None = None) -> dict:
    """Calculate the regular draw countdown and next-round sales boundary.

    Donghaeng Lottery currently publishes the regular draw at about Saturday
    20:35 and internet sales are available Sunday-Friday 06:00-24:00, with
    Saturday sales ending at 20:00.  After the Saturday draw deadline the
    countdown intentionally stays at zero until Sunday 06:00; only then does it
    roll to the next round.  ``result_round`` and ``result_status`` are accepted
    for API compatibility but never make the display skip that sales boundary.
    """
    del result_round, result_status
    current = now or datetime.now(KST)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(KST)

    # Sunday before internet sales reopen still belongs to Saturday's completed
    # sales cycle.  From Sunday 06:00 onward the next Saturday is the active
    # purchasable round and a fresh countdown may begin.
    if current.weekday() == 6 and current.time() < NEXT_ROUND_SALES_TIME:
        day = current.date() - timedelta(days=1)
    else:
        day = current.date() + timedelta(days=(5 - current.weekday()) % 7)

    round_no = (day - FIRST_DRAW_DATE).days // 7 + 1
    if round_no < 1:
        raise ValueError("date precedes the first Lotto draw")

    scheduled = datetime.combine(day, REGULAR_DRAW_TIME, KST)
    sales_reopen = datetime.combine(day + timedelta(days=1), NEXT_ROUND_SALES_TIME, KST)
    return {
        "round": round_no,
        "scheduled_at": scheduled.isoformat(),
        "sales_reopen_at": sales_reopen.isoformat(),
        # Kept for the browser countdown API: rollover now means the exact point
        # at which the following round becomes purchasable online.
        "rollover_at": sales_reopen.isoformat(),
        "server_now": current.isoformat(),
        "timezone": "Asia/Seoul",
        "basis": "regular_schedule",
        "source_url": SCHEDULE_SOURCE,
        "source_verified_on": SCHEDULE_VERIFIED_ON,
        "notice": (
            "정규 추첨·인터넷 판매시간 기준 · 토요일 20:35경부터 카운트를 0으로 유지하고 "
            "일요일 06:00 다음 회차 판매 시작부터 새 카운트를 시작합니다. 방송 편성 및 판매점 운영시간은 달라질 수 있습니다."
        ),
    }


def panel_metadata(result_round: int | None, result_status: str) -> dict:
    """Share only public method descriptions, never personal/AI profile data."""
    catalog = method_catalog()
    catalog.append({
        "method_id": AI_METHOD_ID,
        "name": "Home Assistant AI 추천",
        "category": "Home Assistant AI",
        "description": "번호는 백엔드 CCSS 공식으로 추첨하고 Home Assistant AI는 실행 근거만 설명합니다. AI가 번호를 만들거나 당첨을 예측하지 않습니다.",
        "requirements": "AI 추천 활성화 및 데이터 생성 AI 설정",
    })
    return {"archived_method_catalog": [{"method_id": key, "name": label + " · 종료된 공식"} for key, label in RETIRED_METHOD_LABELS.items()], "method_catalog": catalog, "draw_schedule": draw_schedule(result_round, result_status)}
