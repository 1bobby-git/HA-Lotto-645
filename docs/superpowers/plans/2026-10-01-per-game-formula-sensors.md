# 공식별 게임 개별 센서 (per-game formula sensors) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 공식에 설정된 게임 수(1~10)만큼 **별도 센서 엔티티**를 만들고, 이름에서 리뷰 별표시(☆/★)를 제거한다.

**Architecture:** `game_entities.py` (Home Assistant 비의존)에 unique_id/이름 규칙을 두고, `sensor.py`가 설정된 게임 수만큼 `LottoGameSensor(coordinator, method_id, game_no)`를 생성한다. 1번 게임은 기존 unique_id를 그대로 재사용해 entity_id·이력·자동화를 보호하고, 2~N번은 `_g{N}` suffix로 신규 엔티티를 만든다. 리뷰 원장(공식당 1표)과 예측 스냅샷은 손대지 않는다.

**Tech Stack:** Python 3.14 / Home Assistant custom component / pytest (Home Assistant 미설존 환경: 소스 텍스트·AST 검증 + HA 비의존 모듈 직접 import)

**Spec:** `docs/superpowers/specs/2026-10-01-per-game-formula-sensors-design.md`

---

### Task 1: HA 비의존 게임 엔티티 헬퍼

**Files:**
- Create: `custom_components/lotto_645/game_entities.py`
- Test: `tests/test_game_entities.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_game_entities.py`:

```python
"""Per-game formula sensor identity and naming (does not import Home Assistant)."""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
PACKAGE = 'lotto_game_entities_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
entities = __import__(PACKAGE + '.game_entities', fromlist=['game_entities'])


def test_first_game_keeps_the_legacy_unique_id():
    assert entities.game_unique_id('entry', 'hot_numbers', 1) == 'entry_method_hot_numbers'


def test_extra_games_use_a_stable_suffix():
    assert entities.game_unique_id('entry', 'hot_numbers', 2) == 'entry_method_hot_numbers_g2'
    assert entities.game_unique_id('entry', 'hot_numbers', 10) == 'entry_method_hot_numbers_g10'


def test_configured_count_lists_every_sensor_identity():
    assert entities.game_unique_ids('entry', 'hot_numbers', 3) == {
        'entry_method_hot_numbers',
        'entry_method_hot_numbers_g2',
        'entry_method_hot_numbers_g3',
    }


def test_a_count_below_one_still_keeps_the_primary_sensor():
    assert entities.game_unique_ids('entry', 'hot_numbers', 0) == {'entry_method_hot_numbers'}


def test_names_carry_the_game_number_without_review_stars():
    plain = entities.game_entity_name(1, '빈도 프리셋 · 핫넘버')
    assert plain == '1번 | 빈도 프리셋 · 핫넘버'
    assert '☆' not in plain and '★' not in plain
    bought = entities.game_entity_name(5, '빈도 프리셋 · 핫넘버', purchased=True)
    assert bought == '5번 | ✓구매일치 | 빈도 프리셋 · 핫넘버'
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_game_entities.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named '...game_entities'`)

- [ ] **Step 3: 구현**

`custom_components/lotto_645/game_entities.py`:

```python
"""Registry identity and display names for per-game formula sensors.

Kept free of Home Assistant imports so the naming rules are unit testable.
"""
from __future__ import annotations


def game_unique_id(entry_id: str, method_id: str, game_no: int = 1) -> str:
    """Game 1 keeps the pre-2.4.10 unique_id so existing entities survive."""
    suffix = '' if game_no <= 1 else f'_g{game_no}'
    return f'{entry_id}_method_{method_id}{suffix}'


def game_unique_ids(entry_id: str, method_id: str, count: int) -> set[str]:
    """Every sensor identity a configured game count must keep registered."""
    total = max(1, int(count))
    return {game_unique_id(entry_id, method_id, n) for n in range(1, total + 1)}


def game_entity_name(game_no: int, label: str, *, purchased: bool = False) -> str:
    """`N번 | 라벨` — the review stars stay on the Lotto page, not in entity names."""
    prefix = f'{game_no}번 | '
    return f'{prefix}✓구매일치 | {label}' if purchased else f'{prefix}{label}'
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_game_entities.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add custom_components/lotto_645/game_entities.py tests/test_game_entities.py
git commit -m "feat: 게임별 센서 identity/이름 헬퍼 추가"
```

