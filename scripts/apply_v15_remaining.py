from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing replacement marker in {path}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# analysis.py: feed the validated personal profile into the 명리 engine.
replace_once(
    "custom_components/lotto_645/analysis.py",
    "def _feature_maps(history: list[LottoDraw]) -> tuple[dict[str, dict[int, float]], dict[str, Any]]:",
    "def _feature_maps(\n    history: list[LottoDraw],\n    saju_profile: dict[str, Any] | None = None,\n) -> tuple[dict[str, dict[int, float]], dict[str, Any]]:",
)
replace_once(
    "custom_components/lotto_645/analysis.py",
    "    myungri = build_myungri_context(history[-1].draw_date)\n",
    "    myungri = build_myungri_context(history[-1].draw_date, saju_profile)\n",
)
replace_once(
    "custom_components/lotto_645/analysis.py",
    "def build_analysis(history: list[LottoDraw], method_ids: Sequence[str] | None = None, generation_nonce: int = 0) -> AnalysisResult:",
    "def build_analysis(\n    history: list[LottoDraw],\n    method_ids: Sequence[str] | None = None,\n    generation_nonce: int = 0,\n    saju_profile: dict[str, Any] | None = None,\n) -> AnalysisResult:",
)
replace_once(
    "custom_components/lotto_645/analysis.py",
    "    ranked, context = _feature_maps(history)\n",
    "    ranked, context = _feature_maps(history, saju_profile)\n    if (\n        METHOD_MYUNGRI_HETU in selected_method_ids\n        and context[\"myungri\"].get(\"status\") != \"ready\"\n    ):\n        raise ValueError(\"명리 권장은 개인 사주정보 입력 후 사용할 수 있습니다\")\n",
)
replace_once(
    "custom_components/lotto_645/analysis.py",
    '        "algorithm": "selectable_multi_formula_v4",',
    '        "algorithm": "selectable_multi_formula_v5_personal_saju",',
)
old_reason = '''        reason = (\n            f"{meta.get('target_draw_date') or '다음 추첨일'} {meta.get('sexagenary_day') or '일진'}의 일간 "\n            f"{meta.get('day_master_element_ko') or '오행'}과 하도 수리오행의 상생·동기 관계, "\n            f"오행 분산·음양 균형을 중심으로 {pair[0]}-{pair[1]} 통계 연결을 보조 반영"\n        )'''
new_reason = '''        favorable = "·".join(meta.get("favorable_elements_ko", [])) or "보완오행"\n        interactions = meta.get("interactions", {})\n        positive_count = len(interactions.get("stem_harmony", [])) + len(interactions.get("branch_harmony", []))\n        negative_count = len(interactions.get("stem_clash", [])) + len(interactions.get("branch_clash_harm_punishment", []))\n        reason = (\n            f"개인 원국 일간 {meta.get('day_master') or '-'}({meta.get('day_master_element_ko') or '-'}), "\n            f"{meta.get('strength') or '강약 미정'} 기준 보완오행 {favorable}; "\n            f"대운과 {meta.get('target_draw_date') or '다음 추첨일'} 사주의 합계열 {positive_count}건·충해형 {negative_count}건, "\n            f"하도 수리오행 및 {pair[0]}-{pair[1]} 통계 연결을 보조 반영"\n        )'''
replace_once("custom_components/lotto_645/analysis.py", old_reason, new_reason)
old_summary = '''        "myungri_context": {\n            "status": myungri.get("status"),\n            "target_draw_date": myungri.get("target_draw_date"),\n            "sexagenary_day": myungri.get("sexagenary_day"),\n            "day_master": myungri.get("day_master"),\n            "day_master_element": myungri.get("day_master_element_ko"),\n            "day_branch": myungri.get("day_branch"),\n            "day_branch_element": myungri.get("day_branch_element_ko"),\n            "notice": myungri.get("notice"),\n        },'''
new_summary = '''        "myungri_context": {\n            "status": myungri.get("status"),\n            "profile_configured": myungri.get("status") == "ready",\n            "target_draw_date": myungri.get("target_draw_date"),\n            "day_master": myungri.get("day_master"),\n            "day_master_element": myungri.get("day_master_element_ko"),\n            "day_master_strength": myungri.get("strength"),\n            "favorable_elements": myungri.get("favorable_elements_ko"),\n            "current_daewoon": myungri.get("luck_cycle", {}).get("current") if myungri.get("status") == "ready" else None,\n            "target_interactions": myungri.get("interactions"),\n            "notice": myungri.get("notice"),\n            "privacy_notice": myungri.get("privacy_notice"),\n        },'''
replace_once("custom_components/lotto_645/analysis.py", old_summary, new_summary)

