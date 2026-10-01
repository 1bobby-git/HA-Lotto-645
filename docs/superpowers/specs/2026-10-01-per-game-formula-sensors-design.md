# 공식별 게임 개별 센서 (per-game formula sensors) 설계

- 날짜: 2026-10-01
- 대상 버전: 2.4.10
- 상태: 사용자 승인됨

## 배경

2.4.7에서 공식별 생성 게임 수(1~10)를 지원하면서 "센서는 공식당 하나만 두고 추가
게임은 `games` 속성으로 노출"하는 방식을 택했습니다. 사용자는 공식당 5개를
생성하면 **해당 공식의 센서를 5개** 두는 방식으로 수정해 달라고 요청했습니다.
바이너리센서(당첨 상세)는 대상이 아닙니다.

## 요구사항 (사용자 확정)

1. 공식당 게임 수만큼 **센서 엔티티**를 만든다. 게임이 5장이면 센서 5개.
2. **1번 게임은 기존 엔티티를 재사용**한다. `unique_id`/`entity_id`/레코드 이력을
   그대로 유지해 기존 자동화·대시보드가 깨지지 않는다. 2~N번 게임만 신규 엔티티.
3. 이름은 5개 모두 동일 패턴: `N번 | {공식 라벨}` (예: `1번 | 빈도 프리셋 · 핫넘버`).
4. **센서 이름에서 리뷰 표시를 제거**한다. `☆평가대기`, `★4.2 · 84.0점` 같은
   접두사를 쓰지 않는다. (리뷰 정보는 로또 페이지 패널과 `local_review` 속성에
   그대로 남는다.)
5. 기존 `games`·`game_count` 속성은 **유지**한다. 공식 전체 요약을 쓰는 템플릿과
   스크립트를 보호하기 위해서다.

## 비요구사항 (손대지 않음)

- 당첨 상세 바이너리센서(`binary_sensor.py`)의 `results` 속성
- 리뷰 원장 "공식당 회차당 1표" 정책과 `_build_prediction_snapshot`의 첫 게임 유지
- 로또 페이지 패널의 `display_name` 별점 표시 (`ticket_panel.py`)
- 게임 수 설정 플로우, 배치 생성·병합 로직, 서비스 계약

## 설계

### 엔티티 생성

`sensor.py::async_setup_entry`가 선택 공식마다 `coordinator.game_count(method_id)`
개의 `LottoGameSensor`를 만든다.

```python
LottoGameSensor(coordinator, method_id, game_no)  # game_no: 1..N
```

| game_no | unique_id | entity_id |
|---|---|---|
| 1 | `{entry_id}_method_{method_id}` (기존 유지) | 레지스트리 기존 값 유지 |
| N≥2 | `{entry_id}_method_{method_id}_g{N}` | HA가 이름 기반으로 신규 생성 |

### 이름 / 아이콘 / state

- `name`: `f"{game_no}번 | {label}"` (`review_name` 호출 제거)
- 구매일치(자기 게임 기준): `f"{game_no}번 | ✓구매일치 | {label}"`
- `icon`: 자기 게임의 구매 일치 여부로 `mdi:ticket-confirmation` / `mdi:numeric`
- `native_value`: 자기 게임의 6개 번호 (쉼표 구분)

`Home Assistant AI 추천` 센서도 `review_name` 호출을 제거해 이름에서 별표시를
없앤다. `✓구매일치` 접두사는 구매 표시이므로 유지한다.

### availability

- 1번: 기존과 동일 (`coordinator.data` 존재 + 해당 공식의 primary 추천 존재)
- N≥2: `recommendations_by_method(method_id)`에 `formula_game == game_no`인 게임이
  실제로 존재할 때만 available. 부족분(shortfall)으로 아직 생성되지 않았으면
  unavailable.

### 속성

각 게임 센서는 다음을 노출한다.

- 자기 게임: `formula_game`, `game_index`, `numbers`, `purchase_match`,
  `purchase_match_count`, `purchase_matches`
- 공식 전체 (기존 유지): `games`, `game_count`, `requested_game_count`,
  `game_count_notice`, `game_shortfall` 관련 값
- 공식 단위 정보 (그대로): `local_review`, `method_category`,
  `method_description`, `target_round`, `based_on_round`, 안내 문구들

### 엔티티 정리 (pruning)

`_active_optional_sensor_unique_ids`가 설정된 게임 수만큼
`{entry_id}_method_{method_id}_g{n}` (n=2..N)을 active set에 포함시킨다.
개수가 줄면 잔여 `_g{n}` 레지스트리 엔티티가 기존 로직과 같이 제거된다.
active set은 **설정값** 기준이지 생성된 게임 수 기준이 아니다 (부족분으로
미생성된 게임도 엔티티는 존재하고 unavailable이다).

### 영속성 영향 없음

- 예측 스냅샷, 리뷰 원장, 구매번호 저장소, 배치 상태 모두 그대로.
- `result_details.decorate_result`의 `recommendation_sensor_unique_id`는 계속
  1번 게임 센서의 unique_id를 가리킨다 (리뷰 원장이 공식당 1장만 담기 때문).

## 테스트 계획

1. 설정한 게임 수만큼 엔티티가 만들어지고 각 state가 자기 게임 번호인지
2. 1번 엔티티의 unique_id가 기존 값을 유지하는지
3. 이름이 `N번 | 라벨` 패턴이고 ☆/★를 포함하지 않는지
4. 개수 감소 시 `_g{n}` 엔티티가 active set에서 빠져 제거 대상이 되는지
5. 부족분으로 미생성 게임 센서가 unavailable인지
6. `games`/`game_count` 속성이 계속 노출되는지
7. 기존 `smoke_ha_options.py`의 `☆평가대기`/`★4.0` 이름 assertion 수정

검증: 전체 pytest + `python -m compileall` + `ruff --select F821`.

## 배포

1. 버전 2.4.10 (manifest.json, const.py, www 스탬프 6곳+판넬 태그 compat 유지)
2. README 2.4.10 릴리스 노트
3. 커밋/푸시 → HACS 릴리스 자동 발행 → Validate 워크플로 수동 실행
4. 릴리스 zip 내용 검증

## 위험

- 신규 엔티티의 entity_id는 HA가 이름(한국어) 기반으로 슬러그화해 생성한다.
  기존 1번 엔티티의 entity_id는 변하지 않는다.
- 공식 라벨이 같아도 공식 id가 다르면 unique_id가 다르므로 충돌하지 않는다.
- `review_name` 함수 자체는 로또 페이지용으로 남으므로 패널 표시는 변하지 않는다.
