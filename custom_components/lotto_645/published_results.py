"""Public publisher results, kept separate from the official historical seed.

A complete, round-bound publisher report can be shown as provisional; conflicts
hold evaluation. 'Cross checked' counts publishers, not claims of independence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from .models import LottoDraw

KST = ZoneInfo("Asia/Seoul")
FIRST_DRAW = date(2002, 12, 7)
FEEDS = (
    ("sbs", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02&plink=RSSREADER"),
    ("yonhap", "https://www.yna.co.kr/rss/economy.xml"),
    ("newsis", "https://www.newsis.com/RSS/sokbo.xml"),
)
ALLOWED_ARTICLES = {"sbs": ("news.sbs.co.kr", "/news/endPage.do"),
                    "yonhap": ("www.yna.co.kr", "/view/"),
                    "newsis": ("www.newsis.com", "/view/")}
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
SEP = r"\s*[,·ㆍ，﹐]\s*"
SIX = r"(?<![0-9])([0-9]{1,2}(?:" + SEP + r"[0-9]{1,2}){5})(?!\s*[,·ㆍ，﹐]\s*[0-9]|[0-9])"
BONUS = re.compile(r"보너스\s*(?:당첨\s*)?(?:번호\s*)?(?:는|은|가|이|:|：|=)?\s*[\"'‘’“”\[\(]*\s*([0-9]{1,2})(?![0-9])")
ROUND = re.compile(r"(?<![0-9])(?:제\s*)?([0-9]{1,5})\s*회(?:차)?")


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignore = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "noscript"):
            self.ignore += 1
        if tag in ("p", "br", "div", "li"):
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self.ignore = max(0, self.ignore - 1)
        self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.ignore:
            self.parts.append(data)


def plain_text(html: str) -> str:
    parser = _Text()
    parser.feed(html[:2_000_000])
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def draw_date(round_no: int) -> date:
    if type(round_no) is not int or not 1 <= round_no <= 10000:
        raise ValueError("Invalid draw round")
    return FIRST_DRAW + timedelta(weeks=round_no - 1)


def draw_cutoff(round_no: int) -> datetime:
    # Scheduled drawing START, not a claim of a measured live broadcast end.
    return datetime.combine(draw_date(round_no), time(20, 35), KST)


def current_draw_round(now: datetime) -> int:
    if now.tzinfo is None:
        raise ValueError("Aware timestamp required")
    local = now.astimezone(KST)
    n = (local.date() - FIRST_DRAW).days // 7 + 1
    if local < draw_cutoff(max(1, n)):
        n -= 1
    return max(0, n)


def poll_interval(now: datetime) -> int | None:
    """Fast only around publication; no continuous 24/7 portal crawling."""
    local = now.astimezone(KST)
    minute = local.hour * 60 + local.minute
    if local.weekday() == 5 and 20 * 60 + 35 <= minute <= 21 * 60 + 30:
        return 60
    if local.weekday() == 5 and 21 * 60 + 30 < minute <= 23 * 60 + 30:
        return 300
    if local.weekday() == 6 and minute <= 10 * 60:
        return 900
    return None


def article_allowed(publisher: str, url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host, prefix = ALLOWED_ARTICLES[publisher]
        return (parsed.scheme == "https" and parsed.hostname == host and not parsed.username
                and not parsed.password and parsed.port in (None, 443)
                and parsed.path.startswith(prefix) and len(url) <= 1500)
    except (KeyError, ValueError):
        return False


@dataclass(frozen=True)
class PublishedDraw:
    draw: LottoDraw
    publisher: str
    url: str
    published_at: str

    def as_dict(self) -> dict:
        return {"draw": self.draw.to_storage(), "publisher": self.publisher,
                "url": self.url, "published_at": self.published_at}

    @classmethod
    def from_dict(cls, data: dict) -> "PublishedDraw":
        draw = LottoDraw.from_storage(data["draw"])
        if draw.draw_date != draw_date(draw.round).isoformat() or not article_allowed(data["publisher"], data["url"]):
            raise ValueError("Invalid saved publisher evidence")
        parsedate = datetime.fromisoformat(data["published_at"])
        if parsedate.tzinfo is None or parsedate < draw_cutoff(draw.round):
            raise ValueError("Invalid publication time")
        return cls(draw, data["publisher"], data["url"], data["published_at"])


def parse_report(title: str, content: str, publisher: str, url: str,
                 published_at: datetime, target_round: int, now: datetime) -> PublishedDraw | None:
    """Require same round, actual result language, six mains AND a distinct bonus."""
    if published_at.tzinfo is None or now.tzinfo is None or not article_allowed(publisher, url):
        return None
    if not draw_cutoff(target_round) <= published_at <= now + timedelta(minutes=5):
        return None
    if published_at > draw_cutoff(target_round) + timedelta(days=3) or now < draw_cutoff(target_round):
        return None
    head = plain_text(title)
    if ("로또" not in head or not re.search(r"당첨|보너스|1등", head)
            or re.search(r"예상|추천|예측|명당|조작", head)):
        return None
    if {int(m) for m in ROUND.findall(head)} != {target_round}:
        return None
    text = head + " " + plain_text(content)
    combos = set()
    for match in re.finditer(SIX, text):
        if re.search(r"[0-9]\s*[,·ㆍ，﹐]\s*$", text[:match.start()]):
            continue  # not a six-number tail cut from a seven-number list
        values = tuple(sorted(map(int, re.findall(r"[0-9]+", match.group(1)))))
        if len(set(values)) == 6 and all(1 <= n <= 45 for n in values):
            combos.add(values)
    bonuses = {int(m) for m in BONUS.findall(text)}
    if len(combos) != 1 or len(bonuses) != 1:
        return None
    values, bonus = next(iter(combos)), next(iter(bonuses))
    if not 1 <= bonus <= 45 or bonus in values:
        return None
    # Reject text that prominently mixes multiple draw results.
    rounds = {int(m) for m in ROUND.findall(text)}
    if rounds != {target_round}:
        return None
    return PublishedDraw(LottoDraw(target_round, draw_date(target_round).isoformat(), values, bonus),
                         publisher, url, published_at.isoformat())


def rss_items(raw: bytes, publisher: str, target_round: int, now: datetime) -> list[dict]:
    """Extract only bounded relevant RSS items. Never persist article body."""
    if len(raw) > 2_000_000 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsafe or oversized RSS")
    root = ET.fromstring(raw)
    result = []
    for item in root.findall(".//item")[:250]:
        title = item.findtext("title", "")
        if "로또" not in title or target_round not in [int(m) for m in ROUND.findall(title)]:
            continue
        url = item.findtext("link", "").strip()
        if not article_allowed(publisher, url):
            continue
        try:
            when = parsedate_to_datetime(item.findtext("pubDate", ""))
        except (ValueError, TypeError, OverflowError):
            continue
        if when.tzinfo is None or when > now + timedelta(minutes=5) or when < draw_cutoff(target_round):
            continue
        content = item.findtext("description", "") + " " + item.findtext(CONTENT_NS, "")
        result.append({"title": title, "content": content, "url": url, "published_at": when})
    return result


def select_result(candidates: list[PublishedDraw]) -> dict[str, Any]:
    """Disagreement is a visible waiting state, never an arbitrary winning result."""
    if not candidates:
        return {"status": "waiting", "sources": [], "draw": None}
    signatures = {(c.draw.round, c.draw.numbers, c.draw.bonus) for c in candidates}
    sources = [{"publisher": c.publisher, "url": c.url, "published_at": c.published_at} for c in candidates]
    if len(signatures) != 1:
        return {"status": "conflict", "sources": sources, "draw": None,
                "round": max(c.draw.round for c in candidates)}
    groups = {c.publisher for c in candidates}
    return {"status": "cross_checked" if len(groups) >= 2 else "provisional",
            "sources": sources, "draw": candidates[0].draw.to_storage(),
            "round": candidates[0].draw.round,
            "notice": "언론 공개 속보 기준 · 동행복권 공식 이력과 아직 대조하지 않음. 재전송 기사는 독립 취재를 의미하지 않습니다."}
