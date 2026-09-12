from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# coordinator.py
path = "custom_components/lotto_645/coordinator.py"
replace_once(
    path,
    "from .myungri import extract_saju_profile, has_complete_saju_profile\n",
    "from .myungri import extract_saju_profile, has_complete_saju_profile\nfrom .result_evaluator import evaluate_recommendations\n",
)
replace_once(
    path,
    "        self._regeneration_exclusions: tuple[tuple[int, ...], ...] = ()\n        self._manual_lock = asyncio.Lock()\n",
    "        self._regeneration_exclusions: tuple[tuple[int, ...], ...] = ()\n        self._prediction_snapshot: dict[str, Any] | None = None\n        self._draw_evaluation: dict[str, Any] | None = None\n        self._manual_lock = asyncio.Lock()\n",
)
replace_once(
    path,
    "    @property\n    def local_generated_at(self) -> datetime | None:\n        return self._local_generated_at\n\n    async def _async_setup(self) -> None:\n",
    "    @property\n    def local_generated_at(self) -> datetime | None:\n        return self._local_generated_at\n\n    @property\n    def last_draw_evaluation(self) -> dict[str, Any] | None:\n        \"\"\"Return the latest persisted recommendation-vs-draw evaluation.\"\"\"\n        return self._draw_evaluation\n\n    async def _async_setup(self) -> None:\n",
)
replace_once(
    path,
    "        if payload:\n            try:\n                draws = [\n",
    "        if payload:\n            try:\n                prediction_snapshot = payload.get(\"prediction_snapshot\")\n                if isinstance(prediction_snapshot, dict):\n                    self._prediction_snapshot = prediction_snapshot\n                draw_evaluation = payload.get(\"draw_evaluation\")\n                if isinstance(draw_evaluation, dict):\n                    self._draw_evaluation = draw_evaluation\n                draws = [\n",
)
replace_once(
    path,
    "                self._local_generated_at = None\n                _LOGGER.warning(\"로또 로컬 캐시를 읽지 못했습니다: %s\", err)\n",
    "                self._local_generated_at = None\n                self._prediction_snapshot = None\n                self._draw_evaluation = None\n                _LOGGER.warning(\"로또 로컬 캐시를 읽지 못했습니다: %s\", err)\n",
)
replace_once(
    path,
    "                \"ai_generated_at\": (\n                    self._cached_ai_generated_at.isoformat()\n                    if self._cached_ai_generated_at\n                    else None\n                ),\n            }\n        )\n",
    "                \"ai_generated_at\": (\n                    self._cached_ai_generated_at.isoformat()\n                    if self._cached_ai_generated_at\n                    else None\n                ),\n                \"prediction_snapshot\": self._prediction_snapshot,\n                \"draw_evaluation\": self._draw_evaluation,\n            }\n        )\n",
)
replace_once(
    path,
    "    @staticmethod\n    def _history_changed(left: list[LottoDraw], right: list[LottoDraw]) -> bool:\n",
    '''    def _build_prediction_snapshot(\n        self,\n        analysis: AnalysisResult,\n        ai_recommendation: Recommendation | None,\n        ai_generated_at: datetime | None,\n    ) -> dict[str, Any]:\n        recommendations = [item.to_storage() for item in analysis.recommendations]\n        if ai_recommendation is not None:\n            recommendations.append(ai_recommendation.to_storage())\n        return {\n            "target_round": analysis.target_round,\n            "based_on_round": analysis.based_on_round,\n            "local_generation_sequence": self._local_generation_nonce,\n            "local_generated_at": (\n                self._local_generated_at.isoformat() if self._local_generated_at else None\n            ),\n            "ai_generated_at": ai_generated_at.isoformat() if ai_generated_at else None,\n            "recommendations": recommendations,\n        }\n\n    def _set_prediction_snapshot(\n        self,\n        analysis: AnalysisResult,\n        ai_recommendation: Recommendation | None,\n        ai_generated_at: datetime | None,\n    ) -> None:\n        snapshot = self._build_prediction_snapshot(\n            analysis, ai_recommendation, ai_generated_at\n        )\n        if snapshot != self._prediction_snapshot:\n            self._prediction_snapshot = snapshot\n            self._needs_storage_save = True\n\n    def _evaluate_prediction_snapshot(self) -> None:\n        snapshot = self._prediction_snapshot\n        if not isinstance(snapshot, dict):\n            return\n        try:\n            target_round = int(snapshot.get("target_round", 0))\n        except (TypeError, ValueError):\n            return\n        if target_round <= 0:\n            return\n        if self._draw_evaluation and self._draw_evaluation.get("round") == target_round:\n            return\n        draw = next((item for item in self.history if item.round == target_round), None)\n        if draw is None:\n            return\n        try:\n            recommendations = tuple(\n                Recommendation.from_storage(item)\n                for item in snapshot.get("recommendations", [])\n                if isinstance(item, dict)\n            )\n        except (KeyError, TypeError, ValueError) as err:\n            _LOGGER.warning("저장된 추천 스냅샷을 당첨 판정에 사용할 수 없습니다: %s", err)\n            return\n        self._draw_evaluation = evaluate_recommendations(\n            draw,\n            recommendations,\n            prediction_snapshot=snapshot,\n            evaluated_at=datetime.now(UTC),\n        )\n        self._needs_storage_save = True\n        _LOGGER.info(\n            "%s회 추천 결과 판정 완료: %s게임 중 %s게임 당첨, 최고 %s",\n            target_round,\n            self._draw_evaluation.get("checked_game_count", 0),\n            self._draw_evaluation.get("winning_game_count", 0),\n            self._draw_evaluation.get("highest_prize", "미당첨"),\n        )\n\n    @staticmethod\n    def _history_changed(left: list[LottoDraw], right: list[LottoDraw]) -> bool:\n''',
)
replace_once(
    path,
    "    async def _async_update_data(self) -> Lotto645Data:\n        \"\"\"Prefer the shared mirror; never crawl official history from HA clients.\"\"\"\n        changed = False\n",
    "    async def _async_update_data(self) -> Lotto645Data:\n        \"\"\"Prefer the shared mirror; never crawl official history from HA clients.\"\"\"\n        if self.data is not None:\n            self._set_prediction_snapshot(\n                self.data.analysis,\n                self.data.ai_recommendation,\n                self.data.ai_generated_at,\n            )\n        changed = False\n",
)
replace_once(
    path,
    "        if self.history[-1].round != old_latest_round:\n            self._cached_ai_recommendation = None\n",
    "        if self.history[-1].round != old_latest_round:\n            self._evaluate_prediction_snapshot()\n            self._cached_ai_recommendation = None\n",
)
replace_once(
    path,
    "        if self._needs_storage_save:\n            await self._save_storage()\n\n        return Lotto645Data(\n",
    "        self._set_prediction_snapshot(analysis, ai_recommendation, ai_generated_at)\n        if self._needs_storage_save:\n            await self._save_storage()\n\n        return Lotto645Data(\n",
)
replace_once(
    path,
    "        self.data = replace(\n            self.data,\n            ai_recommendation=recommendation,\n            ai_status=\"ready\",\n            ai_error=None,\n            ai_generated_at=generated_at,\n        )\n        await self._save_storage()\n",
    "        self.data = replace(\n            self.data,\n            ai_recommendation=recommendation,\n            ai_status=\"ready\",\n            ai_error=None,\n            ai_generated_at=generated_at,\n        )\n        self._set_prediction_snapshot(self.data.analysis, recommendation, generated_at)\n        await self._save_storage()\n",
)