---

### Task 2: sensor.py — 게임 수만큼 엔티티 생성 + 이름 교체

**Files:**
- Modify: `custom_components/lotto_645/sensor.py` (`async_setup_entry` ~122-147, `LottoGameSensor` 324-433, `LottoAiRecommendationSensor.name` 447-454)
- Test: `tests/test_game_entities.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_game_entities.py` 파일 끝에 추가:

```python
def test_sensor_module_builds_one_entity_per_configured_game_and_names_it_without_stars():
    source = (BASE / 'sensor.py').read_text(encoding='utf-8')
    assert 'for game_no in range(1, coordinator.game_count(method_id) + 1)' in source
    assert 'LottoGameSensor(coordinator, method_id, game_no)' in source
    assert 'game_unique_id(coordinator.entry.entry_id, method_id, game_no)' in source
    assert 'game_entity_name(self.game_no, label, purchased=bool(matches))' in source
    assert 'review_name(' not in source
    assert 'from .review import review_name' not in source
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_game_entities.py -q`
Expected: FAIL (위 assert 중 최소 하나가 실패)

- [ ] **Step 3: import 수정**

`custom_components/lotto_645/sensor.py`의 import 블록에서:

```python
from .methods import METHOD_MYUNGRI_HETU, METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE, METHODS_BY_ID, method_catalog
```

다음 줄을 추가하고,

```python
from .game_entities import game_entity_name, game_unique_id, game_unique_ids
```

```python
from .review import review_name, NOTICE as REVIEW_NOTICE
```

를

```python
from .review import NOTICE as REVIEW_NOTICE
```

로 교체한다.

- [ ] **Step 4: `async_setup_entry`가 게임 수만큼 엔티티를 만들도록 수정**

기존:

```python
    entities.extend(
        LottoGameSensor(coordinator, method_id)
        for method_id in coordinator.selected_method_ids
    )
```

교체:

```python
    entities.extend(
        LottoGameSensor(coordinator, method_id, game_no)
        for method_id in coordinator.selected_method_ids
        for game_no in range(1, coordinator.game_count(method_id) + 1)
    )
```

- [ ] **Step 5: `LottoGameSensor` docstring/`__init__`/접근자 교체**

기존 클래스 docstring(324-340행 주석 포함)을 다음으로 교체:

```python
class LottoGameSensor(Lotto645Entity, SensorEntity):
    """One generated game of one selected method.

    Game 1 keeps the pre-2.4.10 unique_id and state so existing dashboards and
    automations keep working. Every further configured game is its own entity
    with its own state; the formula-wide list stays in the `games` attribute.
    """
```

`__init__` 교체:

```python
    def __init__(self, coordinator: Lotto645Coordinator, method_id: str, game_no: int = 1) -> None:
        super().__init__(coordinator)
        self.method_id = method_id
        self.game_no = game_no
        method = METHODS_BY_ID[method_id]
        self._attr_name = game_entity_name(game_no, method.label)
        self._attr_unique_id = game_unique_id(coordinator.entry.entry_id, method_id, game_no)

    @property
    def _own_recommendation(self):
        """The single game this entity reports; None until that game exists."""
        if self.coordinator.data is None:
            return None
        for recommendation in self.coordinator.data.analysis.recommendations_by_method(self.method_id):
            if recommendation.formula_game == self.game_no:
                return recommendation
        return None
```

`name` property 교체:

```python
    @property
    def name(self) -> str:
        label = METHODS_BY_ID[self.method_id].label
        matches = _purchase_matches(self.coordinator, self._own_recommendation)
        return game_entity_name(self.game_no, label, purchased=bool(matches))
```

`icon` property 교체:

```python
    @property
    def icon(self) -> str:
        if _purchase_matches(self.coordinator, self._own_recommendation):
            return "mdi:ticket-confirmation"
        return "mdi:numeric"
```

`available` property 교체:

```python
    @property
    def available(self) -> bool:
        return super().available and self._own_recommendation is not None
```

`native_value` property 교체:

