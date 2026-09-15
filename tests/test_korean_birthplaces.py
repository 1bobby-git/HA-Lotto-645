from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=spec_from_file_location(
    "lotto_korean_birthplaces",
    ROOT/"custom_components/lotto_645/korean_birthplaces.py",
)
MODULE=module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_korean_birthplace_catalog_is_small_fixed_and_unique():
    values=MODULE.KOREAN_BIRTHPLACES
    assert len(values)==17 and len(set(values))==17
    assert values[0]=="서울특별시"
    assert "세종특별자치시" in values and "제주특별자치도" in values
    assert MODULE.is_supported_birthplace("경기도")
    assert not MODULE.is_supported_birthplace("free form")


def test_legacy_value_is_preserved_but_not_open_ended():
    options=MODULE.birthplace_selector_options("Tokyo, Japan")
    assert options[0]=={
        "value":"Tokyo, Japan",
        "label":"기존 입력 · Tokyo, Japan",
    }
    assert len(options)==18
    assert MODULE.is_supported_birthplace("Tokyo, Japan",legacy="Tokyo, Japan")
    assert not MODULE.is_supported_birthplace("Osaka, Japan",legacy="Tokyo, Japan")
