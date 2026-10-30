"""Shared history mirror updater: lag catch-up and visible failures (no network)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "update_lotto_mirror_under_test", ROOT / "scripts" / "update_lotto_mirror.py"
)
mirror = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mirror  # dataclasses resolve annotations via sys.modules
_SPEC.loader.exec_module(mirror)


def make(round_no: int, shift: int = 0):
    numbers = tuple(sorted(((round_no + shift + step) % 45) + 1 for step in (0, 7, 14, 21, 28, 35)))
    bonus = ((round_no + shift + 42) % 45) + 1
    return mirror.Draw(round_no, mirror.normalize_date("", round_no), numbers, bonus)


def history(last: int) -> list:
    return [make(round_no) for round_no in range(1, last + 1)]


class FakeOfficial:
    """Official endpoints with the script's own request budget enforced."""

    def __init__(self, latest: int):
        self.latest = latest
        self.requests = 0

    def _count(self) -> None:
        self.requests += 1
        assert self.requests <= mirror.MAX_OFFICIAL_REQUESTS, "official request budget exceeded"

    def latest_round(self) -> int:
        self._count()
        return self.latest

    def single(self, round_no: int):
        self._count()
        return make(round_no) if round_no <= self.latest else None

    def center(self, round_no: int) -> list:
        self._count()
        return [make(n) for n in range(max(1, round_no - 2), min(self.latest, round_no + 2) + 1)]


def test_current_source_is_cross_checked_without_lag():
    draws = history(12)
    client = FakeOfficial(12)
    assert mirror.verify_with_official(draws, client) == 0
    assert draws[-1].round == 12 and client.requests == 2


def test_one_round_publication_lag_is_still_filled_in_one_run():
    draws = history(11)
    client = FakeOfficial(12)
    assert mirror.verify_with_official(draws, client) == 0
    assert [draw.round for draw in draws][-2:] == [11, 12]


def test_two_round_lag_adds_the_next_official_round_instead_of_aborting():
    draws = history(10)
    client = FakeOfficial(12)
    remaining = mirror.verify_with_official(draws, client)
    assert draws[-1].round == 11 and remaining == 1
    assert client.requests <= mirror.MAX_OFFICIAL_REQUESTS


def test_disagreement_with_official_still_stops_the_update():
    draws = history(12)
    draws[-1] = make(12, shift=1)
    with pytest.raises(mirror.MirrorUpdateError, match="disagrees"):
        mirror.verify_with_official(draws, FakeOfficial(12))


def test_source_ahead_of_official_still_stops_the_update():
    with pytest.raises(mirror.MirrorUpdateError, match="ahead"):
        mirror.verify_with_official(history(13), FakeOfficial(12))


def test_previous_verified_mirror_extends_a_lagging_community_archive():
    merged = mirror.extend_with_verified_mirror(history(10), history(12))
    assert [draw.round for draw in merged] == list(range(1, 13))
    assert mirror.extend_with_verified_mirror(history(12), history(10))[-1].round == 12


def test_disagreeing_previous_mirror_is_not_used_for_extension():
    previous = history(12)
    previous[4] = make(5, shift=3)
    merged = mirror.extend_with_verified_mirror(history(10), previous)
    assert merged[-1].round == 10


def _run_main(monkeypatch, *, community: int, existing: int, official: int):
    written = []
    client = FakeOfficial(official)
    monkeypatch.setattr(mirror, "load_existing_mirror", lambda: history(existing))
    monkeypatch.setattr(mirror, "download_community_history", lambda: history(community))
    monkeypatch.setattr(mirror, "OfficialClient", lambda: client)
    monkeypatch.setattr(mirror, "write_payload", written.append)
    return mirror.run(), written, client


def test_abandoned_community_archive_keeps_the_mirror_advancing(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    code, written, client = _run_main(monkeypatch, community=10, existing=12, official=13)
    assert code == 0 and written[0]["latest_round"] == 13
    assert client.requests <= mirror.MAX_OFFICIAL_REQUESTS
    assert "::warning" not in capsys.readouterr().out


def test_remaining_lag_is_committed_and_reported_as_a_warning(monkeypatch, capsys, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    code, written, _client = _run_main(monkeypatch, community=10, existing=10, official=13)
    assert code == 0 and written[0]["latest_round"] == 11
    out = capsys.readouterr().out
    assert "::warning title=Lotto history mirror::" in out and "2 round" in out
    assert "2 round" in summary.read_text(encoding="utf-8")


def test_failure_exits_non_zero_with_a_visible_error_annotation(monkeypatch, capsys, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    def blocked():
        raise mirror.MirrorUpdateError("Donghaeng Lottery returned HTTP 403; stop without retry")

    monkeypatch.setattr(mirror, "main", blocked)
    assert mirror.run() == 1
    out = capsys.readouterr().out
    assert "ERROR: Donghaeng Lottery returned HTTP 403" in out
    assert "::error title=Lotto history mirror::Donghaeng Lottery returned HTTP 403" in out
    assert "HTTP 403" in summary.read_text(encoding="utf-8")


def test_annotations_stay_plain_outside_github_actions(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    mirror.annotate("warning", "line one\nline two")
    out = capsys.readouterr().out
    assert out.startswith("WARNING: line one") and "::" not in out


def test_annotation_escapes_workflow_command_characters(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    mirror.annotate("error", "100% failed\nnext")
    assert "::error title=Lotto history mirror::100%25 failed%0Anext" in capsys.readouterr().out