```python
    @property
    def native_value(self) -> str | None:
        recommendation = self._own_recommendation
        if recommendation is None:
            return None
        return ", ".join(str(number) for number in recommendation.numbers)
```

- [ ] **Step 6: `extra_state_attributes`를 자기 게임 기준으로 수정**

`extra_state_attributes`에서:

```python
        data = self.coordinator.data
        recommendation = data.analysis.recommendation_by_method(self.method_id)
```

를

```python
        data = self.coordinator.data
        recommendation = self._own_recommendation
```

로 교체하고, 반환 dict에서 `matches`를 자기 게임 기준으로 바꾼다:

```python
        method = METHODS_BY_ID[self.method_id]
        games = _formula_games(self.coordinator, self.method_id)
        matches = _purchase_matches(self.coordinator, recommendation)
        requested = self.coordinator.game_count(self.method_id)
        return {
            **recommendation.as_attributes(),
            "game_no": self.game_no,
            "game_count": len(games),
            "requested_game_count": requested,
            "games": _game_attributes(self.coordinator, games),
            "game_count_notice": (
                f"이 엔티티는 {method.label} 공식의 {self.game_no}번째 게임입니다. "
                "공식당 요청한 장수만큼 게임이 각각 별도 센서로 노출되며, numbers는 "
                "그 게임의 6개 번호입니다. games 속성에는 같은 공식의 전체 게임이 "
                "남습니다. 어느 공식도 당첨 확률을 바꾸지 않습니다."
            ),
            "purchase_match": bool(matches),
            "purchase_match_count": len(matches),
            "purchase_matches": matches,
            "purchase_match_notice": (
                "이 게임의 6개 번호가 같은 회차에 저장한 구매번호와 모두 같은 경우입니다. "
                "실제 구매 사실을 인증하는 값은 아닙니다."
            ),
            ...
```

(뒤의 `local_review` 이하 항목은 그대로 둔다.)

- [ ] **Step 7: AI 센서 이름에서 리뷰 표시 제거**

`LottoAiRecommendationSensor.name` 교체:

```python
    @property
    def name(self) -> str:
        data = self.coordinator.data
        matched = bool(_purchase_matches(self.coordinator, data.ai_recommendation))
        return f"✓구매일치 | {self._attr_name}" if matched else self._attr_name
```

- [ ] **Step 8: 사용하지 않은 헬퍼 제거**

`_all_purchase_matches`(sensor.py 71-77행)는 어디에서도 쓰이지 않으므로 제거한다.

- [ ] **Step 9: 테스트 통과 확인**

Run: `python -m pytest tests/test_game_entities.py -q`
Expected: PASS

- [ ] **Step 10: 컴파일 확인**

Run: `python -m compileall -q custom_components/lotto_645`
Expected: 오류 없음

- [ ] **Step 11: 커밋**

```bash
git add custom_components/lotto_645/sensor.py tests/test_game_entities.py
git commit -m "feat: 공식당 게임 수만큼 센서 엔티티 생성 및 리뷰 별표시 제거"
```

---

### Task 3: 개수 변경 시 엔티티 정리(pruning)와 안내 문구