# sensor.py: show a dedicated profile/status entity even for upgraded users who
# previously had 명리 selected without personal information.
replace_once(
    "custom_components/lotto_645/sensor.py",
    "from .methods import METHODS_BY_ID, method_catalog\n",
    "from .methods import METHOD_MYUNGRI_HETU, METHODS_BY_ID, method_catalog\n",
)
replace_once(
    "custom_components/lotto_645/sensor.py",
    "    entities.extend(\n        LottoGameSensor(coordinator, method_id)\n        for method_id in coordinator.selected_method_ids\n    )\n",
    "    if METHOD_MYUNGRI_HETU in coordinator.configured_method_ids:\n        entities.append(LottoSajuProfileSensor(coordinator))\n    entities.extend(\n        LottoGameSensor(coordinator, method_id)\n        for method_id in coordinator.selected_method_ids\n    )\n",
)
replace_once(
    "custom_components/lotto_645/sensor.py",
    '            "ai_enabled": self.coordinator.ai_enabled,\n',
    '            "saju_profile_status": self.coordinator.saju_profile_status,\n            "ai_enabled": self.coordinator.ai_enabled,\n',
)
marker = "\n\nclass LottoGameSensor(Lotto645Entity, SensorEntity):\n"
insert = '''\n\nclass LottoSajuProfileSensor(Lotto645Entity, SensorEntity):\n    \"\"\"Show whether personal Saju is configured and expose derived natal context.\"\"\"\n\n    _attr_name = \"명리 사주 프로필\"\n    _attr_icon = \"mdi:yin-yang\"\n\n    def __init__(self, coordinator: Lotto645Coordinator) -> None:\n        super().__init__(coordinator)\n        self._attr_unique_id = f\"{coordinator.entry.entry_id}_saju_profile\"\n\n    @property\n    def native_value(self) -> str:\n        return \"준비됨\" if self.coordinator.saju_profile_ready else \"설정 필요\"\n\n    @property\n    def extra_state_attributes(self) -> dict:\n        base = {\n            \"status\": self.coordinator.saju_profile_status,\n            \"required_before_use\": True,\n            \"required_fields\": [\"양력/음력\", \"생년월일\", \"출생시간\", \"성별\", \"출생지\", \"시간대\"],\n            \"privacy\": \"입력값은 Home Assistant 구성에 로컬 저장되며 로또 미러와 HA AI 추천 프롬프트에 원본 생년월일·출생시간·출생지를 보내지 않습니다.\",\n        }\n        recommendation = self.coordinator.data.analysis.recommendation_by_method(METHOD_MYUNGRI_HETU)\n        if recommendation is None:\n            base[\"message\"] = \"통합 구성을 열어 개인 사주정보를 입력하면 명리 권장 추천이 활성화됩니다.\"\n            return base\n        details = recommendation.details\n        for key in (\n            \"birth_profile\", \"four_pillars\", \"pillar_details\", \"day_master\",\n            \"day_master_element\", \"day_master_strength\", \"support_ratio\",\n            \"five_element_balance\", \"ten_god_element_roles\", \"favorable_elements\",\n            \"avoid_elements\", \"current_daewoon\", \"target_draw_date\",\n            \"target_draw_time\", \"target_draw_four_pillars\", \"target_interactions\",\n            \"traditional_notice\", \"privacy_notice\",\n        ):\n            if key in details:\n                base[key] = details[key]\n        return base\n'''
replace_once("custom_components/lotto_645/sensor.py", marker, insert + marker)

# CI installs the exact runtime dependency used by the integration.
replace_once(
    ".github/workflows/validate.yml",
    "run: python -m pip install --upgrade pip pytest",
    'run: python -m pip install --upgrade pip pytest "lunar_python==1.4.8"',
)