# sensor.py
path = "custom_components/lotto_645/sensor.py"
replace_once(
    path,
    "    DISCLAIMER,\n    FIRST_PRIZE_ODDS,\n",
    "    AI_METHOD_ID,\n    DISCLAIMER,\n    FIRST_PRIZE_ODDS,\n",
)
replace_once(
    path,
    "        LottoMethodGuideSensor(coordinator),\n        LottoLatestDrawSensor(coordinator),\n",
    "        LottoMethodGuideSensor(coordinator),\n        LottoLatestDrawSensor(coordinator),\n        LottoDrawNumbersSensor(coordinator),\n        LottoWinningStatusSensor(coordinator),\n",
)
replace_once(
    path,
    "\n\nclass LottoLatestDrawSensor(Lotto645Entity, SensorEntity):\n",
    '''\n\nclass LottoDrawNumbersSensor(Lotto645Entity, SensorEntity):\n    \"\"\"Show the six main numbers of the latest completed official draw.\"\"\"\n\n    _attr_name = "추첨번호"\n    _attr_icon = "mdi:counter"\n\n    def __init__(self, coordinator: Lotto645Coordinator) -> None:\n        super().__init__(coordinator)\n        self._attr_unique_id = f"{coordinator.entry.entry_id}_draw_numbers"\n\n    @property\n    def native_value(self) -> str:\n        draw = self.coordinator.data.latest_draw\n        return ", ".join(str(number) for number in draw.numbers)\n\n    @property\n    def extra_state_attributes(self) -> dict:\n        draw = self.coordinator.data.latest_draw\n        return {\n            "round": draw.round,\n            "draw_date": draw.draw_date,\n            "winning_numbers": list(draw.numbers),\n            "bonus_number": draw.bonus,\n            "first_prize_winners": draw.first_prize_winners,\n            "first_prize_amount": draw.first_prize_amount,\n            "source_status": self.coordinator.data.source_status,\n            "data_source": SOURCE_NAME,\n            "source_url": SOURCE_RESULT_URL,\n        }\n\n\nclass LottoWinningStatusSensor(Lotto645Entity, SensorEntity):\n    \"\"\"Summarize how the saved recommendations performed after a draw.\"\"\"\n\n    _unrecorded_attributes = frozenset({"results", "winners", "losers"})\n    _attr_name = "당첨 여부"\n    _attr_icon = "mdi:ticket-percent-outline"\n\n    def __init__(self, coordinator: Lotto645Coordinator) -> None:\n        super().__init__(coordinator)\n        self._attr_unique_id = f"{coordinator.entry.entry_id}_winning_status"\n\n    @property\n    def native_value(self) -> str:\n        evaluation = self.coordinator.last_draw_evaluation\n        if not evaluation:\n            return "판정 대기"\n        winning_count = int(evaluation.get("winning_game_count", 0))\n        if winning_count:\n            return f"{winning_count}개 당첨 · 최고 {evaluation.get('highest_prize', '당첨')}"\n        return "전체 미당첨"\n\n    def _decorate_result(self, result: dict) -> dict:\n        method_id = str(result.get("method_id", ""))\n        if method_id == AI_METHOD_ID:\n            unique_id = f"{self.coordinator.entry.entry_id}_ai_recommendation"\n        else:\n            unique_id = f"{self.coordinator.entry.entry_id}_method_{method_id}"\n        return {**result, "recommendation_sensor_unique_id": unique_id}\n\n    @property\n    def extra_state_attributes(self) -> dict:\n        evaluation = self.coordinator.last_draw_evaluation\n        if not evaluation:\n            return {\n                "status": "waiting",\n                "message": (\n                    "현재 추천 대상 회차의 추첨번호가 갱신되면 저장된 모든 추천 센서를 "\n                    "자동으로 대조해 1~5등 또는 미당첨을 판정합니다."\n                ),\n                "prize_rules": "1등=6개, 2등=5개+보너스, 3등=5개, 4등=4개, 5등=3개",\n            }\n        results = [self._decorate_result(item) for item in evaluation.get("results", [])]\n        winners = [item for item in results if item.get("status") == "당첨"]\n        losers = [item for item in results if item.get("status") == "미당첨"]\n        return {\n            "status": "evaluated",\n            "round": evaluation.get("round"),\n            "draw_date": evaluation.get("draw_date"),\n            "winning_numbers": evaluation.get("winning_numbers"),\n            "bonus_number": evaluation.get("bonus_number"),\n            "evaluated_at": evaluation.get("evaluated_at"),\n            "prediction_based_on_round": evaluation.get("prediction_based_on_round"),\n            "prediction_generation_sequence": evaluation.get("prediction_generation_sequence"),\n            "prediction_generated_at": evaluation.get("prediction_generated_at"),\n            "checked_game_count": evaluation.get("checked_game_count", 0),\n            "winning_game_count": evaluation.get("winning_game_count", 0),\n            "losing_game_count": evaluation.get("losing_game_count", 0),\n            "highest_prize": evaluation.get("highest_prize"),\n            "highest_prize_sensor": evaluation.get("highest_prize_sensor"),\n            "results": results,\n            "winners": winners,\n            "losers": losers,\n            "prize_rules": "1등=6개, 2등=5개+보너스, 3등=5개, 4등=4개, 5등=3개",\n            "note": "실제 entity_id는 사용자가 이름을 변경할 수 있으므로 센서명과 unique_id를 함께 제공합니다.",\n        }\n\n\nclass LottoLatestDrawSensor(Lotto645Entity, SensorEntity):\n''',
)

