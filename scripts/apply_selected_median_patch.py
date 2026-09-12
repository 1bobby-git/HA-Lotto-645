from pathlib import Path
import json


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# methods.py
path = "custom_components/lotto_645/methods.py"
replace_once(
    path,
    'METHOD_PUBLIC_ENSEMBLE: Final = "public_ensemble"\n# Keep the legacy ID for existing config-entry compatibility.\n',
    'METHOD_PUBLIC_ENSEMBLE: Final = "public_ensemble"\nMETHOD_SELECTED_MEDIAN: Final = "selected_median_consensus"\n# Keep the legacy ID for existing config-entry compatibility.\n',
)
replace_once(
    path,
    '        myungri_weight=0.52,\n        pool_size=22,\n    ),\n)\n',
    '''        myungri_weight=0.52,
        pool_size=22,
    ),
    MethodDefinition(
        METHOD_SELECTED_MEDIAN,
        "합의 추천 · 선택 방식 중앙값",
        "선택 방식 집계",
        (
            "현재 함께 선택한 다른 로컬 추천 방식들의 1~45 번호별 0~1 적합도를 모아 각 번호의 중앙값을 계산합니다. "
            "한 방식의 극단값이 전체를 끌고 가지 않도록 중앙값을 사용하며, 그 중앙값이 높은 번호들로 최종 6개 조합을 만듭니다. "
            "AI 추천은 집계에서 제외하고, 명리 방식은 사용자가 함께 선택한 경우에만 포함합니다. 의미 있는 중앙값을 위해 다른 추천 방식 2개 이상이 필요합니다."
        ),
        {},
        pool_size=26,
    ),
)
''',
)
replace_once(
    path,
    '''            "requirements": (
                "생년월일, 출생시간, 양력/음력, 성별, 출생지, 시간대"
                if method.method_id == METHOD_MYUNGRI_HETU
                else "없음"
            ),
''',
    '''            "requirements": (
                "생년월일, 출생시간, 양력/음력, 성별, 출생지, 시간대"
                if method.method_id == METHOD_MYUNGRI_HETU
                else "다른 추천 방식 2개 이상"
                if method.method_id == METHOD_SELECTED_MEDIAN
                else "없음"
            ),
''',
)

