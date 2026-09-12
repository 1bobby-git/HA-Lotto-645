from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:180]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "custom_components/lotto_645/coordinator.py"
replace_once(
    path,
    '''        recommendations = [item.to_storage() for item in analysis.recommendations]\n        if ai_recommendation is not None:\n            recommendations.append(ai_recommendation.to_storage())\n''',
    '''        def minimal_item(item: Recommendation) -> dict[str, Any]:\n            # The result checker only needs identity + six numbers.  Do not copy\n            # large analysis details or derived Saju context into the persistent\n            # prediction snapshot.\n            return {\n                "index": item.index,\n                "method_id": item.method_id,\n                "label": item.label,\n                "method": item.method,\n                "numbers": list(item.numbers),\n                "reason": "",\n                "score": None,\n                "details": {},\n                "source": item.source,\n            }\n\n        recommendations = [minimal_item(item) for item in analysis.recommendations]\n        if ai_recommendation is not None:\n            recommendations.append(minimal_item(ai_recommendation))\n''',
)
replace_once(
    path,
    '''        if self.data is not None:\n            self._set_prediction_snapshot(\n                self.data.analysis,\n                self.data.ai_recommendation,\n                self.data.ai_generated_at,\n            )\n        changed = False\n''',
    '''        if self.data is not None:\n            self._set_prediction_snapshot(\n                self.data.analysis,\n                self.data.ai_recommendation,\n                self.data.ai_generated_at,\n            )\n        elif self._prediction_snapshot is None and self.history:\n            # Upgrade compatibility: v1.7 and older did not persist recommendation\n            # snapshots.  Reconstruct the currently displayed target round from\n            # the cached pre-draw history before accepting a newer mirror round.\n            try:\n                profile = self.saju_profile if self.saju_profile_ready else None\n                cached_analysis = await self.hass.async_add_executor_job(\n                    build_analysis,\n                    self.history,\n                    self.selected_method_ids,\n                    self._local_generation_nonce,\n                    profile,\n                    self._regeneration_exclusions,\n                )\n            except ValueError as err:\n                _LOGGER.debug("기존 추천 스냅샷 재구성 생략: %s", err)\n            else:\n                self._set_prediction_snapshot(\n                    cached_analysis,\n                    self._cached_ai_recommendation,\n                    self._cached_ai_generated_at,\n                )\n        changed = False\n''',
)

# Document that the snapshot intentionally excludes personal/large analysis details.
path = "CHANGELOG.md"
replace_once(
    path,
    "- 추첨 결과가 들어오면서 다음 회차 추천으로 넘어가기 전에 직전 추천 스냅샷을 영구 저장·판정해 결과가 덮어써지지 않도록 개선.\n",
    "- 추첨 결과가 들어오면서 다음 회차 추천으로 넘어가기 전에 직전 추천 스냅샷을 영구 저장·판정해 결과가 덮어써지지 않도록 개선. 스냅샷에는 센서명·방식ID·6개 번호 등 판정에 필요한 최소 정보만 저장하며 명리 상세정보는 복제하지 않음.\n",
)