**Files:**
- Modify: `custom_components/lotto_645/sensor.py:80-91` (`_active_optional_sensor_unique_ids`), `:176-182` (추천 요약 how_to_view), `:259-263` (공식 안내 usage)
- Modify: `tests/test_panel_live_payload.py:127-142`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_panel_live_payload.py`의 `test_pruner_keeps_guide_and_active_formula_but_removes_deselected`를 다음으로 교체하고, 파일 상단 import에 `import game_entities` 패키지 로드(다른 테스트와 동일한 synthetic package 패턴)를 추가한다:

```python
def test_pruner_keeps_guide_and_active_formula_but_removes_deselected():
    source=ast.parse((ROOT/'custom_components/lotto_645/sensor.py').read_text(encoding="utf-8"))
    keep={'_active_optional_sensor_unique_ids','_prune_stale_optional_sensor_entities'}
    nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in keep]
    entries=[SimpleNamespace(domain='sensor',platform='lotto_645',unique_id='entry_'+name,entity_id=name)
             for name in ['method_guide','method_uniform_fisher_yates','method_uniform_fisher_yates_g2',
                          'method_uniform_fisher_yates_g3','method_personal_lucky','recommendations']]
    entries.append(SimpleNamespace(domain='sensor',platform='other',unique_id='entry_method_other',entity_id='other'))
    registry=SimpleNamespace(async_remove=Mock())
    er=SimpleNamespace(async_get=lambda h:registry,async_entries_for_config_entry=lambda r,e:entries)
    env={'Lotto645Coordinator':object,'HomeAssistant':object,'ConfigEntry':object,'er':er,'DOMAIN':'lotto_645',
         'METHOD_MYUNGRI_HETU':'myungri_hetu_day_pillar','game_unique_ids':game_entities.game_unique_ids}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'sensor','exec'),env)
    entry=SimpleNamespace(entry_id='entry')
    owner=SimpleNamespace(entry=entry,selected_method_ids=['uniform_fisher_yates'],
                          configured_method_ids=['uniform_fisher_yates'],ai_enabled=False,
                          game_count=lambda method_id:3)
    env['_prune_stale_optional_sensor_entities'](object(),entry,owner)
    registry.async_remove.assert_called_once_with('method_personal_lucky')

def test_pruner_removes_extra_game_sensors_when_the_count_drops():
    source=ast.parse((ROOT/'custom_components/lotto_645/sensor.py').read_text(encoding="utf-8"))
    keep={'_active_optional_sensor_unique_ids','_prune_stale_optional_sensor_entities'}
    nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in keep]
    entries=[SimpleNamespace(domain='sensor',platform='lotto_645',unique_id='entry_'+name,entity_id=name)
             for name in ['method_uniform_fisher_yates','method_uniform_fisher_yates_g2',
                          'method_uniform_fisher_yates_g3']]
    registry=SimpleNamespace(async_remove=Mock())
    er=SimpleNamespace(async_get=lambda h:registry,async_entries_for_config_entry=lambda r,e:entries)
    env={'Lotto645Coordinator':object,'HomeAssistant':object,'ConfigEntry':object,'er':er,'DOMAIN':'lotto_645',
         'METHOD_MYUNGRI_HETU':'myungri_hetu_day_pillar','game_unique_ids':game_entities.game_unique_ids}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'sensor','exec'),env)
    entry=SimpleNamespace(entry_id='entry')
    owner=SimpleNamespace(entry=entry,selected_method_ids=['uniform_fisher_yates'],
                          configured_method_ids=['uniform_fisher_yates'],ai_enabled=False,
                          game_count=lambda method_id:1)
    env['_prune_stale_optional_sensor_entities'](object(),entry,owner)
    removed={call.args[0] for call in registry.async_remove.call_args_list}
    assert removed == {'method_uniform_fisher_yates_g2','method_uniform_fisher_yates_g3'}
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_panel_live_payload.py -q`
Expected: FAIL (`NameError: game_count` 또는 `game_unique_ids`)

- [ ] **Step 3: `_active_optional_sensor_unique_ids` 구현**

기존:

```python
    entry_id = coordinator.entry.entry_id
    active = {
        f"{entry_id}_method_{method_id}"
        for method_id in coordinator.selected_method_ids
    }
```

교체:

```python
    entry_id = coordinator.entry.entry_id
    active = set()
    for method_id in coordinator.selected_method_ids:
        active |= game_unique_ids(entry_id, method_id, coordinator.game_count(method_id))
```

(docstring의 "Only this integration's optional sensor identities are touched" 문장은 그대로 유지한다.)

- [ ] **Step 4: 안내 문구 갱신**

`LottoRecommendationsSensor.extra_state_attributes["how_to_view"]`:

```python
            "how_to_view": (
                "각 공식은 게임 수만큼 별도 센서(1번 | 공식명, 2번 | 공식명, ...)로 노출되며 "
                "각 센서의 state가 그 게임의 6개 번호입니다. games 속성에는 같은 공식의 "
                "전체 게임이 함께 담깁니다. 실제 결과는 n회 추첨번호·당첨 여부, 직접 입력한 "
                "구매번호는 내 구매번호 센서에서 확인하세요."
            ),
