# 구매 복권의 공식 표식 강화 (game-level formula provenance) 설계

- 날짜: 2026-10-01
- 대상 버전: 2.4.11
- 상태: 사용자 승인됨 ("둘 다")

## 배경

2.4.10에서 공식당 게임 수만큼 센서를 만들었다. 이제 게임이 1~10장인데, 구매한 복권에
붙는 공식 표식(`formula_links` → 로또 페이지 `적용 공식 · 공식명` 배지)이 두 가지 부족하다.

1. **어느 게임인지 표시되지 않는다.** 링크에 게임 번호가 없어 5장 중 3번째 장을 샀어도
   배지는 `적용 공식 · 핫넘버`로만 보인다. 센서는 이제 `3번 | 핫넘버`로 구분된다.
2. **저장 시점이 아니면 표식이 남지 않는다.** `_purchase_formula_links`는 복권을 저장하는
   순간 현재 분석과 비교하므로, 추첨 후 등록이나 과거 회차 등록에서는 비교 대상이 없다.
   사후 보정(`with_review_formula_links`)은 리뷰 원장 `predictions`(공식당 1장)만 보기
   때문에 2~5장 일치는 연결되지 않는다.

## 요구사항 (사용자 확정)

1. 공식 표식에 **몇 번째 게임인지**를 포함한다. 배지 형식 `적용 공식 · 3번 핫넘버`
   (센서 이름 `3번 | 핫넘버`와 같은 순서).
2. **추첨 후 등록·과거 회차 등록에서도** 2~5장 일치의 표식이 남도록 한다.
3. 리뷰 원장의 **공식당 회차당 1표 원칙은 유지**한다.

## 핵심 결정: 전체 게임 아카이브

리뷰 원장(`review.py`)의 회차 행에 `predictions`(공식당 1장)과 별개로 `games`
(그 회차에 생성된 **전체 게임**)를 보관한다.

- `predictions`는 그대로다 → 리뷰 별점·당첨 판정·당첨 상세 바이너리센서 동작 **무변경**
- `games`는 구매 표식 사후 연결 전용이다
- 저장 시점 비교는 `_purchase_formula_links`(전체 게임 스캔), 사후 연결은
  `with_review_formula_links`(원장 `games` 스캔)가 맡는다

대안과 기각 사유:
- 스냅샷에 전체 게임을 넣어 원장이 1표만 집계 → `_draw_evaluation` 판정 건수가 바뀌는
  부작용 위험
- 저장 시점 비교만 유지 → 요구사항 2 미충족

## 설계

### 1. 링크에 게임 번호

`coordinator._purchase_formula_links`가 링크 dict에 `formula_game`을 넣는다.

`purchased_tickets._formula_link`는 `formula_game`을 **선택 정수(1~1000)** 로 검증해
보존한다. 기존 저장분에 이 필드가 없어도 정상 동작한다(하위 호환).
`_merge_formula_links`/`normalize_formula_links`의 동일성 키에 `formula_game`을 추가해
같은 공식의 서로 다른 장이 합쳐지지 않게 한다.

`PurchaseBook.report`는 게임 행마다 `applied_formula_games`(labels와 같은 순서의 정수
리스트)를 추가한다. 기존 `applied_formula_ids`/`applied_formula_labels`는 그대로 둔다.

### 2. 원장에 전체 게임 보관

- `ReviewBook.record_snapshot(snapshot, now=None, archive_all=False)`
  - `archive_all=True`이면 검증 통과한 모든 게임을 `row['games']`에
    `f"{method_id}#{formula_game}"` 키로 보관한다
  - `predictions`는 **가장 작은 `formula_game` 하나만** 담는다(현재의 첫 게임 규칙과 동일)
  - 게임별 동결 규칙은 기존과 동일: 추첨 마감 전 시각만, 더 오래된 시각은 덮어쓰지 않음
- `ReviewBook.to_storage`/`from_storage`가 `games`를 선택 필드로 저장·복원
  - 파싱에 실패한 개별 행은 **건너뛴다**. `predictions`와 달리 `games`는 부가 데이터라
    손상되어도 원장 전체를 사용 불가로 만들면 안 된다
- `ReviewBook.round_review`/`summary`는 `predictions`만 사용 → 리뷰 1표 유지

`coordinator._build_prediction_snapshot(..., all_games=True)`로 전체 게임 스냅샷을 만들고
`_set_prediction_snapshot`에서 `record_snapshot(archive, archive_all=True)`를 추가 호출한다.
`_prediction_snapshot` 자체는 첫 게임 규칙을 유지한다.

### 3. 사후 연결

`PurchaseBook.with_review_formula_links`가 `predictions` 값과 `games` 값을 함께 스캔해
번호가 6개 모두 같은 링크를 만든다. `games` 행에는 `formula_game`이 있으므로 배지까지
구분된다. 두来源의 링크는 `_merge_formula_links`로 중복 제거된다.

### 4. 표시

- `www/lotto-panel-view.js` 복권 행 배지: `적용 공식 · {label} {N}번`
- `www/lotto-panel-core.js` 지갑 요약 라인: 같은 표기
- `formula_game`이 없는 기존 링크는 번호 없이 기존처럼 표시한다

### 5. 유지하는 하한

- 생성 시각이 확인되지 않은 번호에는 표식을 붙이지 않는다(기존 원칙)
- 2.4.10 이전 회차처럼 `games`가 없는 원장 행은 `predictions`(1장)만 연결된다
- 리뷰 1표, 당첨 판정, 구매번호 저장 형식의 나머지 부분은 그대로

## 테스트 계획

1. 링크에 `formula_game`이 실리고 저장/복원 후에도 유지된다
2. 같은 공식의 1번·3번 장 링크가 합쳐지지 않는다
3. `report()`가 `applied_formula_games`를 labels와 같은 순서로 노출한다
4. `record_snapshot(archive_all=True)`가 `games`에 전체 게임을 담고 `predictions`는 1장이다
5. 리뷰 요약/순위가 `games` 추가로 변하지 않는다(1표 원칙)
6. 저장소가 손상된 `games` 행을 건너뛰고 원장 전체는 정상 복원된다
7. 추첨 후 등록 시나리오: 원장 `games`의 3번 장 일치 → 배지 연결
8. 배지 문자열에 `3번`이 들어간다

검증: 전체 pytest + `compileall` + `ruff --select F821`.

## 배포

버전 2.4.11(manifest/const/www 스탬프/판넬 태그 compat 유지), README 릴리스 노트,
커밋·푸시 → HACS 릴리스 → Validate → 릴리스 zip 검증.

## 위험

- 저장 크기: 회차당 최대 220행(공식 22개 × 10장), 대략 1.5MB/년 누적. 기존 원장은
  회차 전체를 보관하므로 같은 증가 패턴 안이다.
- `games`가 없는 과거 회차는 1장만 연결된다. 없는 정보를 만들어 내지 않는다.
