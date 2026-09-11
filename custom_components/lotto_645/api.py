"""Conservative HTTP access for shared mirror and optional official fallback."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import (
    HISTORY_URL,
    MAIN_INFO_URL,
    MIRROR_URL,
    OFFICIAL_CIRCUIT_BREAKER_SECONDS,
    OFFICIAL_DIRECT_MAX_MISSING_ROUNDS,
    OFFICIAL_MAX_REQUESTS_PER_UPDATE,
    OFFICIAL_MIN_INTERVAL_SECONDS,
    OFFICIAL_RESULT_URL,
    SINGLE_DRAW_URL,
)
from .history import LottoHistoryError, parse_history_payload
from .models import LottoDraw


class LottoApiError(Exception):
    """Base data-source error."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LottoApiClient:
    """Read the shared mirror and, only when allowed, tiny official deltas."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "HomeAssistant-HA-Lotto-645/1.3 (+shared-mirror)",
        }
        self._official_headers = {
            **self._headers,
            "Referer": OFFICIAL_RESULT_URL,
        }
        self._official_lock = asyncio.Lock()
        self._official_requests = 0
        self._last_official_request_at = 0.0
        self._official_blocked_until = 0.0
        self._mirror_etag: str | None = None

    def begin_update_cycle(self) -> None:
        """Reset only the per-update official request budget."""
        self._official_requests = 0

    async def async_fetch_shared_mirror(
        self,
    ) -> tuple[list[LottoDraw] | None, dict[str, Any]]:
        """Fetch the repository mirror once, supporting conditional ETag requests."""
        headers = dict(self._headers)
        if self._mirror_etag:
            headers["If-None-Match"] = self._mirror_etag
        try:
            async with asyncio.timeout(20):
                async with self._session.get(MIRROR_URL, headers=headers) as response:
                    if response.status == 304:
                        return None, {"not_modified": True, "etag": self._mirror_etag}
                    if response.status >= 400:
                        raise LottoApiError(
                            f"공유 로또 이력 미러 응답 오류: HTTP {response.status}"
                        )
                    payload = await response.json(content_type=None)
                    etag = response.headers.get("ETag")
        except TimeoutError as err:
            raise LottoApiError("공유 로또 이력 미러 요청 시간이 초과되었습니다") from err
        except ClientError as err:
            raise LottoApiError(f"공유 로또 이력 미러 통신 실패: {err}") from err
        except ValueError as err:
            raise LottoApiError("공유 로또 이력 미러 JSON을 해석할 수 없습니다") from err

        try:
            draws, metadata = parse_history_payload(payload, require_hash=True)
        except LottoHistoryError as err:
            raise LottoApiError(str(err)) from err
        self._mirror_etag = etag
        metadata["etag"] = etag
        metadata["not_modified"] = False
        return draws, metadata

    async def _raise_for_official_status(self, response: ClientResponse) -> None:
        if response.status in (403, 429):
            retry_raw = response.headers.get("Retry-After")
            retry_after = float(OFFICIAL_CIRCUIT_BREAKER_SECONDS)
            if retry_raw:
                try:
                    retry_after = max(300.0, min(float(retry_raw), retry_after))
                except ValueError:
                    pass
            self._official_blocked_until = time.monotonic() + retry_after
            raise LottoApiError(
                f"동행복권이 HTTP {response.status}로 접근을 제한했습니다. 직접 요청을 중단합니다",
                retry_after,
            )
        if response.status >= 400:
            raise LottoApiError(f"동행복권 응답 오류: HTTP {response.status}")

    async def _official_get_json(
        self, url: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Make one sequential official request under a hard safety budget."""
        now = time.monotonic()
        if now < self._official_blocked_until:
            raise LottoApiError(
                "동행복권 직접 요청 회로 차단기가 활성화되어 있습니다",
                self._official_blocked_until - now,
            )
        if self._official_requests >= OFFICIAL_MAX_REQUESTS_PER_UPDATE:
            raise LottoApiError("동행복권 직접 요청 안전 한도에 도달했습니다")

        async with self._official_lock:
            elapsed = time.monotonic() - self._last_official_request_at
            wait = OFFICIAL_MIN_INTERVAL_SECONDS - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._official_requests += 1
            try:
                async with asyncio.timeout(15):
                    async with self._session.get(
                        url,
                        params=params,
                        headers=self._official_headers,
                    ) as response:
                        await self._raise_for_official_status(response)
                        return await response.json(content_type=None)
            except TimeoutError as err:
                raise LottoApiError("동행복권 직접 요청 시간이 초과되었습니다") from err
            except ClientError as err:
                raise LottoApiError(f"동행복권 직접 통신 실패: {err}") from err
            except ValueError as err:
                raise LottoApiError("동행복권 응답을 JSON으로 해석할 수 없습니다") from err
            finally:
                self._last_official_request_at = time.monotonic()

    async def async_latest_round_official(self) -> int:
        """Read the official latest round with one request."""
        payload = await self._official_get_json(MAIN_INFO_URL)
        try:
            rows = payload["data"]["result"]["pstLtEpstInfo"]["lt645"]
            rounds = [int(item["ltEpsd"]) for item in rows]
        except (KeyError, TypeError, ValueError) as err:
            raise LottoApiError("최신 회차 응답 형식이 예상과 다릅니다") from err
        if not rounds:
            raise LottoApiError("최신 회차 정보가 비어 있습니다")
        return max(rounds)

    @staticmethod
    def _parse_draw(item: dict[str, Any]) -> LottoDraw:
        try:
            round_no = int(item["ltEpsd"])
            numbers = tuple(sorted(int(item[f"tm{i}WnNo"]) for i in range(1, 7)))
            bonus = int(item["bnsWnNo"])
            draw = LottoDraw(
                round=round_no,
                draw_date=str(item.get("ltRflYmd", "")),
                numbers=numbers,  # type: ignore[arg-type]
                bonus=bonus,
                first_prize_winners=(
                    int(item["rnk1WnNope"])
                    if item.get("rnk1WnNope") is not None
                    else None
                ),
                first_prize_amount=(
                    int(item["rnk1WnAmt"])
                    if item.get("rnk1WnAmt") is not None
                    else None
                ),
            )
            # Re-use strict storage validation, including bonus not overlapping mains.
            return LottoDraw.from_storage(draw.to_storage())
        except (KeyError, TypeError, ValueError) as err:
            raise LottoApiError("회차 당첨 결과 응답 형식이 예상과 다릅니다") from err

    def _parse_list(self, payload: Any) -> list[LottoDraw]:
        try:
            items = payload["data"]["list"]
        except (KeyError, TypeError) as err:
            raise LottoApiError("회차 목록 응답 형식이 예상과 다릅니다") from err
        if not isinstance(items, list):
            raise LottoApiError("회차 목록이 리스트 형식이 아닙니다")
        return sorted(
            {draw.round: draw for draw in (self._parse_draw(x) for x in items if isinstance(x, dict))}.values(),
            key=lambda draw: draw.round,
        )

    async def async_fetch_center_official(self, round_no: int) -> list[LottoDraw]:
        payload = await self._official_get_json(
            HISTORY_URL,
            {"srchDir": "center", "srchLtEpsd": int(round_no)},
        )
        return self._parse_list(payload)

    async def async_fetch_single_official(self, round_no: int) -> LottoDraw | None:
        payload = await self._official_get_json(
            SINGLE_DRAW_URL, {"srchLtEpsd": int(round_no)}
        )
        return next(
            (draw for draw in self._parse_list(payload) if draw.round == round_no),
            None,
        )

    async def async_fetch_recent_range_official(
        self, start_round: int, end_round: int
    ) -> list[LottoDraw]:
        """Fetch only a tiny recent gap; never use this for historical crawling."""
        if start_round > end_round:
            return []
        gap = end_round - start_round + 1
        if gap > OFFICIAL_DIRECT_MAX_MISSING_ROUNDS:
            raise LottoApiError(
                f"직접 증분 수집 허용 범위({OFFICIAL_DIRECT_MAX_MISSING_ROUNDS}회)를 초과했습니다"
            )
        wanted = set(range(start_round, end_round + 1))
        by_round: dict[int, LottoDraw] = {}
        for draw in await self.async_fetch_center_official(end_round):
            if draw.round in wanted:
                by_round[draw.round] = draw
        for round_no in sorted(wanted - set(by_round)):
            draw = await self.async_fetch_single_official(round_no)
            if draw is not None:
                by_round[round_no] = draw
        missing = sorted(wanted - set(by_round))
        if missing:
            raise LottoApiError(
                "직접 증분 데이터에 누락이 있습니다: "
                + ", ".join(map(str, missing))
            )
        return [by_round[index] for index in range(start_round, end_round + 1)]