# Pure engine regression tests for profile gating + personal Four Pillars.
test_path = ROOT / "tests/test_analysis_engine.py"
test_path.write_text('''"""Pure-Python regression tests for the deterministic analysis engine."""\n\nfrom __future__ import annotations\n\nfrom datetime import date\nimport importlib.util\nfrom pathlib import Path\nimport random\nimport sys\nimport types\nimport pytest\n\nROOT = Path(__file__).resolve().parents[1]\nPACKAGE_PATH = ROOT / "custom_components" / "lotto_645"\ncustom_components = types.ModuleType("custom_components")\ncustom_components.__path__ = [str(ROOT / "custom_components")]\nsys.modules.setdefault("custom_components", custom_components)\npackage = types.ModuleType("custom_components.lotto_645")\npackage.__path__ = [str(PACKAGE_PATH)]\nsys.modules.setdefault("custom_components.lotto_645", package)\n\ndef _load(name: str) -> types.ModuleType:\n    full_name = f"custom_components.lotto_645.{name}"\n    spec = importlib.util.spec_from_file_location(full_name, PACKAGE_PATH / f"{name}.py")\n    assert spec is not None and spec.loader is not None\n    module = importlib.util.module_from_spec(spec)\n    sys.modules[full_name] = module\n    spec.loader.exec_module(module)\n    return module\n\nconst = _load("const")\nmodels = _load("models")\nmethods = _load("methods")\nmyungri = _load("myungri")\nanalysis = _load("analysis")\n\ndef _history(count: int = 180):\n    rng = random.Random(645)\n    rows = []\n    start = date(2022, 1, 1)\n    for round_no in range(1, count + 1):\n        numbers = tuple(sorted(rng.sample(range(1, 46), 6)))\n        remaining = [number for number in range(1, 46) if number not in numbers]\n        draw_date = start.fromordinal(start.toordinal() + (round_no - 1) * 7)\n        rows.append(models.LottoDraw(round=round_no, draw_date=draw_date.isoformat(), numbers=numbers, bonus=rng.choice(remaining)))\n    return rows\n\ndef _profile():\n    return {\n        "calendar": "solar", "birth_date": "1990-05-17", "birth_time": "14:30",\n        "lunar_leap_month": False, "gender": "male", "birth_place": "Seoul",\n        "timezone": "Asia/Seoul", "true_solar_time": False, "longitude": None,\n    }\n\ndef test_catalog_and_default_gating():\n    assert len(methods.METHODS) == 16\n    assert len(methods.PUBLIC_METHOD_IDS) == 12\n    assert methods.METHOD_MYUNGRI_HETU not in methods.DEFAULT_METHOD_IDS\n    myungri_method = methods.METHODS_BY_ID[methods.METHOD_MYUNGRI_HETU]\n    assert "개인 사주" in myungri_method.description\n\ndef test_personal_saju_profile_builds_four_pillars():\n    profile = _profile()\n    myungri.validate_saju_profile(profile)\n    context = myungri.build_myungri_context("2026-09-05", profile)\n    assert context["status"] == "ready"\n    assert set(context["natal_pillars"]) == {"year", "month", "day", "time"}\n    assert context["day_master"]\n    assert context["strength"] in {"신강", "신약", "중화"}\n    assert context["favorable_elements_ko"]\n    assert context["target_pillars"]["day"]["ganzhi"]\n    assert context["luck_cycle"]\n\ndef test_myungri_requires_profile():\n    with pytest.raises(ValueError, match="개인 사주정보"):\n        analysis.build_analysis(_history(), (methods.METHOD_MYUNGRI_HETU,))\n\ndef test_personal_myungri_recommendation_details():\n    history = _history()\n    selected = (methods.METHOD_PHASE_RESIDUAL, methods.METHOD_MYUNGRI_HETU)\n    result = analysis.build_analysis(history, selected, 0, _profile())\n    traditional = result.recommendation_by_method(methods.METHOD_MYUNGRI_HETU)\n    assert traditional is not None\n    assert traditional.details["saju_profile_status"] == "준비됨"\n    assert len(traditional.details["four_pillars"]) == 4\n    assert traditional.details["day_master_strength"] in {"신강", "신약", "중화"}\n    assert traditional.details["current_daewoon"]\n    assert traditional.details["target_interactions"] is not None\n    assert traditional.numbers not in {draw.numbers for draw in history}\n\ndef test_manual_generation_nonce_rotates_local_candidates():\n    history = _history(120)\n    selected = (methods.METHOD_PHASE_RESIDUAL, methods.METHOD_WEIGHTED_FREQUENCY, methods.METHOD_PUBLIC_ENSEMBLE)\n    baseline = analysis.build_analysis(history, selected, 0)\n    regenerated = analysis.build_analysis(history, selected, 1)\n    assert [item.numbers for item in baseline.recommendations] != [item.numbers for item in regenerated.recommendations]\n''', encoding="utf-8")

