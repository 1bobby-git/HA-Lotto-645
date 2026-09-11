# HA-Lotto-645

Home Assistant용 **로또 6/45 전체 회차 분석 및 5게임 추천** 커스텀 통합입니다.

> 이 통합의 추천은 과거 데이터에서 특징을 추출하는 휴리스틱입니다. 로또 추첨은 독립적인 무작위 사건이며, 어떤 분석도 1등 당첨 확률을 실제로 높이거나 당첨을 보장하지 않습니다. 모든 6개 조합의 1등 확률은 동일하게 **1 / 8,145,060**입니다.

## 주요 기능

- 동행복권 **1회부터 최신 확정 회차까지** 당첨번호 6개를 동기화
- 2026년 개편된 동행복권 결과 JSON 표면 사용
- 최초 전체 동기화 후 Home Assistant 저장소에 캐시하고, 이후 **새 회차만 증분 동기화**
- 최신 회차가 바뀌지 않으면 추천 번호도 바뀌지 않는 **결정적 분석**
- 과거 1등 6개 본번호와 완전히 동일한 조합 자동 제외
- 보너스 번호는 추천 조합에 사용하지 않음
- 독창 패턴 2게임 + 별도 구조 휴리스틱 3게임 = 총 5게임
- 각 게임별 핵심 근거, 분석 점수, 강한 번호쌍, 미출현 간격, 과거 최대 일치 개수 제공
- 6시간 간격 자동 확인 + 즉시 새로고침 버튼 + `lotto_645.refresh` 서비스
- Config Flow / HACS 구조 지원

## 분석 방식

단순히 빈출수, 홀짝 비율, 번호대 합계만으로 번호를 고르지 않습니다. 다음 특징을 함께 계산합니다.

1. **장기-단기 잔차 위상**
   - 전체, 최근 260회, 120회, 30회의 출현 횟수를 이론적 기대값 대비 표준화합니다.
   - 장기 방향과 최근 변화 방향이 충돌하는 `counter phase`와 시간축의 변화량/곡률을 계산합니다.
2. **다음 회차 전이 점수**
   - 최신 당첨번호 각각이 과거에 등장한 뒤 다음 회차에서 어떤 번호가 나타났는지를 표준화해 결합합니다.
3. **번호쌍 그래프**
   - 45개 번호의 모든 990개 쌍에 대해 전체 회차 + 최근 120회의 동시출현 잔차를 계산해 그래프 결속도로 사용합니다.
4. **미출현 간격 위상**
   - 현재 미출현 간격을 이론적 기댓값과 비교해 극단/균형 상태를 서로 다른 프로필에 반영합니다.
5. **과거 조합 거리**
   - 과거 1등 완전 동일 조합은 제거하고, 반복되는 4개/5개 코어와 최신 회차 과도 중복에 감점을 줍니다.
6. **게임 간 다양성**
   - 5게임이 거의 같은 숫자로 반복되지 않도록 게임 간 중복 개수를 제한합니다.

### 5개 추천 프로필

| 게임 | 방식 | 핵심 |
|---|---|---|
| 1 | 위상-잔차 그래프 | 장·단기 방향 반전 + 전이 + 쌍 그래프 |
| 2 | 전이-간격 위상 | 시간축 곡률 + 간격 + 다음 회차 전이 |
| 3 | 구조 수렴 휴리스틱 | 전이·그래프·간격이 동시에 수렴하는 번호 |
| 4 | 쌍 그래프 결속 | 전체+최근 번호쌍 연결 강도 중심 |
| 5 | 시간축 균형 휴리스틱 | 장기·최근 잔차 극단을 줄이고 구조 균형 우선 |

## 설치

### HACS 사용자 저장소

1. HACS → Integrations → Custom repositories
2. `https://github.com/1bobby-git/HA-Lotto-645` 추가
3. Category: Integration
4. 설치 후 Home Assistant 재시작
5. 설정 → 기기 및 서비스 → 통합 구성 요소 추가 → **Lotto 6/45 Analysis**

### 수동 설치

`custom_components/lotto_645` 폴더를 HA의 `/config/custom_components/lotto_645`에 복사한 뒤 재시작합니다.

## 생성되는 엔티티

- `sensor.lotto_6_45_analysis_추천_요약`
- `sensor.lotto_6_45_analysis_추천_게임_1` ~ `추천_게임_5`
- `sensor.lotto_6_45_analysis_최신_당첨_결과`
- `button.lotto_6_45_analysis_즉시_새로고침`

실제 entity_id는 Home Assistant의 엔티티 명명/언어 설정에 따라 달라질 수 있으므로 엔티티 레지스트리에서 확인하세요.

### 게임 센서 속성 예시

```yaml
state: "1, 17, 28, 32, 33, 40"
numbers: [1, 17, 28, 32, 33, 40]
label: "독창 패턴 ①"
method: "위상-잔차 그래프"
core_reason: "장·단기 잔차의 방향 변화가 큰 ..."
analysis_score: 0.7421
strongest_pair: [33, 40]
strongest_pair_score: 0.5132
gaps_since_last:
  "1": 4
  "17": 8
exact_past_first_prize_match: false
max_numbers_matching_any_past_first_prize: 4
latest_draw_overlap: 1
target_round: 1241
based_on_round: 1240
first_prize_odds: "1/8,145,060"
```

## Lovelace 예시

```yaml
type: entities
title: 로또 6/45 추천
entities:
  - entity: sensor.lotto_6_45_analysis_추천_요약
  - entity: sensor.lotto_6_45_analysis_추천_게임_1
  - entity: sensor.lotto_6_45_analysis_추천_게임_2
  - entity: sensor.lotto_6_45_analysis_추천_게임_3
  - entity: sensor.lotto_6_45_analysis_추천_게임_4
  - entity: sensor.lotto_6_45_analysis_추천_게임_5
  - entity: button.lotto_6_45_analysis_즉시_새로고침
```

## 데이터 업데이트

- 기본 확인 주기: 6시간
- 최초 설치: 1회~최신 회차 전체 동기화 후 HA `.storage`에 캐시
- 이후: 최신 회차 번호만 확인하고 새 회차가 있을 때 해당 구간만 동기화
- 동행복권 일시 장애 시 기존 정상 캐시와 추천을 유지하고 `source_status`를 `cached_fallback`으로 표시

동행복권 사이트 내부 JSON 응답 구조는 공식 Open API 계약이 아니므로 향후 사이트 개편 시 변경될 수 있습니다.

## 데이터 출처

- 동행복권 로또 6/45 추첨결과
- 최신 회차: `https://dhlottery.co.kr/selectMainInfo.do`
- 회차 목록: `https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do`
- 단일 회차 보완: `https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do`

## 라이선스

MIT
