"""Public formula metadata only. No formula implementation or weighting code."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
from .service_contract import Catalog

METHOD_MYUNGRI_HETU = "myungri_hetu_day_pillar"
METHOD_SELECTED_MEDIAN = "selected_median_consensus"
METHOD_SELECTED_VOTE = "selected_vote_consensus"
DEFAULT_METHOD_IDS = ("uniform_fisher_yates",)
ADVANCED_METHOD_IDS = set()
RETIRED_METHOD_LABELS = {"personal_lucky":"개인 행운 번호 (종료)",
                       "portfolio_triplet_coverage":"다중 조합 (종료)"}

@dataclass(frozen=True)
class Method:
    method_id: str
    label: str
    category: str
    description: str
    formula_version: str
    options_schema: dict
    requires_personal_profile: bool = False
    status: str = "active"
    sampling: str | None = None

METHODS_BY_ID: dict[str, Method] = {}

def install_catalog(catalog: Catalog) -> None:
    # Retain metadata for historical records and unavailable old sensors.
    active = set()
    for row in catalog.methods:
        METHODS_BY_ID[row.formula_id] = Method(row.formula_id, row.name,
            row.category, row.public_summary, row.formula_version,
            row.options_schema, row.requires_personal_profile, row.status)
        active.add(row.formula_id)
    for key, old in list(METHODS_BY_ID.items()):
        if key not in active:
            from dataclasses import replace
            METHODS_BY_ID[key] = replace(old, status="withdrawn")

def normalize_method_ids(value):
    if not isinstance(value, (list, tuple)):
        return DEFAULT_METHOD_IDS
    return tuple(dict.fromkeys(str(x) for x in value if str(x) in METHODS_BY_ID))

def consensus_source_ids(value):
    return tuple(x for x in value if x in METHODS_BY_ID and x not in
                 (METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE))

def method_selector_options(*, advanced=False):
    return [{"value":m.method_id,"label":m.label} for m in METHODS_BY_ID.values()
            if (m.method_id in ADVANCED_METHOD_IDS) == advanced]

def method_catalog():
    return [{"method_id":m.method_id,"formula_id":m.method_id,"label":m.label,
             "category":m.category,"name":m.label,"description":m.description,
             "requirements":"개인정보 원격 계산 동의 필요" if m.requires_personal_profile else "별도 연결 설정 없이 이용",
             "formula_version":m.formula_version,"status":m.status,
             "options_schema":m.options_schema} for m in METHODS_BY_ID.values()]

# Public descriptions bootstrap the offline wallet; service catalog is authoritative.
install_catalog(Catalog.parse(json.loads(Path(__file__).with_name("catalog_seed.json").read_text(encoding="utf-8"))))

METHODS=tuple(METHODS_BY_ID.values())  # compatibility descriptions, not calculations