# UI translations: add an explicit second step for personal birth information.
def patch_translation(path: str, korean: bool) -> None:
    p = ROOT / path
    data = json.loads(p.read_text(encoding="utf-8"))
    options = data.setdefault("options", {})
    steps = options.setdefault("step", {})
    init = steps.setdefault("init", {})
    if korean:
        init["description"] = "추천 방식을 하나 이상 선택하세요. '명리 권장 · 개인 사주 원국·대운·추첨일'을 선택하면 다음 단계에서 개인 사주정보를 반드시 입력해야 활성화됩니다."
        steps["saju"] = {
            "title": "개인 사주정보 입력",
            "description": "명리 권장 사용 전 필수 단계입니다. 연·월·일·시주와 대운을 계산하기 위해 출생정보를 입력합니다. 입력값은 Home Assistant에 로컬 저장되며 로또 미러와 HA AI에 원본 출생정보를 보내지 않습니다.",
            "data": {
                "saju_calendar": "출생일 기준 (양력/음력)", "saju_birth_date": "생년월일", "saju_birth_time": "출생시간",
                "saju_gender": "성별 (대운 순·역행 계산용)", "saju_birth_place": "출생지", "saju_timezone": "출생지 시간대 (IANA)",
                "saju_lunar_leap_month": "음력 윤달", "saju_true_solar_time": "진태양시 보정 사용", "saju_longitude": "출생지 경도 (진태양시 보정 시 필수)"
            },
            "data_description": {
                "saju_birth_place": "예: Seoul, South Korea. 표시/기록용이며 외부 지오코딩을 호출하지 않습니다.",
                "saju_timezone": "예: Asia/Seoul", "saju_lunar_leap_month": "양력 출생이면 무시됩니다.",
                "saju_true_solar_time": "선택 시 표준시 자오선과 출생지 경도, 균시차를 이용해 시주용 시각을 보정합니다.",
                "saju_longitude": "예: 서울 약 126.9780. 진태양시를 끈 경우 비워도 됩니다."
            }
        }
        options.setdefault("error", {})["invalid_saju_profile"] = "사주정보가 누락되었거나 유효하지 않습니다. 생년월일·출생시간·달력 구분·성별·출생지·시간대를 확인하세요."
    else:
        init["description"] = "Select one or more methods. Selecting the personal Four Pillars method requires completing the birth-profile step before it can be activated."
        steps["saju"] = {
            "title": "Personal Four Pillars profile",
            "description": "Required before the personal Saju method can run. Raw birth values remain in Home Assistant and are not sent to the lottery mirror or to HA AI prompts.",
            "data": {
                "saju_calendar": "Birth calendar", "saju_birth_date": "Birth date", "saju_birth_time": "Birth time", "saju_gender": "Gender (luck-cycle direction)",
                "saju_birth_place": "Birth place", "saju_timezone": "Birth timezone (IANA)", "saju_lunar_leap_month": "Lunar leap month",
                "saju_true_solar_time": "Use true solar time correction", "saju_longitude": "Birth longitude"
            }
        }
        options.setdefault("error", {})["invalid_saju_profile"] = "The Four Pillars profile is missing or invalid. Check all required birth fields."
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

patch_translation("custom_components/lotto_645/strings.json", False)
patch_translation("custom_components/lotto_645/translations/en.json", False)
patch_translation("custom_components/lotto_645/translations/ko.json", True)