```

`LottoMethodGuideSensor.extra_state_attributes["usage"]`:

```python
            "usage": (
                "통합 구성에서 여러 공식을 동시에 선택할 수 있습니다. 구성 > 추첨 공식의 "
                "'공식별 생성 게임 수'에서 공식마다 1~10장을 요청하면 요청한 장수만큼 "
                "센서가 만들어지고, 한 공식의 전체 게임은 각 센서의 games 속성에서도 확인할 수 있습니다."
            ),
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_panel_live_payload.py tests/test_game_entities.py -q`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add custom_components/lotto_645/sensor.py tests/test_panel_live_payload.py
git commit -m "feat: 게임 수 변경 시 추가 게임 센서 등록정보 정리 및 안내 문구 갱신"
```

---

### Task 4: 기존 테스트·스크립트의 이름 assertion 수정

**Files:**
- Modify: `tests/test_frontend_delivery.py:55-60`
- Modify: `scripts/smoke_ha_options.py:332-335`

- [ ] **Step 1: `test_frontend_delivery` 구매일치 마커 검사 수정**

```python
def test_native_formula_entities_expose_purchase_match_marker():
    sensor = (R / 'sensor.py').read_text(encoding='utf-8')
    entities = (R / 'game_entities.py').read_text(encoding='utf-8')
    assert sensor.count('✓구매일치 |') + entities.count('✓구매일치 |') == 2
    assert sensor.count('mdi:ticket-confirmation') >= 2
    assert '"purchase_match": bool(matches)' in sensor
    assert '"purchase_matches": matches' in sensor
```

- [ ] **Step 2: `smoke_ha_options` 이름 assertion 수정**

```python
        game_sensor=sensor_module.LottoGameSensor(obj,'weighted_frequency')
        assert game_sensor.name == '1번 | 가중 빈도'
        obj._review_summaries['weighted_frequency']={'mean_score':80.,'stars':4.,'reviewed_rounds':1}
        assert game_sensor.name == '1번 | 가중 빈도'
```

(실제 공식 라벨은 파일 상의 `weighted_frequency` 라벨과 일치해야 한다. 라벨 확인 후 하드코딩 대신
`'1번 | ' == game_sensor.name[:5]` 형태로 검사해도 된다.)

- [ ] **Step 3: 테스트 통과 확인**

Run: `python -m pytest tests/test_frontend_delivery.py -q`
Expected: PASS

- [ ] **Step 4: 커밋**

```bash
git add tests/test_frontend_delivery.py scripts/smoke_ha_options.py
git commit -m "test: 게임별 센서 이름 규칙에 맞춰 assertion 갱신"
```

---

### Task 5: 문서와 모델 주석 갱신

**Files:**
- Modify: `custom_components/lotto_645/models.py:92-93`
- Modify: `README.md:60-66` (2.4.7 섹션)

- [ ] **Step 1: `models.py` 주석 갱신**

기존:

```python
    # One to N inside a single formula. The first game stays the entity state;
    # the extra games are attributes of the same formula entity.
```

교체:

```python
    # One to N inside a single formula. Every game is its own sensor entity;
    # formula_game is the 1-based slot this entity reports.
```

- [ ] **Step 2: README 2.4.7 섹션 문장 갱신**

`README.md`의 `## 2.4.7 공식별 생성 게임 수` 섹션에서 "같은 센서의 `games` 속성"으로 설명된 문장을
"공식당 게임 수만큼 별도 센서(`N번 | 공식명`)"로 교체하고, `games` 속성이 공식 전체 요약으로 남는다고 명시한다.
`✓구매일치` 문장은 "게임 센서마다 자기 게임이 일치할 때 표시된다"로 교체한다.

- [ ] **Step 3: 컴파일 확인**

Run: `python -m compileall -q custom_components/lotto_645`
Expected: 오류 없음

- [ ] **Step 4: 커밋**

```bash
git add custom_components/lotto_645/models.py README.md
git commit -m "docs: 게임별 센서 구조로 문구 갱신"
```

---

### Task 6: 전체 검증

- [ ] **Step 1: 전체 테스트 실행**

Run: `python -m pytest -q`
Expected: 모든 테스트 PASS (현재 376 + 신규)

- [ ] **Step 2: 문법·미정의 참조 검사**

