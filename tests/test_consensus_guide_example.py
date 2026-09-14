"""Keep the user-facing median example synchronized with the production formula."""
from pathlib import Path
import re

from test_consensus import A, B, MID, derive, payload, row

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs/methods/selected_median_consensus.md"
BUNDLED = ROOT / "custom_components/lotto_645/www/methods/selected_median_consensus.md"
EXAMPLE = """공식 A:  2, 10, 18, 26, 34, 42
공식 B:  4, 12, 20, 28, 36, 44

중앙값:  3, 11, 19, 27, 35, 43"""


def test_requested_example_is_in_repository_and_packaged_help():
    text = GUIDE.read_text(encoding="utf-8")
    assert text == BUNDLED.read_text(encoding="utf-8")
    assert EXAMPLE in text
    assert "같은 순번의 번호끼리 계산합니다." in text
    assert "무조건 1을 더하거나 빼는 것이 아니라" in text


def test_published_example_matches_the_actual_consensus_engine():
    text = GUIDE.read_text(encoding="utf-8")
    block = re.search(r"```text\n(공식 A:.*?)\n```", text, re.DOTALL)
    assert block is not None
    lines = [line for line in block.group(1).splitlines() if line.strip()]
    tickets = [tuple(int(n.strip()) for n in line.split(":", 1)[1].split(","))
               for line in lines]
    assert len(tickets) == 3
    result = derive(payload([row(A, tickets[0]), row(B, tickets[1], 2)]))
    recommendation = result.recommendation_by_method(MID)
    assert recommendation is not None
    assert recommendation.numbers == tickets[2]
    assert tuple(recommendation.details["consensus_position_medians"]) == tickets[2]
    assert recommendation.details["consensus_position_deviations"] == [0] * 6
