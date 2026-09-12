from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:180]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# API: manual refresh must bypass an ETag learned by background checks so the
# full newer mirror can still be adopted only when the user asks for it.
path = "custom_components/lotto_645/api.py"
replace_once(
    path,
    '''    async def async_fetch_shared_mirror(\n        self,\n    ) -> tuple[list[LottoDraw] | None, dict[str, Any]]:\n        """Fetch the repository mirror once, supporting conditional ETag requests."""\n        headers = dict(self._headers)\n        if self._mirror_etag:\n            headers["If-None-Match"] = self._mirror_etag\n''',
    '''    async def async_fetch_shared_mirror(\n        self, *, force: bool = False\n    ) -> tuple[list[LottoDraw] | None, dict[str, Any]]:\n        """Fetch the shared mirror; manual refresh may force a complete response."""\n        headers = dict(self._headers)\n        if self._mirror_etag and not force:\n            headers["If-None-Match"] = self._mirror_etag\n''',
)

# Coordinator: only a user-triggered refresh may adopt a newer draw and evaluate
# the saved pre-draw recommendations.
path = "custom_components/lotto_645/coordinator.py"
replace_once(
    path,
    '''        self._prediction_snapshot: dict[str, Any] | None = None\n        self._draw_evaluation: dict[str, Any] | None = None\n        self._manual_lock = asyncio.Lock()\n''',
    '''        self._prediction_snapshot: dict[str, Any] | None = None\n        self._draw_evaluation: dict[str, Any] | None = None\n        self._manual_result_refresh_requested = False\n        self._manual_lock = asyncio.Lock()\n''',
)
replace_once(
    path,
    '''    async def _async_update_data(self) -> Lotto645Data:\n        """Prefer the shared mirror; never crawl official history from HA clients."""\n        if self.data is not None:\n            self._set_prediction_snapshot(\n                self.data.analysis,\n                self.data.ai_recommendation,\n                self.data.ai_generated_at,\n            )\n        elif self._prediction_snapshot is None and self.history:\n''',
    '''    async def _async_update_data(self) -> Lotto645Data:\n        """Refresh data; newer draw adoption is explicitly user-triggered."""\n        manual_result_refresh = self._manual_result_refresh_requested\n        self._manual_result_refresh_requested = False\n        # async_refresh_and_regenerate() captures the exact pre-refresh ticket\n        # snapshot before advancing the generation nonce.  Do not overwrite that\n        # snapshot at the start of the user-triggered result check.\n        if self.data is not None and not manual_result_refresh:\n            self._set_prediction_snapshot(\n                self.data.analysis,\n                self.data.ai_recommendation,\n                self.data.ai_generated_at,\n            )\n        elif self._prediction_snapshot is None and self.history:\n''',
)
replace_once(
    path,
    '''            mirror_history, mirror_meta = await self.client.async_fetch_shared_mirror()\n''',
    '''            mirror_history, mirror_meta = await self.client.async_fetch_shared_mirror(\n                force=manual_result_refresh\n            )\n''',
)
replace_once(
    path,
    '''                mirror_latest = mirror_history[-1].round\n                if not self.history or mirror_latest >= self.history[-1].round:\n                    changed = self._history_changed(self.history, mirror_history)\n                    self.history = mirror_history\n                    source_status = "shared_mirror"\n                    _LOGGER.debug(\n                        "공유 로또 미러 동기화: %s회, updated_at=%s",\n                        mirror_latest,\n                        mirror_meta.get("updated_at"),\n                    )\n                else:\n                    source_status = "cache_ahead_of_mirror"\n''',
    '''                mirror_latest = mirror_history[-1].round\n                cached_latest = self.history[-1].round if self.history else 0\n                if (\n                    self.history\n                    and mirror_latest > cached_latest\n                    and not manual_result_refresh\n                ):\n                    # A newer weekly result may exist remotely, but the user asked\n                    # that draw/result sensors remain unchanged until the refresh\n                    # button is explicitly pressed.  Keep the current coordinator\n                    # payload completely stable.\n                    source_status = (\n                        self.data.source_status if self.data is not None else self._startup_source\n                    )\n                    _LOGGER.debug(\n                        "새 회차 %s는 수동 새로고침 전까지 보류합니다 (현재 %s회)",\n                        mirror_latest,\n                        cached_latest,\n                    )\n                elif not self.history or mirror_latest >= cached_latest:\n                    changed = self._history_changed(self.history, mirror_history)\n                    self.history = mirror_history\n                    source_status = "shared_mirror"\n                    _LOGGER.debug(\n                        "공유 로또 미러 동기화: %s회, updated_at=%s",\n                        mirror_latest,\n                        mirror_meta.get("updated_at"),\n                    )\n                else:\n                    source_status = "cache_ahead_of_mirror"\n''',
)
replace_once(
    path,
    '''        if not mirror_ok and self.allow_official_fallback and self.history:\n''',
    '''        if (\n            manual_result_refresh\n            and not mirror_ok\n            and self.allow_official_fallback\n            and self.history\n        ):\n''',
)
replace_once(
    path,
    '''        if self.history[-1].round != old_latest_round:\n            self._evaluate_prediction_snapshot()\n            self._cached_ai_recommendation = None\n''',
    '''        if self.history[-1].round != old_latest_round:\n            if manual_result_refresh:\n                self._evaluate_prediction_snapshot()\n            self._cached_ai_recommendation = None\n''',
)
replace_once(
    path,
    '''    async def async_refresh_and_regenerate(self) -> None:\n        """Refresh history and rotate all local recommendations, leaving AI untouched."""\n        async with self._manual_lock:\n            previous = tuple(item.numbers for item in self.data.analysis.recommendations) if self.data else ()\n            if self.data and self.data.ai_recommendation:\n                previous += (self.data.ai_recommendation.numbers,)\n            self._regeneration_exclusions = previous\n            self._local_generation_nonce += 1\n''',
    '''    async def async_refresh_and_regenerate(self) -> None:\n        """User-triggered refresh, optional new-draw evaluation, and local regeneration."""\n        async with self._manual_lock:\n            if self.data is not None:\n                # Freeze exactly what the user saw before this refresh.  If a new\n                # draw is obtained by this request, this snapshot is what gets\n                # evaluated before next-round recommendations replace it.\n                self._set_prediction_snapshot(\n                    self.data.analysis,\n                    self.data.ai_recommendation,\n                    self.data.ai_generated_at,\n                )\n            self._manual_result_refresh_requested = True\n            previous = tuple(item.numbers for item in self.data.analysis.recommendations) if self.data else ()\n            if self.data and self.data.ai_recommendation:\n                previous += (self.data.ai_recommendation.numbers,)\n            self._regeneration_exclusions = previous\n            self._local_generation_nonce += 1\n''',
)

