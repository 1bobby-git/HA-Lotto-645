"""Built-in South Korean birthplace choices for the Saju options flow.

The birth-place label is metadata for the local Four Pillars calculation. Korea
uses one civil timezone, so new Korean choices are paired with Asia/Seoul in the
options flow. No geocoding or network download is required.
"""
from __future__ import annotations

KOREAN_BIRTHPLACES: tuple[str, ...] = (
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
    "경기도",
    "강원특별자치도",
    "충청북도",
    "충청남도",
    "전북특별자치도",
    "전라남도",
    "경상북도",
    "경상남도",
    "제주특별자치도",
)
KOREAN_BIRTHPLACE_VALUES = frozenset(KOREAN_BIRTHPLACES)


def birthplace_selector_options(current: object = None) -> list[dict[str, str]]:
    """Return the fixed Korean choices plus one saved legacy value if needed."""
    value = str(current or "").strip()
    result = [{"value": item, "label": item} for item in KOREAN_BIRTHPLACES]
    if value and value not in KOREAN_BIRTHPLACE_VALUES:
        result.insert(0, {"value": value, "label": f"기존 입력 · {value}"})
    return result


def is_supported_birthplace(value: object, *, legacy: object = None) -> bool:
    """Accept Korea choices and only the exact value already saved by older versions."""
    text = str(value or "").strip()
    previous = str(legacy or "").strip()
    return bool(text) and (
        text in KOREAN_BIRTHPLACE_VALUES or (previous and text == previous)
    )