# analysis.py
path = "custom_components/lotto_645/analysis.py"
replace_once(
    path,
    '    METHOD_PUBLIC_ENSEMBLE,\n    METHOD_RECENCY_DECAY,\n',
    '    METHOD_PUBLIC_ENSEMBLE,\n    METHOD_SELECTED_MEDIAN,\n    METHOD_RECENCY_DECAY,\n',
)
replace_once(
    path,
    '''def _method_number_scores(method: MethodDefinition, ranked: dict[str, dict[int, float]]) -> dict[int, float]:
    return {
        number: sum(weight * ranked[feature][number] for feature, weight in method.weights.items())
        / sum(method.weights.values())
        for number in NUMBERS
    }


''',
    '''def _method_number_scores(method: MethodDefinition, ranked: dict[str, dict[int, float]]) -> dict[int, float]:
    if method.method_id == METHOD_SELECTED_MEDIAN:
        values = ranked.get("_selected_median_consensus")
        if values is None:
            raise ValueError("선택 방식 중앙값 계산 정보가 준비되지 않았습니다")
        return dict(values)
    return {
        number: sum(weight * ranked[feature][number] for feature, weight in method.weights.items())
        / sum(method.weights.values())
        for number in NUMBERS
    }


def _prepare_selected_median(
    selected_method_ids: Sequence[str],
    ranked: dict[str, dict[int, float]],
) -> dict[str, Any]:
    """Build a robust consensus score from the user's other selected methods."""
    contributors = tuple(
        method_id for method_id in selected_method_ids
        if method_id != METHOD_SELECTED_MEDIAN
    )
    if len(contributors) < 2:
        raise ValueError("선택 방식 중앙값은 다른 추천 방식을 2개 이상 함께 선택해야 합니다")
    source_scores = {
        method_id: _method_number_scores(METHODS_BY_ID[method_id], ranked)
        for method_id in contributors
    }
    medians: dict[int, float] = {}
    spreads: dict[int, float] = {}
    for number in NUMBERS:
        values = [source_scores[method_id][number] for method_id in contributors]
        medians[number] = float(median(values))
        spreads[number] = max(values) - min(values)
    ranked["_selected_median_consensus"] = medians
    return {
        "source_method_ids": list(contributors),
        "source_method_labels": [METHODS_BY_ID[method_id].label for method_id in contributors],
        "source_count": len(contributors),
        "median_scores": medians,
        "score_spreads": spreads,
        "vote_counts": {number: 0 for number in NUMBERS},
        "rule": "선택한 다른 로컬 방식들의 번호별 0~1 적합도 중앙값; AI 제외",
    }


''',
)
replace_once(
    path,
    '    if method.method_id == METHOD_MYUNGRI_HETU:\n        meta = context["myungri"]\n',
    '''    if method.method_id == METHOD_SELECTED_MEDIAN:
        meta = context["selected_median_consensus"]
        votes = meta.get("vote_counts", {})
        vote_leaders = sorted(combo, key=lambda n: (-votes.get(n, 0), -meta["median_scores"][n], n))[:2]
        reason = (
            f"선택한 다른 {meta['source_count']}개 방식의 번호별 적합도 중앙값을 사용; "
            f"선택결과 중 지지표가 높은 {vote_leaders[0]}·{vote_leaders[1]}, "
            f"중앙값 상위 조합을 과거 1등·중복 제외 조건으로 확정"
        )
    elif method.method_id == METHOD_MYUNGRI_HETU:
        meta = context["myungri"]
''',
)
replace_once(
    path,
    '''    if method.method_id == METHOD_MYUNGRI_HETU:
        details.update(combo_myungri_details(combo, context["myungri"]))
    return reason, details
''',
    '''    if method.method_id == METHOD_SELECTED_MEDIAN:
        meta = context["selected_median_consensus"]
        details.update(
            {
                "consensus_source_method_ids": meta["source_method_ids"],
                "consensus_source_methods": meta["source_method_labels"],
                "consensus_source_count": meta["source_count"],
                "consensus_rule": meta["rule"],
                "consensus_number_median_scores": {
                    str(number): round(meta["median_scores"][number], 6) for number in combo
                },
                "consensus_number_score_spread": {
                    str(number): round(meta["score_spreads"][number], 6) for number in combo
                },
                "consensus_number_support_votes": {
                    str(number): int(meta.get("vote_counts", {}).get(number, 0)) for number in combo
                },
            }
        )
    if method.method_id == METHOD_MYUNGRI_HETU:
        details.update(combo_myungri_details(combo, context["myungri"]))
    return reason, details
''',
)
replace_once(
    path,
    '    profile = saju_profile if METHOD_MYUNGRI_HETU in selected_method_ids else None\n    ranked, context = _feature_maps(history, profile)\n',
    '''    profile = saju_profile if METHOD_MYUNGRI_HETU in selected_method_ids else None
    ranked, context = _feature_maps(history, profile)
    if METHOD_SELECTED_MEDIAN in selected_method_ids:
        context["selected_median_consensus"] = _prepare_selected_median(
            selected_method_ids, ranked
        )
''',
)
replace_once(
    path,
    '''    selected: list[tuple[int, ...]] = []
    recommendations: list[Recommendation] = []
    for index, method_id in enumerate(selected_method_ids, start=1):
        method = METHODS_BY_ID[method_id]
''',
    '''    selected: list[tuple[int, ...]] = []
    recommendations: list[Recommendation] = []
    execution_method_ids = tuple(
        method_id for method_id in selected_method_ids
        if method_id != METHOD_SELECTED_MEDIAN
    ) + ((METHOD_SELECTED_MEDIAN,) if METHOD_SELECTED_MEDIAN in selected_method_ids else ())
    for index, method_id in enumerate(execution_method_ids, start=1):
        method = METHODS_BY_ID[method_id]
        if method_id == METHOD_SELECTED_MEDIAN:
            contributor_ids = set(context["selected_median_consensus"]["source_method_ids"])
            votes = Counter(
                number
                for recommendation in recommendations
                if recommendation.method_id in contributor_ids
                for number in recommendation.numbers
            )
            context["selected_median_consensus"]["vote_counts"] = {
                number: votes[number] for number in NUMBERS
            }
''',
)
replace_once(
    path,
    '''                "number_feature_weights": {key: round(value / sum(method.weights.values()), 6)
                                           for key, value in method.weights.items()},
                "number_feature_scores": {str(n): {key: round(ranked[key][n], 6)
                                                   for key in method.weights} for n in combo},
''',
    '''                "number_feature_weights": (
                    {"selected_method_median": 1.0}
                    if method.method_id == METHOD_SELECTED_MEDIAN
                    else {key: round(value / sum(method.weights.values()), 6)
                          for key, value in method.weights.items()}
                ),
                "number_feature_scores": (
                    {str(n): {
                        "selected_method_median": round(
                            context["selected_median_consensus"]["median_scores"][n], 6
                        ),
                        "source_score_spread": round(
                            context["selected_median_consensus"]["score_spreads"][n], 6
                        ),
                        "support_votes": int(
                            context["selected_median_consensus"].get("vote_counts", {}).get(n, 0)
                        ),
                    } for n in combo}
                    if method.method_id == METHOD_SELECTED_MEDIAN
                    else {str(n): {key: round(ranked[key][n], 6)
                                   for key in method.weights} for n in combo}
                ),
''',
)
replace_once(
    path,
    '        "algorithm": "selectable_multi_formula_v6_audited_saju",\n',
    '        "algorithm": "selectable_multi_formula_v7_selected_median_consensus",\n',
)
replace_once(
    path,
    '        "selected_method_ids": list(selected_method_ids),\n',
    '        "selected_method_ids": list(selected_method_ids),\n        "execution_method_ids": list(execution_method_ids),\n',
)