# __init__.py: fast polling only during the Korean Saturday draw-result window.
path = "custom_components/lotto_645/__init__.py"
replace_once(
    path,
    "from __future__ import annotations\n\nimport voluptuous as vol\n",
    "from __future__ import annotations\n\nfrom datetime import time, timedelta\nfrom zoneinfo import ZoneInfo\n\nimport voluptuous as vol\n",
)
replace_once(
    path,
    "from homeassistant.core import HomeAssistant, ServiceCall\nfrom homeassistant.helpers import config_validation as cv\n",
    "from homeassistant.core import HomeAssistant, ServiceCall, callback\nfrom homeassistant.helpers import config_validation as cv\nfrom homeassistant.helpers.event import async_track_time_interval\n",
)
replace_once(
    path,
    "    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))\n\n    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n",
    '''    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))\n\n    seoul_tz = ZoneInfo("Asia/Seoul")\n\n    @callback\n    def _draw_result_window_tick(now) -> None:\n        local = now.astimezone(seoul_tz)\n        if (\n            local.weekday() == 5\n            and time(20, 30) <= local.time().replace(tzinfo=None) <= time(22, 30)\n        ):\n            hass.async_create_task(\n                coordinator.async_request_refresh(),\n                "lotto_645_draw_result_refresh",\n            )\n\n    entry.async_on_unload(\n        async_track_time_interval(\n            hass, _draw_result_window_tick, timedelta(minutes=5)\n        )\n    )\n\n    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n''',
)

