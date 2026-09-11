#!/usr/bin/env python3
"""Build and incrementally update the HA-Lotto-645 shared history mirror.

The Home Assistant integration should not make every installation crawl the
Donghaeng Lottery website.  This script centralizes that work in one GitHub
Actions job and deliberately keeps official traffic very small:

* normal week with no new draw: one official request;
* new draw: normally two official requests;
* bootstrap: use a pinned public historical SQLite snapshot, verify its tail
  against Donghaeng Lottery, then request only the missing recent window.

There is no proxy rotation, CAPTCHA bypass, IP evasion, concurrency, or rapid
retry.  HTTP 403/429 stops the job immediately so the previous mirror remains
available.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MIRROR_PATH = ROOT / "data" / "lotto645-history.json"

MAIN_INFO_URL = "https://www.dhlottery.co.kr/selectMainInfo.do"
HISTORY_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
SINGLE_DRAW_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do"

# Bootstrap-only factual history seed.  It is pinned so an upstream change
# cannot silently alter our historical base.  Recent rows are cross-checked
# against Donghaeng Lottery before the mirror is accepted.
SEED_COMMIT = "78e55c13463b41567e11d8e7217d0b175d577443"
SEED_DB_URL = (
    "https://raw.githubusercontent.com/happylie/lotto_data/"
    f"{SEED_COMMIT}/lotto_data.db"
)

MIN_OFFICIAL_INTERVAL_SECONDS = 2.5
MAX_OFFICIAL_REQUESTS = 12
TIMEOUT_SECONDS = 20
USER_AGENT = (
    "HA-Lotto-645-Mirror/1.0 "
    "(+https://github.com/1bobby-git/HA-Lotto-645; weekly shared cache)"
)


class MirrorUpdateError(RuntimeError):
    """Mirror update failed without invalidating the previous mirror."""


@dataclass(frozen=True, slots=True)
class Draw:
    round: int
    draw_date: str
    numbers: tuple[int, int, int, int, int, int]
    bonus: int
    first_prize_winners: int | None = None
    first_prize_amount: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "round": self.round,
            "draw_date": self.draw_date,
            "numbers": list(self.numbers),
            "bonus": self.bonus,
            "first_prize_winners": self.first_prize_winners,
            "first_prize_amount": self.first_prize_amount,
        }


class OfficialClient:
    """Strictly rate-limited, sequential Donghaeng Lottery reader."""

    def __init__(self) -> None:
        self.requests = 0
        self._last_request_at = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = MIN_OFFICIAL_INTERVAL_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if self.requests >= MAX_OFFICIAL_REQUESTS:
            raise MirrorUpdateError(
                f"official request safety limit reached ({MAX_OFFICIAL_REQUESTS})"
            )
        self._wait()
        target = url
        if params:
            target = f"{url}?{urlencode(params)}"
        request = Request(
            target,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": USER_AGENT,
                "Referer": "https://www.dhlottery.co.kr/lt645/result",
            },
        )
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read()
        except HTTPError as err:
            # Do not hammer or attempt to bypass access controls.
            if err.code in (403, 429):
                raise MirrorUpdateError(
                    f"Donghaeng Lottery returned HTTP {err.code}; stop without retry"
                ) from err
            raise MirrorUpdateError(
                f"Donghaeng Lottery returned HTTP {err.code}"
            ) from err
        except (URLError, TimeoutError) as err:
            raise MirrorUpdateError(f"official request failed: {err}") from err
        finally:
            self.requests += 1
            self._last_request_at = time.monotonic()

        if status >= 400:
            raise MirrorUpdateError(f"official request returned HTTP {status}")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise MirrorUpdateError("official response was not valid JSON") from err

    def latest_round(self) -> int:
        payload = self.get_json(MAIN_INFO_URL)
        try:
            rows = payload["data"]["result"]["pstLtEpstInfo"]["lt645"]
            rounds = [int(item["ltEpsd"]) for item in rows]
        except (KeyError, TypeError, ValueError) as err:
            raise MirrorUpdateError("unexpected latest-round response schema") from err
        if not rounds:
            raise MirrorUpdateError("latest-round response was empty")
        return max(rounds)

    def center(self, round_no: int) -> list[Draw]:
        payload = self.get_json(
            HISTORY_URL,
            {"srchDir": "center", "srchLtEpsd": int(round_no)},
        )
        return parse_official_list(payload)

    def single(self, round_no: int) -> Draw | None:
        payload = self.get_json(
            SINGLE_DRAW_URL, {"srchLtEpsd": int(round_no)}
        )
        for draw in parse_official_list(payload):
            if draw.round == round_no:
                return draw
        return None


def normalize_date(value: Any) -> str:
    text = str(value or "").strip().replace(".", "-").replace("/", "-")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    parts = [part for part in text.split("-") if part]
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return text


def validate_draw(draw: Draw) -> None:
    if draw.round < 1:
        raise MirrorUpdateError("draw round must be positive")
    if len(draw.numbers) != 6 or len(set(draw.numbers)) != 6:
        raise MirrorUpdateError(f"round {draw.round}: invalid six-number set")
    if any(number < 1 or number > 45 for number in draw.numbers):
        raise MirrorUpdateError(f"round {draw.round}: number out of range")
    if draw.bonus < 1 or draw.bonus > 45 or draw.bonus in draw.numbers:
        raise MirrorUpdateError(f"round {draw.round}: invalid bonus number")


def parse_official_item(item: dict[str, Any]) -> Draw:
    try:
        draw = Draw(
            round=int(item["ltEpsd"]),
            draw_date=normalize_date(item.get("ltRflYmd", "")),
            numbers=tuple(
                sorted(int(item[f"tm{i}WnNo"]) for i in range(1, 7))
            ),  # type: ignore[arg-type]
            bonus=int(item["bnsWnNo"]),
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
    except (KeyError, TypeError, ValueError) as err:
        raise MirrorUpdateError("unexpected draw response schema") from err
    validate_draw(draw)
    return draw


def parse_official_list(payload: Any) -> list[Draw]:
    try:
        items = payload["data"]["list"]
    except (KeyError, TypeError) as err:
        raise MirrorUpdateError("unexpected history response schema") from err
    if not isinstance(items, list):
        raise MirrorUpdateError("history response list is invalid")
    rows = [parse_official_item(item) for item in items if isinstance(item, dict)]
    return sorted({row.round: row for row in rows}.values(), key=lambda row: row.round)


def download_seed_db() -> Path:
    request = Request(SEED_DB_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError) as err:
        raise MirrorUpdateError(f"bootstrap seed download failed: {err}") from err
    if not raw.startswith(b"SQLite format 3\x00"):
        raise MirrorUpdateError("bootstrap seed is not a SQLite database")
    temp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp.write(raw)
    temp.close()
    return Path(temp.name)


def load_seed_history() -> list[Draw]:
    path = download_seed_db()
    try:
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                'SELECT round, date, "1st", "2nd", "3rd", "4th", "5th", "6th", bonus '
                "FROM tb_lotto_list ORDER BY round"
            ).fetchall()
    except sqlite3.Error as err:
        raise MirrorUpdateError(f"bootstrap seed database error: {err}") from err
    finally:
        path.unlink(missing_ok=True)

    draws: list[Draw] = []
    for row in rows:
        draw = Draw(
            round=int(row[0]),
            draw_date=normalize_date(row[1]),
            numbers=tuple(sorted(int(value) for value in row[2:8])),  # type: ignore[arg-type]
            bonus=int(row[8]),
        )
        validate_draw(draw)
        draws.append(draw)
    validate_contiguous(draws)
    return draws


def load_existing_mirror() -> list[Draw]:
    if not MIRROR_PATH.exists():
        return []
    try:
        payload = json.loads(MIRROR_PATH.read_text(encoding="utf-8"))
        items = payload["draws"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as err:
        raise MirrorUpdateError(f"existing mirror is invalid: {err}") from err

    draws: list[Draw] = []
    for item in items:
        try:
            draw = Draw(
                round=int(item["round"]),
                draw_date=normalize_date(item.get("draw_date", "")),
                numbers=tuple(sorted(int(value) for value in item["numbers"])),  # type: ignore[arg-type]
                bonus=int(item["bonus"]),
                first_prize_winners=(
                    int(item["first_prize_winners"])
                    if item.get("first_prize_winners") is not None
                    else None
                ),
                first_prize_amount=(
                    int(item["first_prize_amount"])
                    if item.get("first_prize_amount") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise MirrorUpdateError("existing mirror row is invalid") from err
        validate_draw(draw)
        draws.append(draw)
    validate_contiguous(draws)
    return draws


def validate_contiguous(draws: list[Draw]) -> None:
    if not draws:
        raise MirrorUpdateError("history is empty")
    rounds = [draw.round for draw in draws]
    if rounds != list(range(1, rounds[-1] + 1)):
        raise MirrorUpdateError("history must be contiguous from round 1")


def verify_seed_tail(seed: list[Draw], client: OfficialClient) -> None:
    """Cross-check seed rows visible in one official center window."""
    tail_round = seed[-1].round
    official = client.center(tail_round)
    seed_by_round = {draw.round: draw for draw in seed}
    overlaps = [draw for draw in official if draw.round in seed_by_round]
    if not overlaps:
        raise MirrorUpdateError("bootstrap seed could not be cross-checked")
    for draw in overlaps:
        seeded = seed_by_round[draw.round]
        if seeded.numbers != draw.numbers or seeded.bonus != draw.bonus:
            raise MirrorUpdateError(
                f"bootstrap seed mismatch at round {draw.round}; refusing mirror"
            )


def fetch_missing(
    history: list[Draw], latest_round: int, client: OfficialClient
) -> list[Draw]:
    by_round = {draw.round: draw for draw in history}
    wanted = set(range(history[-1].round + 1, latest_round + 1))
    while wanted - set(by_round):
        missing = sorted(wanted - set(by_round))
        pointer = missing[-1]
        page = client.center(pointer)
        before = len(by_round)
        for draw in page:
            if draw.round in wanted:
                by_round[draw.round] = draw
        if len(by_round) == before:
            # One cautious single-round request can fill an endpoint edge case.
            draw = client.single(pointer)
            if draw is not None:
                by_round[draw.round] = draw
        if len(by_round) == before:
            raise MirrorUpdateError(
                f"could not obtain missing round {pointer} without extra crawling"
            )

    result = [by_round[index] for index in range(1, latest_round + 1)]
    validate_contiguous(result)
    return result


def write_mirror(draws: list[Draw], client: OfficialClient, bootstrap: bool) -> None:
    MIRROR_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(UTC).isoformat(),
        "latest_round": draws[-1].round,
        "draw_count": len(draws),
        "source": "Donghaeng Lottery verified shared mirror",
        "official_url": "https://www.dhlottery.co.kr/lt645/result",
        "bootstrap_seed": (
            {
                "repository": "happylie/lotto_data",
                "commit": SEED_COMMIT,
                "used": True,
            }
            if bootstrap
            else {"used": False}
        ),
        "official_requests_this_update": client.requests,
        "draws": [draw.as_dict() for draw in draws],
    }
    MIRROR_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    existing = load_existing_mirror()
    bootstrap = not existing
    client = OfficialClient()

    if bootstrap:
        print("mirror missing: loading pinned historical bootstrap seed")
        history = load_seed_history()
        print(f"seed loaded through round {history[-1].round}")
        verify_seed_tail(history, client)
        print("seed tail verified against Donghaeng Lottery")
    else:
        history = existing
        print(f"existing mirror through round {history[-1].round}")

    latest = client.latest_round()
    print(f"official latest round: {latest}")
    if latest < history[-1].round:
        raise MirrorUpdateError(
            "official latest round is behind the mirror; keeping existing mirror"
        )
    if latest == history[-1].round:
        print(
            f"mirror already current; official requests={client.requests}; no file change"
        )
        return 0

    updated = fetch_missing(history, latest, client)
    write_mirror(updated, client, bootstrap)
    print(
        f"mirror updated: {history[-1].round} -> {updated[-1].round}; "
        f"official requests={client.requests}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MirrorUpdateError as err:
        print(f"ERROR: {err}")
        raise SystemExit(1) from err