# config_flow.py
path = "custom_components/lotto_645/config_flow.py"
replace_once(
    path,
    '    METHOD_MYUNGRI_HETU,\n    METHODS_BY_ID,\n',
    '    METHOD_MYUNGRI_HETU,\n    METHOD_SELECTED_MEDIAN,\n    METHODS_BY_ID,\n',
)
replace_once(
    path,
    '''                if not normalized:
                    errors[CONF_SELECTED_METHODS] = "select_at_least_one"
                else:
                    pending = dict(self._options)
''',
    '''                if not normalized:
                    errors[CONF_SELECTED_METHODS] = "select_at_least_one"
                elif (
                    METHOD_SELECTED_MEDIAN in normalized
                    and sum(method_id != METHOD_SELECTED_MEDIAN for method_id in normalized) < 2
                ):
                    errors["base"] = "consensus_sources_required"
                else:
                    pending = dict(self._options)
''',
)

# translations
for path in (
    "custom_components/lotto_645/strings.json",
    "custom_components/lotto_645/translations/en.json",
):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    desc = data["options"]["step"]["recommendations"]["data_description"]["selected_methods"]
    if "median" not in desc.lower():
        data["options"]["step"]["recommendations"]["data_description"]["selected_methods"] = (
            desc + " The selected-method median consensus requires at least two other local methods and excludes AI."
        )
    data["options"]["error"]["consensus_sources_required"] = (
        "The selected-method median consensus requires at least two other recommendation methods."
    )
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

path = "custom_components/lotto_645/translations/ko.json"
data = json.loads(Path(path).read_text(encoding="utf-8"))
desc = data["options"]["step"]["recommendations"]["data_description"]["selected_methods"]
if "중앙값" not in desc:
    data["options"]["step"]["recommendations"]["data_description"]["selected_methods"] = (
        desc + " '합의 추천 · 선택 방식 중앙값'은 AI를 제외한 다른 로컬 방식 2개 이상을 함께 선택해야 합니다."
    )
data["options"]["error"]["consensus_sources_required"] = (
    "'합의 추천 · 선택 방식 중앙값'을 사용하려면 다른 추천 방식을 2개 이상 함께 선택하세요."
)
Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# tests
path = "tests/test_analysis_engine.py"
replace_once(path, "    assert len(methods.METHODS) == 16\n", "    assert len(methods.METHODS) == 17\n")
replace_once(
    path,
    '''        if method.method_id == methods.METHOD_MYUNGRI_HETU:
            continue
''',
    '''        if method.method_id in {methods.METHOD_MYUNGRI_HETU, methods.METHOD_SELECTED_MEDIAN}:
            continue
''',
)
p = Path(path)
text = p.read_text(encoding="utf-8")
addition = '''


def test_selected_median_requires_two_other_methods():
    history = _history(120)
    with pytest.raises(ValueError, match="2개 이상"):
        analysis.build_analysis(
            history,
            (methods.METHOD_WEIGHTED_FREQUENCY, methods.METHOD_SELECTED_MEDIAN),
        )


def test_selected_median_uses_only_selected_local_methods_and_runs_last():
    history = _history(120)
    selected = (
        methods.METHOD_PHASE_RESIDUAL,
        methods.METHOD_WEIGHTED_FREQUENCY,
        methods.METHOD_PAIR_COOCCURRENCE,
        methods.METHOD_SELECTED_MEDIAN,
    )
    result = analysis.build_analysis(history, selected, 0)
    assert len(result.recommendations) == 4
    consensus = result.recommendations[-1]
    assert consensus.method_id == methods.METHOD_SELECTED_MEDIAN
    assert consensus.details["consensus_source_count"] == 3
    assert consensus.details["consensus_source_method_ids"] == list(selected[:-1])
    assert consensus.details["consensus_rule"].startswith("선택한 다른 로컬 방식")
    assert set(consensus.details["consensus_number_median_scores"]) == {
        str(number) for number in consensus.numbers
    }
    assert all(
        0 <= value <= 3
        for value in consensus.details["consensus_number_support_votes"].values()
    )
    assert consensus.numbers not in {draw.numbers for draw in history}
    assert result.summary["execution_method_ids"][-1] == methods.METHOD_SELECTED_MEDIAN
'''
if "test_selected_median_requires_two_other_methods" not in text:
    p.write_text(text + addition, encoding="utf-8")

