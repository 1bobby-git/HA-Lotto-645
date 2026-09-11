"""HTTP client for Donghaeng Lottery public result surfaces."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import HISTORY_URL, MAIN_INFO_URL, SINGLE_DRAW_URL
from .models import LottoDraw


class LottoApiError(Exception):
    """Base API error."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LottoApiClient:
    """Small async client for Lotto 6/45 result data."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "HomeAssistant-HA-Lotto-645/1.0",
            "Referer": "https://www.dhlottery.co.kr/lt645/result",
        }

    async def _raise_for_status(self, response: ClientResponse) -> None:
        if response.status == 429:
            retry_raw = response.headers.get("Retry-After")
            retry_after = 300.0
            if retry_raw:
                try:
                    retry_after = max(60.0, min(float(retry_raw), 3600.0))
                except ValueError:
                    pass
            raise LottoApiError("동행복권 서버 요청 제한에 도달했습니다", retry_after)
        if response.status >= 400:
            raise LottoApiError(f"동행복권 응답 오류: HTTP {response.status}")

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            async with asyncio.timeout(15):
                async with self._session.get(
                    url, params=params, headers=self._headers
                ) as response:
                    await self._raise_for_status(response)
                    return await response.json(content_type=None)
        except TimeoutError as err:
            raise LottoApiError("동행복권 요청 시간이 초과되었습니다") from err
        except ClientError as err:
            raise LottoApiError(f"동행복권 통신 실패: {err}") from err
        except ValueError as err:
            raise LottoApiError("동행복권 응답을 JSON으로 해석할 수 없습니다") from err

    async def async_latest_round(self) -> int:
        """Fetch the latest announced Lotto round."""
        payload = await self._get_json(MAIN_INFO_URL)
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
            numbers = tuple(int(item[f"tm{i}WnNo"]) for i in range(1, 7))
            bonus = int(item["bnsWnNo"])
        except (KeyError, TypeError, ValueError) as err:
            raise LottoApiError("회차 당첨 결과 응답 형식이 예상과 다릅니다") from err

        if len(numbers) != 6 or len(set(numbers)) != 6:
            raise LottoApiError(f"{round_no}회 당첨번호 6개가 유효하지 않습니다")
        if any(number < 1 or number > 45 for number in numbers):
            raise LottoApiError(f"{round_no}회 당첨번호 범위가 유효하지 않습니다")
        if bonus < 1 or bonus > 45:
            raise LottoApiError(f"{round_no}회 보너스 번호가 유효하지 않습니다")

        raw_date = str(item.get("ltRflYmd", ""))
        draw_date = raw_date
        if len(raw_date) == 8 and raw_date.isdigit():
            draw_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"

        return LottoDraw(
            round=round_no,
            draw_date=draw_date,
            numbers=tuple(sorted(numbers)),  # type: ignore[arg-type]
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

    def _parse_list(self, payload: Any) -> list[LottoDraw]:
        try:
            items = payload["data"]["list"]
        except (KeyError, TypeError) as err:
            raise LottoApiError("회차 목록 응답 형식이 예상과 다릅니다") from err
        if not isinstance(items, list):
            raise LottoApiError("회차 목록이 리스트 형식이 아닙니다")
        draws = [self._parse_draw(item) for item in items if isinstance(item, dict)]
        return sorted({draw.round: draw for draw in draws}.values(), key=lambda d: d.round)

    async def async_fetch_center(self, round_no: int) -> list[LottoDraw]:
        """Fetch a window centered around a round."""
        payload = await self._get_json(
            HISTORY_URL,
            {"srchDir": "center", "srchLtEpsd": int(round_no)},
        )
        return self._parse_list(payload)

    async def async_fetch_older(self, cursor_round: int) -> list[LottoDraw]:
        """Fetch a window older than the supplied cursor."""
        payload = await self._get_json(
            HISTORY_URL,
            {"srchDir": "older", "srchCursorLtEpsd": int(cursor_round)},
        )
        return self._parse_list(payload)

    async def async_fetch_single(self, round_no: int) -> LottoDraw | None:
        """Fetch one round using the single-round endpoint."""
        payload = await self._get_json(SINGLE_DRAW_URL, {"srchLtEpsd": int(round_no)})
        draws = self._parse_list(payload)
        for draw in draws:
            if draw.round == round_no:
                return draw
        return None

    async def async_fetch_full_history(self, latest_round: int) -> list[LottoDraw]:
        """Fetch draw 1 through latest_round using paged windows."""
        if latest_round < 1:
            raise LottoApiError("최신 회차 번호가 유효하지 않습니다")

        by_round: dict[int, LottoDraw] = {}
        page = await self.async_fetch_center(latest_round)
        for draw in page:
            if 1 <= draw.round <= latest_round:
                by_round[draw.round] = draw
        if not by_round:
            raise LottoApiError("최신 회차 주변 데이터를 가져오지 못했습니다")

        safety = 0
        while min(by_round) > 1:
            safety += 1
            if safety > 160:
                raise LottoApiError("전체 회차 수집 안전 한도를 초과했습니다")
            cursor = min(by_round)
            page = await self.async_fetch_older(cursor)
            new_count = 0
            for draw in page:
                if 1 <= draw.round <= latest_round and draw.round not in by_round:
                    by_round[draw.round] = draw
                    new_count += 1
            if new_count == 0:
                break
            await asyncio.sleep(0.08)

        await self._fill_missing(by_round, range(1, latest_round + 1))
        missing = sorted(set(range(1, latest_round + 1)) - set(by_round))
        if missing:
            preview = ", ".join(str(value) for value in missing[:8])
            raise LottoApiError(f"전체 회차 데이터에 누락이 있습니다: {preview}")
        return [by_round[index] for index in range(1, latest_round + 1)]

    async def async_fetch_range(self, start_round: int, end_round: int) -> list[LottoDraw]:
        """Fetch a contiguous inclusive round range."""
        if start_round > end_round:
            return []
        wanted = set(range(start_round, end_round + 1))
        by_round: dict[int, LottoDraw] = {}
        pointer = end_round
        safety = 0

        while wanted - set(by_round):
            safety += 1
            if safety > 80:
                break
            page = await self.async_fetch_center(pointer)
            if not page:
                break
            for draw in page:
                if draw.round in wanted:
                    by_round[draw.round] = draw
            unseen = sorted(wanted - set(by_round))
            if not unseen:
                break
            lower = [value for value in unseen if value < pointer]
            if not lower:
                break
            pointer = max(lower)
            await asyncio.sleep(0.05)

        await self._fill_missing(by_round, wanted)
        missing = sorted(wanted - set(by_round))
        if missing:
            preview = ", ".join(str(value) for value in missing[:8])
            raise LottoApiError(f"증분 회차 데이터에 누락이 있습니다: {preview}")
        return [by_round[index] for index in range(start_round, end_round + 1)]

    async def _fill_missing(
        self, by_round: dict[int, LottoDraw], expected_rounds: Iterable[int]
    ) -> None:
        missing = sorted(set(expected_rounds) - set(by_round))
        for round_no in missing[:20]:
            draw = await self.async_fetch_single(round_no)
            if draw is not None:
                by_round[round_no] = draw
            await asyncio.sleep(0.04)