```bash
python -m compileall -q custom_components/lotto_645
python -m ruff check --select F821 custom_components/lotto_645 tests
```
Expected: 오류 없음

---

### Task 7: 2.4.10 버전 상승과 릴리스 노트

**Files:**
- Modify: `custom_components/lotto_645/manifest.json`, `custom_components/lotto_645/const.py`
- Modify: `custom_components/lotto_645/www/*.js` (버전 스탬프), `custom_components/lotto_645/ticket_panel.py`
- Modify: `tests/test_managed_connection.py:333-350` (허용 태그)
- Modify: `README.md` (신규 섹션)

- [ ] **Step 1: 버전 문자열 위치 확인**

Run: `git grep -n "2\.4\.9" -- .`
Expected: manifest.json, const.py, www/*.js, ticket_panel.py, README.md, tests/test_managed_connection.py

- [ ] **Step 2: `2.4.9` → `2.4.10`, `2-4-9` → `2-4-10` 일괄 교체**

이전 태그는 `COMPATIBLE_PANEL_TAGS`에 리터럴로 남겨야 한다 (기존 설치 보호). 새 태그를 추가하고
가장 오래된 태그만 제거한다.

- [ ] **Step 3: README 최상단에 2.4.10 섹션 추가**

```markdown
## 2.4.10 공식별 게임 개별 센서

공식에 설정한 게임 수(1~10)만큼 **별도 센서**가 만들어집니다. 이름은 `1번 | 공식명`,
`2번 | 공식명` 형식이며, 각 센서의 state가 그 게임의 6개 번호입니다.
- 1번 게임은 기존 센서의 entity_id·이력을 그대로 사용하므로 기존 자동화·대시보드가 깨지지 않습니다.
- 센서 이름의 리뷰 표시(☆평가대기, ★점수)는 제거했습니다. 리뷰는 로또 페이지와 `local_review` 속성에서 확인하세요.
- `games`·`game_count` 속성은 그대로 남아 한 공식의 전체 게임을 템플릿에서 읽을 수 있습니다.
- 리뷰 원장은 공식당 회차당 1표 원칙을 유지합니다.
```

- [ ] **Step 4: 검증**

```bash
python -m pytest tests/test_frontend_delivery.py tests/test_managed_connection.py -q
python -m compileall -q custom_components/lotto_645
```
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add -A
git commit -m "feat: 공식별 게임 개별 센서 및 2.4.10 릴리스"
```

---

### Task 8: 푸시와 릴리스

- [ ] **Step 1: 상태 확인 후 푸시**

```bash
git status
git log --oneline -8
git push origin main
```

- [ ] **Step 2: HACS 릴리스 대기 및 확인**

```bash
gh release list --limit 3
gh release view v2.4.10 --json name,tagName,assets --jq '.tagName, .assets[].name'
```

- [ ] **Step 3: Validate 워크플로 수동 실행**

```bash
gh workflow run validate.yml
# 잠시 후
gh run list --workflow=validate.yml --limit 2
gh run watch <run-id>
```
Expected: `public-adapter`와 `hassfest` 모두 success

- [ ] **Step 4: 릴리스 zip 내용 검증**

릴리스 자산 zip을 받아 `custom_components/lotto_645/` 8개 항목과 `game_entities.py` 포함 여부 확인.

---

## Self-Review

1. **Spec coverage:** 엔티티 생성(Task 2), unique_id/이름(Task 1-2), availability(Task 2 Step 5), 속성(Task 2 Step 6), pruning(Task 3), 손대지 않는 것(전체), 테스트(Task 1-4, 6), 배포(Task 7-8) — 모두 커버. AI 센서 이름(스펙 "이름/아이콘" 항목)은 Task 2 Step 7.
2. **Placeholder scan:** TBD/TODO 없음. Step마다 명령·기대 결과·코드 명시.
3. **Type consistency:** `game_unique_id(entry_id, method_id, game_no)` / `game_unique_ids(entry_id, method_id, count)` / `game_entity_name(game_no, label, purchased=False)` 는 모든 Task에서 동일 시그니처. `LottoGameSensor(coordinator, method_id, game_no=1)` 도 Task 2/3/4에서 일치.