# README
path = "README.md"
p = Path(path)
text = p.read_text(encoding="utf-8")
section = '''
## v1.7.0 · 선택 방식 중앙값 합의 추천

`합의 추천 · 선택 방식 중앙값`을 추가했습니다. 사용자가 함께 선택한 **다른 로컬 추천 방식 2개 이상**의 1~45 번호별 0~1 적합도를 모아 각 번호의 **중앙값(median)** 을 계산하고 중앙값이 높은 번호들로 6개 조합을 만듭니다. 한 방식의 극단값이 전체를 끌고 가지 않게 하는 강건 집계 방식입니다. AI 추천은 집계하지 않으며, 명리 방식은 사용자가 함께 선택했을 때만 포함합니다.

단순히 각 추천게임의 1번째·2번째 번호를 위치별로 평균/중앙값 내지 않습니다. 그런 계산은 존재하지 않는 인공 번호를 만들 수 있으므로, **각 방식이 1~45 각각에 부여한 내부 적합도의 중앙값**을 사용합니다. 센서 속성에서 참여 방식, 번호별 중앙값, 방식 간 점수 범위, 최종 추천에서 받은 지지표 수를 확인할 수 있습니다. 이 합의 점수 역시 당첨 확률이 아닙니다.

'''
if "## v1.7.0 · 선택 방식 중앙값 합의 추천" not in text:
    text = text.replace("# HA-Lotto-645\n", "# HA-Lotto-645\n" + section, 1)
text = text.replace("## 추천 방식 16종", "## 추천 방식 17종")
text = text.replace(
    "16. 명리 권장 · 개인 사주 원국·대운·추첨일",
    "16. 명리 권장 · 개인 사주 원국·대운·추첨일\n17. 합의 추천 · 선택 방식 중앙값",
)
p.write_text(text, encoding="utf-8")

# formulas doc
path = "docs/FORMULAS.md"
p = Path(path)
text = p.read_text(encoding="utf-8")
formula_section = '''

## 합의 추천 · 선택 방식 중앙값

사용자가 동시에 선택한 다른 로컬 추천 방식들의 **번호별 0~1 적합도**를 번호 1~45 각각에 대해 수집하고 중앙값을 계산합니다. 예를 들어 한 번호의 세 방식 점수가 `0.31, 0.72, 0.95`라면 중앙합의 점수는 `0.72`입니다. 특정 방식 하나의 극단치에 덜 민감한 강건 집계입니다.

- 최소 다른 방식 2개 필요
- AI 추천은 집계 제외
- 명리는 사용자가 함께 선택한 경우 포함
- 선택된 다른 방식의 추천게임에서 해당 번호가 실제 선택된 횟수도 `support_votes`로 별도 표시
- 최종 조합은 과거 1등 완전일치·현재 추천 중복을 계속 제외
- 번호별 중앙값과 방식 간 최대-최소 점수 범위를 센서 속성으로 공개

이 방식은 여러 휴리스틱의 **중앙 경향을 요약**하는 것이며 독립 추첨의 수학적 당첨확률을 높인다는 뜻이 아닙니다.
'''
if "## 합의 추천 · 선택 방식 중앙값" not in text:
    text += formula_section
p.write_text(text, encoding="utf-8")

# changelog
path = "CHANGELOG.md"
p = Path(path)
text = p.read_text(encoding="utf-8")
changelog = '''## 1.7.0

- `합의 추천 · 선택 방식 중앙값` 추가.
- 선택한 다른 로컬 방식 2개 이상의 번호별 0~1 적합도를 중앙값으로 강건 집계.
- AI는 집계 제외, 명리는 선택된 경우만 집계.
- 중앙값 참여 방식·번호별 중앙값·방식 간 점수 범위·최종 지지표 수를 센서 속성으로 공개.
- 중앙합의는 항상 기초 방식들을 먼저 생성한 뒤 마지막 게임으로 계산.
- 과거 1등 완전일치·추천 중복·재생성 제외 규칙 유지.

'''
if "## 1.7.0" not in text:
    text = text.replace("# Changelog\n\n", "# Changelog\n\n" + changelog, 1)
p.write_text(text, encoding="utf-8")

replace_once("custom_components/lotto_645/const.py", 'VERSION = "1.6.1"', 'VERSION = "1.7.0"')
path = "custom_components/lotto_645/manifest.json"
data = json.loads(Path(path).read_text(encoding="utf-8"))
data["version"] = "1.7.0"
Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("Applied selected-method median consensus changes")
