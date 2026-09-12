"""Bounded publisher RSS reader with robots, ETags and source circuit breakers."""
from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

from aiohttp import ClientError, ClientSession

from .published_results import FEEDS, PublishedDraw, parse_report, rss_items, select_result

UA = "HA-Lotto-645/1.10 (+https://github.com/1bobby-git/HA-Lotto-645)"


class FastResultClient:
    """Only allowlisted public URLs, no CAPTCHA bypass, private IP or user URL fetch."""

    def __init__(self, session: ClientSession) -> None:
        self.session = session
        self._robots: dict[str, tuple[float, RobotFileParser]] = {}
        self._blocked: dict[str, float] = {}
        self._etag: dict[str, str] = {}
        self._content: dict[str, bytes] = {}
        self._last_at = 0.0
        self._last_host_read: dict[str, float] = {}
        self._crawl_delay: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self.status: dict = {}
        self.target = 0
        self.evidence: dict[str, PublishedDraw] = {}

    async def _read(self, url: str, *, limit: int, robots: bool = False) -> bytes | None:
        host = urlsplit(url).netloc
        now = time.monotonic()
        if self._blocked.get(host, 0) > now:
            return None
        if not robots and now - self._last_host_read.get(host, 0) < self._crawl_delay.get(host, 0):
            return None
        headers = {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/html;q=0.8"}
        if not robots and url in self._etag:
            headers["If-None-Match"] = self._etag[url]
        async with asyncio.timeout(8):
            async with self.session.get(url, headers=headers, allow_redirects=False) as response:
                self._last_host_read[host] = time.monotonic()
                if response.status in (403, 429):
                    delay = 1800.0
                    raw = response.headers.get("Retry-After", "")
                    try:
                        delay = max(delay, float(raw))
                    except ValueError:
                        try:
                            delay = max(delay, (parsedate_to_datetime(raw) - datetime.now(UTC)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            pass
                    self._blocked[host] = now + (max(delay, 1800) if math.isfinite(delay) else 86400)
                    raise ValueError(f"HTTP {response.status}; source paused")
                if robots and response.status == 404:
                    return b"User-agent: *\nAllow: /\n"
                if response.status == 304:
                    return self._content.get(url)
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                parts = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    parts.extend(chunk)
                    if len(parts) > limit:
                        raise ValueError("Source response exceeds size limit")
                data = bytes(parts)
                if not robots:
                    if etag := response.headers.get("ETag"):
                        self._etag[url] = etag
                    self._content[url] = data
                    # Three feeds plus at most two relevant articles per update.
                    if len(self._content) > 12:
                        for key in list(self._content)[:-10]:
                            self._content.pop(key, None)
                            self._etag.pop(key, None)
                return data

    async def _allowed(self, url: str) -> bool:
        host = urlsplit(url).netloc
        cached = self._robots.get(host)
        if cached is None or time.monotonic() - cached[0] >= 86400:
            data = await self._read(f"https://{host}/robots.txt", limit=256000, robots=True)
            if data is None:
                return False
            rule = RobotFileParser()
            rule.parse(data.decode("utf-8", "replace").splitlines())
            self._robots[host] = (time.monotonic(), rule)
        rule = self._robots[host][1]
        self._crawl_delay[host] = float(rule.crawl_delay(UA) or 0)
        return rule.can_fetch(UA, url)

    async def check(self, target_round: int, *, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        async with self._lock:
            if time.monotonic() - self._last_at < 55 and self.target == target_round:
                return select_result(list(self.evidence.values()))
            self._last_at = time.monotonic()
            if self.target != target_round:
                self.target = target_round
                self.evidence.clear()
            # Parallel distinct publishers; no repeated concurrent hits to a host.
            async def source(publisher: str, url: str) -> None:
                try:
                    if not await self._allowed(url):
                        self.status[publisher] = "자동 접근 제한: 요청하지 않음"
                        return
                    raw = await self._read(url, limit=2_000_000)
                    if raw is None:
                        self.status[publisher] = "재시도 대기"
                        return
                    candidates = rss_items(raw, publisher, target_round, now)
                    accepted = []
                    article_requests = 0
                    for item in candidates[:3]:
                        evidence = parse_report(item['title'], item['content'], publisher,
                                                item['url'], item['published_at'], target_round, now)
                        if evidence is None and not accepted and article_requests < 1 and await self._allowed(item['url']):
                            article_requests += 1
                            article = await self._read(item['url'], limit=1_500_000)
                            if article:
                                evidence = parse_report(item['title'], article.decode('utf-8', 'replace'),
                                                        publisher, item['url'], item['published_at'], target_round, now)
                        if evidence:
                            accepted.append(evidence)
                    for evidence in accepted:
                        # Same publisher can correct an earlier publication. Newer
                        # complete reports replace its evidence rather than accumulating.
                        old = self.evidence.get(publisher)
                        if old is None or datetime.fromisoformat(evidence.published_at) >= datetime.fromisoformat(old.published_at):
                            self.evidence[publisher] = evidence
                    self.status[publisher] = "해당 회차 완전한 결과 수신" if accepted else "해당 회차 본번호·보너스 발표 대기"
                except (TimeoutError, ClientError, ValueError, ET.ParseError, UnicodeError):
                    self.status[publisher] = "응답 오류/형식 변경: 다음 허용 시각 재확인"
            await asyncio.gather(*(source(publisher, url) for publisher, url in FEEDS))
            result = select_result(list(self.evidence.values()))
            result["checked_at"] = now.isoformat()
            result["providers"] = dict(self.status)
            return result