# Documentation and changelog.
replace_once(
    "README.md",
    "# HA-Lotto-645\n",
    "# HA-Lotto-645\n\n## v1.5.0 · 개인 사주 명리 고도화\n\n`명리 권장 · 개인 사주 원국·대운·추첨일`은 이제 **사주정보 입력 전에는 실행되지 않습니다.** 통합 구성에서 이 방식을 선택하면 양력/음력, 생년월일, 출생시간, 성별, 출생지, IANA 시간대를 입력하는 별도 단계가 열립니다. 음력 윤달과 진태양시(경도+균시차) 보정도 지원합니다.\n\n입력 후 연주·월주·일주·시주, 일간, 오행 강약, 지장간, 십신, 납음, 12운성, 대운을 계산하고 다음 추첨일 20:35의 사주와 천간합·충, 지지합·충·해·형을 비교합니다. 번호는 하도 수리오행에 매핑해 보완오행/십신 역할/대운·추첨일 관계를 주 점수로 사용하고 기존 로또 통계는 보조 점수로만 사용합니다.\n\n> 개인 출생정보는 HA 구성에 로컬 저장되며 공유 로또 미러에 전송되지 않습니다. HA AI 추천에도 원본 생년월일·출생시간·출생지를 넣지 않습니다. 명리 해석은 전통 문화 체계의 재현 가능한 휴리스틱이며 당첨 확률 상승이 과학적으로 검증된 것은 아닙니다.\n",
)
replace_once(
    "CHANGELOG.md",
    "# Changelog\n",
    "# Changelog\n\n## 1.5.0 — 2026-09-11\n\n### Added\n- 명리 권장 사용 전 필수 개인 사주정보 입력 단계\n- lunar_python 1.4.8 기반 연·월·일·시주, 절기 기준 팔자, 지장간, 십신, 납음, 12운성 계산\n- 성별에 따른 대운 순·역행 및 현재 대운 계산\n- 추첨일 20:35 사주와 원국의 천간합·충, 지지합·충·해·형 관계 분석\n- 음력/윤달 입력, IANA 시간대, 선택적 진태양시 경도·균시차 보정\n- 명리 사주 프로필 상태/상세 센서\n\n### Changed\n- 명리 권장을 `개인 사주 원국·대운·추첨일` 방식으로 고도화\n- 개인 사주정보가 없으면 명리 추천 센서를 생성하지 않고 `설정 필요` 상태만 표시\n- 신규 기본 추천 목록에서 명리 방식을 제외하여 명시적 선택+프로필 입력 후에만 활성화\n- 명리 점수를 주 신호로 높이고 로또 통계 점수는 보조 신호로 축소\n- HA AI 추천 프롬프트에 원본 생년월일·출생시간·출생지를 전달하지 않도록 명시\n\n",
)
with (ROOT / "docs/FORMULAS.md").open("a", encoding="utf-8") as f:
    f.write("""\n\n## v1.5 개인 사주 명리 고도화\n\n명리 권장은 더 이상 추첨일 일진만으로 계산하지 않습니다. 사용자가 직접 입력한 출생정보로 절기 기준 사주 원국(연·월·일·시주)을 만들고 일간, 오행 강약, 지장간, 십신, 납음, 12운성, 대운을 계산합니다. 이후 다음 추첨일 20:35의 사주와 원국의 천간합·충 및 지지합·충·해·형을 비교합니다.\n\n번호 1~45는 하도 수리오행으로 분류하며, 신강/신약/중화에 따른 **보완 오행 후보**, 십신 역할, 원국 내 부족 오행, 대운 및 추첨일 오행 관계를 개인별 번호 공명 점수로 환산합니다. 최종 조합에서는 보완오행 포함률, 오행 분산, 음양 균형을 함께 평가하고 번호쌍/전이/미출현/최근 빈도는 보조 점수로만 사용합니다.\n\n`용신`은 학파별 판단 차이가 크므로 이 통합은 단정적인 용신을 선언하지 않고 **보완 오행 후보**라는 용어를 사용합니다. 진태양시는 선택 기능이며, 활성화한 경우 출생지 경도와 해당 역사적 시간대 UTC 오프셋 및 균시차를 이용해 시주 계산 시각을 보정합니다.\n\n> 사주 계산 규칙의 재현 가능성과 로또 예측력은 별개의 문제입니다. 이 방식은 당첨 확률을 높인다고 검증되지 않았습니다.\n""")

print("v1.5 remaining patch applied")