# Version and changelog.
path = "custom_components/lotto_645/const.py"
replace_once(path, 'VERSION = "1.7.0"\n', 'VERSION = "1.8.0"\n')
path = "custom_components/lotto_645/manifest.json"
replace_once(path, '  "version": "1.7.0"\n', '  "version": "1.8.0"\n')
path = "CHANGELOG.md"
replace_once(
    path,
    "# Changelog\n\n",
    '''# Changelog\n\n## 1.8.0\n\n- `추첨번호` 센서 추가: 최신 확정 회차의 본번호 6개를 상태로 표시하고 보너스·회차·추첨일을 속성으로 제공.\n- `당첨 여부` 센서 추가: 새 회차가 들어오기 직전 저장된 모든 로컬 추천과 AI 추천을 스냅샷으로 보존하고 실제 추첨번호와 자동 대조.\n- 공식 1~5등 규칙(6개 / 5개+보너스 / 5개 / 4개 / 3개)에 따라 추천 센서별 당첨·미당첨, 일치번호, 보너스 일치, 최고등수를 표시.\n- 추첨 결과가 들어오면서 다음 회차 추천으로 넘어가기 전에 직전 추천 스냅샷을 영구 저장·판정해 결과가 덮어써지지 않도록 개선.\n- 토요일 20:30~22:30 KST 동안 공유 미러를 5분 간격으로 확인하는 추첨 결과 전용 폴링 추가. 동행복권 직접 접근은 기존처럼 기본 OFF이며 이 폴링도 공유 미러 우선.\n\n''',
)

# README: add the two requested sensors and explain evaluation timing.
path = "README.md"
replace_once(
    path,
    "# HA-Lotto-645\n\n",
    '''# HA-Lotto-645\n\n## v1.8.0 · 추첨번호 및 자동 당첨 판정\n\n- **추첨번호**: 최신 확정 회차의 본번호 6개를 상태로 표시하고 보너스번호·회차·추첨일을 속성으로 제공합니다.\n- **당첨 여부**: 해당 회차 추첨 전에 생성되어 저장된 모든 로컬 추천 센서와 Home Assistant AI 추천(존재하는 경우)을 실제 결과와 비교합니다. 1등=6개, 2등=5개+보너스, 3등=5개, 4등=4개, 5등=3개로 판정하며 센서별 당첨/미당첨과 일치번호를 속성에서 확인할 수 있습니다.\n- 추천 결과는 새 추첨 결과가 들어오면서 다음 회차용 번호로 바뀌기 **전에 스냅샷으로 저장**되므로 직전 회차 판정이 유실되지 않습니다.\n- 토요일 20:30~22:30(KST)에는 5분 간격으로 공유 미러 갱신을 확인합니다. 각 HA 설치가 동행복권을 반복 크롤링하지 않으며 직접 폴백은 기존처럼 사용자가 명시적으로 켠 경우만 제한적으로 사용합니다.\n\n''',
)
replace_once(
    path,
    "- 최신 당첨 결과\n",
    "- 최신 당첨 결과\n- 추첨번호\n- 당첨 여부\n",
)

# HA smoke test: exercise persistence/evaluation contract without network calls.
path = "scripts/smoke_ha_options.py"
replace_once(
    path,
    "        obj._manual_lock=asyncio.Lock();obj._local_generation_nonce=0\n",
    "        obj._manual_lock=asyncio.Lock();obj._local_generation_nonce=0\n        obj._prediction_snapshot=None;obj._draw_evaluation=None;obj._needs_storage_save=False\n",
)
replace_once(
    path,
    "        obj.history=[obj.data.latest_draw]\n",
    '''        obj.history=[obj.data.latest_draw]\n        obj._prediction_snapshot={\n            "target_round":30,"based_on_round":29,"local_generation_sequence":0,\n            "local_generated_at":None,"recommendations":[\n                models.Recommendation(1,"old","old sensor","test",(30,31,32,1,2,3),"r",.5,{}).to_storage()\n            ]\n        }\n        obj._evaluate_prediction_snapshot()\n        assert obj._draw_evaluation["round"]==30\n        assert obj._draw_evaluation["results"][0]["prize"]=="5등"\n''',
)
