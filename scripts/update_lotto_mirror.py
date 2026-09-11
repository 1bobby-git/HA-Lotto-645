#!/usr/bin/env python3
"""Build/update the shared Lotto 6/45 history mirror conservatively.

Goal: Home Assistant clients should not individually crawl Donghaeng Lottery.
The weekly GitHub Actions job obtains the historical set from a current public
GitHub dataset in one archive download, then cross-checks the current tail with
Donghaeng Lottery using at most a few sequential requests.

No proxy rotation, CAPTCHA bypass, IP evasion, concurrency, or rapid retries are
used. HTTP 403/429 stops the job immediately and the last valid mirror remains.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MIRROR_PATH = ROOT / "data" / "lotto645-history.json"
BUNDLED_SEED_PATH = ROOT / "custom_components" / "lotto_645" / "history_seed.json"

MAIN_INFO_URL = "https://www.dhlottery.co.kr/selectMainInfo.do"
HISTORY_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
SINGLE_DRAW_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do"
OFFICIAL_RESULT_URL = "https://www.dhlottery.co.kr/lt645/result"

COMMUNITY_REPO = "Utopia-ZEN/hotnumber"
COMMUNITY_ARCHIVE_URL = f"https://github.com/{COMMUNITY_REPO}/archive/refs/heads/main.zip"
FIRST_DRAW_DATE = date(2002, 12, 7)

MIN_OFFICIAL_INTERVAL_SECONDS = 3.0
MAX_OFFICIAL_REQUESTS = 4
TIMEOUT_SECONDS = 20
USER_AGENT = (
    "HA-Lotto-645-Mirror/1.1 "
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
        if elapsed < MIN_OFFICIAL_INTERVAL_SECONDS:
            time.sleep(MIN_OFFICIAL_INTERVAL_SECONDS - elapsed)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if self.requests >= MAX_OFFICIAL_REQUESTS:
            raise MirrorUpdateError(
                f"official request safety limit reached ({MAX_OFFICIAL_REQUESTS})"
            )
        self._wait()
        target = url if not params else f"{url}?{urlencode(params)}"
        request = Request(
            target,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": USER_AGENT,
                "Referer": OFFICIAL_RESULT_URL,
            },
        )
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read()
        except HTTPError as err:
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
        payload = self.get_json(SINGLE_DRAW_URL, {"srchLtEpsd": int(round_no)})
        for draw in parse_official_list(payload):
            if draw.round == round_no:
                return draw
        return None


def normalize_date(value: Any, round_no: int) -> str:
    text = str(value or "").strip().replace(".", "-").replace("/", "-")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    parts = [part for part in text.split("-") if part]
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    if round_no >= 1:
        return (FIRST_DRAW_DATE + timedelta(days=(round_no - 1) * 7)).isoformat()
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
        round_no = int(item["ltEpsd"])
        draw = Draw(
            round=round_no,
            draw_date=normalize_date(item.get("ltRflYmd", ""), round_no),
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


def download_community_history() -> list[Draw]:
    """Download one GitHub archive instead of issuing 1,200+ HTTP requests."""
    request = Request(COMMUNITY_ARCHIVE_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=45) as response:
            archive = response.read()
    except (HTTPError, URLError, TimeoutError) as err:
        raise MirrorUpdateError(f"community mirror archive download failed: {err}") from err

    draws: dict[int, Draw] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            for name in zf.namelist():
                parts = Path(name).parts
                if len(parts) < 4 or parts[-3] != "lotto_data":
                    continue
                if not parts[-2].replace("-", "").isdigit():
                    continue
                if not parts[-1].endswith(".lotto"):
                    continue
                stem = Path(parts[-1]).stem
                if not stem.isdigit():
                    continue
                data = json.loads(zf.read(name).decode("utf-8"))
                round_no = int(data["round"])
                draw = Draw(
                    round=round_no,
                    draw_date=normalize_date(data.get("date", ""), round_no),
                    numbers=tuple(sorted(int(v) for v in data["numbers"])),  # type: ignore[arg-type]
                    bonus=int(data["bonus"]),
                    first_prize_winners=(
                        int(data["winners"])
                        if data.get("winners") is not None
                        else None
                    ),
                    first_prize_amount=(
                        int(data["amount_per_winner"])
                        if data.get("amount_per_winner") is not None
                        else None
                    ),
                )
                validate_draw(draw)
                draws[round_no] = draw
    except (zipfile.BadZipFile, KeyError, TypeError, ValueError, json.JSONDecodeError) as err:
        raise MirrorUpdateError(f"community mirror archive is invalid: {err}") from err

    rows = [draws[index] for index in sorted(draws)]
    validate_contiguous(rows)
    return rows


def load_existing_mirror() -> list[Draw]:
    if not MIRROR_PATH.exists():
        return []
    try:
        payload = json.loads(MIRROR_PATH.read_text(encoding="utf-8"))
        items = payload["draws"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as err:
        raise MirrorUpdateError(f"existing mirror is invalid: {err}") from err

    rows: list[Draw] = []
    for item in items:
        round_no = int(item["round"])
        draw = Draw(
            round=round_no,
            draw_date=normalize_date(item.get("draw_date", ""), round_no),
            numbers=tuple(sorted(int(v) for v in item["numbers"])),  # type: ignore[arg-type]
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
        validate_draw(draw)
        rows.append(draw)
    validate_contiguous(rows)
    return rows


def validate_contiguous(draws: list[Draw]) -> None:
    if not draws:
        raise MirrorUpdateError("history is empty")
    rounds = [draw.round for draw in draws]
    if rounds != list(range(1, rounds[-1] + 1)):
        raise MirrorUpdateError("history must be contiguous from round 1")


def verify_with_official(draws: list[Draw], client: OfficialClient) -> None:
    """Cross-check current community tail with a tiny official request budget."""
    official_latest = client.latest_round()
    if official_latest != draws[-1].round:
        if official_latest < draws[-1].round:
            raise MirrorUpdateError(
                f"community source is ahead of official latest ({draws[-1].round}>{official_latest})"
            )
        gap = official_latest - draws[-1].round
        if gap > 1:
            raise MirrorUpdateError(
                f"community source is {gap} rounds behind official; keep previous mirror"
            )
        # A one-round publication lag can be filled with one official single request.
        missing = client.single(official_latest)
        if missing is None:
            raise MirrorUpdateError("latest official round could not be read safely")
        draws.append(missing)

    latest = draws[-1]
    try:
        official_window = client.center(latest.round)
    except MirrorUpdateError:
        # If the list endpoint times out, a single-round endpoint is a bounded fallback.
        official_single = client.single(latest.round)
        official_window = [official_single] if official_single is not None else []

    match = next((row for row in official_window if row.round == latest.round), None)
    if match is None:
        raise MirrorUpdateError("latest round could not be cross-checked with official data")
    if match.numbers != latest.numbers or match.bonus != latest.bonus:
        raise MirrorUpdateError(
            f"latest round {latest.round} disagrees with official Donghaeng Lottery data"
        )


def draws_hash(draws: list[Draw]) -> str:
    canonical = json.dumps(
        [draw.as_dict() for draw in draws],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_payload(draws: list[Draw], client: OfficialClient) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "updated_at": datetime.now(UTC).isoformat(),
        "latest_round": draws[-1].round,
        "draw_count": len(draws),
        "draws_sha256": draws_hash(draws),
        "source": "shared GitHub mirror cross-checked with Donghaeng Lottery",
        "official_url": OFFICIAL_RESULT_URL,
        "community_source": {
            "repository": COMMUNITY_REPO,
            "role": "bulk historical transport",
        },
        "official_requests_this_update": client.requests,
        "draws": [draw.as_dict() for draw in draws],
    }


def write_payload(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    MIRROR_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUNDLED_SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    MIRROR_PATH.write_text(text, encoding="utf-8")
    BUNDLED_SEED_PATH.write_text(text, encoding="utf-8")


def same_draws(existing: list[Draw], incoming: list[Draw]) -> bool:
    return [d.as_dict() for d in existing] == [d.as_dict() for d in incoming]


def main() -> int:
    existing = load_existing_mirror()
    candidate = download_community_history()
    print(f"community history through round {candidate[-1].round}")

    client = OfficialClient()
    verify_with_official(candidate, client)
    validate_contiguous(candidate)
    print(
        f"official verification complete; latest={candidate[-1].round}; "
        f"official requests={client.requests}"
    )

    if existing and same_draws(existing, candidate):
        # Keep mirror updated_at stable, but make sure the release-bundled seed exists.
        if not BUNDLED_SEED_PATH.exists():
            BUNDLED_SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
            BUNDLED_SEED_PATH.write_bytes(MIRROR_PATH.read_bytes())
            print("mirror unchanged; bundled seed created")
        else:
            print("mirror unchanged")
        return 0

    payload = build_payload(candidate, client)
    write_payload(payload)
    old = existing[-1].round if existing else 0
    print(f"mirror updated: {old} -> {candidate[-1].round}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MirrorUpdateError as err:
        print(f"ERROR: {err}")
        raise SystemExit(1) from err