# Version.
path = "custom_components/lotto_645/const.py"
replace_once(path, 'VERSION = "1.8.0"\n', 'VERSION = "1.8.1"\n')
path = "custom_components/lotto_645/manifest.json"
replace_once(path, '  "version": "1.8.0"\n', '  "version": "1.8.1"\n')

# Documentation.
path = "CHANGELOG.md"
replace_once(
    path,
    "# Changelog\n\n",
    '''# Changelog\n\n## 1.8.1\n\n- 추첨 결과 판정을 **사용자 수동 새로고침 전용**으로 변경. 이번 주 추첨이 끝났더라도 사용자가 `즉시 새로고침 · 번호 재생성`을 누르지 않으면 `추첨번호`와 `당첨 여부` 센서는 이전 상태를 유지함.\n- 사용자가 새로고침을 눌렀고 그 요청에서 새 회차를 실제로 받아온 경우에만 직전 회차 추천 스냅샷과 새 추첨번호를 대조해 1~5등/미당첨을 판정함.\n- 일반 6시간 coordinator 확인은 원격 미러에 새 회차가 있어도 채택하지 않으며 센서 상태를 갱신하지 않음.\n- 수동 새로고침은 ETag를 강제로 우회해 최신 공유 미러 전체를 확인하므로, 백그라운드 확인이 먼저 새 미러의 ETag를 보았더라도 사용자가 버튼을 누르면 새 회차를 정상 수신할 수 있음.\n- 동행복권 직접 증분 폴백도 수동 새로고침 요청에서만 허용하며 기존 기본 OFF/저빈도/요청 제한 정책은 유지.\n\n''',
)
path = "README.md"
replace_once(
    path,
    "## v1.8.0 · 추첨번호 및 자동 당첨 판정\n",
    "## v1.8.1 · 수동 새로고침 기반 추첨번호·당첨 판정\n\n> **중요:** 추첨이 끝났다는 이유만으로 센서를 자동 갱신하지 않습니다. `즉시 새로고침 · 번호 재생성`을 누른 요청에서 새 회차를 받아온 경우에만 `추첨번호`와 `당첨 여부`가 갱신됩니다. 새로고침하지 않았다면 이번 주 추첨 이후에도 이전 상태를 유지합니다.\n\n## v1.8.0 · 추첨번호 및 자동 당첨 판정\n",
)

# Tests: ensure the API exposes the force path and code keeps the manual gate.
path = "tests/test_result_evaluator.py"
with Path(path).open("a", encoding="utf-8") as fp:
    fp.write('''\n\ndef test_manual_refresh_contract_is_explicit_in_source():\n    root = __import__("pathlib").Path(__file__).resolve().parents[1]\n    coordinator = (root / "custom_components/lotto_645/coordinator.py").read_text(encoding="utf-8")\n    api = (root / "custom_components/lotto_645/api.py").read_text(encoding="utf-8")\n    assert "self._manual_result_refresh_requested = True" in coordinator\n    assert "and not manual_result_refresh" in coordinator\n    assert "force=manual_result_refresh" in coordinator\n    assert "force: bool = False" in api\n''')
