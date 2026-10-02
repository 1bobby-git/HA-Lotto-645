# 생성 번호 복권 등록 버튼 설계

- 날짜: 2026-10-01
- 대상 버전: 2.4.12
- 상태: 사용자 승인됨

## 배경

생성한 공식 번호를 그대로 산 경우, 그 번호를 `내 복권`에 손으로 옮겨 적는 과정이 있다.
2.4.11에서 공식 표식(게임 번호 포함)을 붙였으므로, 이제 **버튼 한 번으로 등록**해
표식까지 자동으로 붙게 만들면 흐름이 이어진다.

## 요구사항 (사용자 확정)

1. **게임 센서마다** `이 번호로 복권 등록` 버튼을 만든다.
2. **공식마다** `이 공식 전체 복권 등록` 버튼을 하나 더 만든다.
3. 엔티티 수를 줄이지 않는다(공식 22개 × 게임 10장 = 최대 220개 게임 버튼 + 22개 공식 버튼).
4. 등록 위치는 **빈 A~E 슬롯 자동 배정**. 꽉 차면 새 복권(티켓)을 만들어 이어 붙인다.

## 설계

### 버튼 엔티티 (`button.py`)

| 엔티티 | 이름 | unique_id | 대상 |
|---|---|---|---|
| `LottoGamePurchaseButton` | `{game_entity_name} 복권 등록` | `{entry}_method_{mid}_g{N}_register` (1번은 `_register`) | 그 게임 1장 |
| `LottoFormulaPurchaseButton` | `{label} 전체 복권 등록` | `{entry}_method_{mid}_register_all` | 그 공식의 모든 생성 게임 |

- 아이콘: 게임 `mdi:ticket-plus`, 공식 `mdi:ticket-confirmation`
- `available`: 해당 게임이 실제로 생성됐을 때만. 부족분으로 미생성된 게임 버튼은 unavailable
- 공식 버튼: 생성된 게임이 0개면 unavailable
- `async_press` → `coordinator.async_register_generated_purchase(method_id, game_no)`
  → 결과 dict로 `persistent_notification` 표시(버튼이 UI 책임 담당)

### 등록 동작 (`coordinator.async_register_generated_purchase`)

1. `purchase_storage_error` / `data is None` / 미생성 게임이면 `HomeAssistantError`
2. 등록 회차는 `analysis.target_round` (생성 회차와 복권 회차가 어긋나지 않게 고정)
3. `_purchase_lock`을 **한 번만** 잡고:
   - 이미 등록된 6개 번호는 **건너뛴다**(중복 등록 방지)
   - 현재 회차의 선택된 티켓을 찾아 빈 슬롯부터 채운다
   - 남은 게임은 새 티켓으로 넘긴다(티켓당 최대 5장)
4. `_async_write_purchase()`(신규 내부 헬퍼)로 저장 → `_purchase_formula_links`가 공식 표식을 자동 부착
5. 반환값: `{'round', 'registered': [{slot, ticket_id, formula_game, numbers}], 'skipped': [formula_game], 'created_tickets': n}`

### 저장 경로 리팩터

`async_save_purchase_record`가 락·개정 확인 후 저장하는 부분을 `_async_write_purchase`로
추출한다. 기존 웹소켓 저장 경로는 그대로 재사용하므로 회귀 위험이 없다.

### 정리 규칙

`button.py`에 `_prune_stale_purchase_buttons`를 추가한다. 게임/공식 선택 해제 시
레지스트리에서 해당 버튼을 제거한다(sensor pruning과 같은 패턴, `button` 도메인).

### 유지하는 하한

- 생성 시각이 없는 번호에는 표식이 붙지 않는다(2.4.11 원칙 그대로)
- 중복 번호는 등록하지 않고 알린다
- 저장 실패 시 기존 구매기록은 그대로 유지된다(현재 저장 경로와 동일)
- 리뷰 원장·당첨 판정·공식 표식 규칙은 변경하지 않는다

## 테스트 계획

1. 빈 슬롯 자동 배정, 티켓이 꽉 차면 새 티켓 생성
2. 공식 전체 버튼이 여러 게임을 연속 배치
3. 이미 등록된 번호는 건너뛰고 결과에 남음
4. 등록 후 해당 게임의 공식 표식(게임 번호 포함)이 붙음
5. 미생성 게임 버튼은 unavailable, `async_press`는 오류
6. 공식/게임 선택 해제 시 버튼이 정리 대상
7. 저장 실패·개정 충돌 시 기존 번호 유지

검증: 전체 pytest + `compileall` + `ruff --select F821` + `node --check` (패널 JS 무변경 확인).

## 배포

버전 2.4.12(manifest/const/www 스탬프/판넬 태그 compat 유지), README 릴리스 노트,
커밋·푸시 → HACS 릴리스 → Validate → 릴리스 zip 검증.
