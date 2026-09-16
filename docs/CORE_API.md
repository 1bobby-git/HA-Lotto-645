# Lotto Core · API 1

## 두 프로젝트의 역할

HA-Lotto-645는 추첨 공식·현재 회차 추천·실제 저장 추천의 대조와 리뷰·구매번호 등록을 담당합니다. Lotto Lab은 이 코어를 내려받아 이력 분할, 반복 실행, 당첨 비교, 집계와 실험 DB를 담당합니다. HA에는 Lab의 검증 실행기나 UI를 포함하지 않습니다.

코어의 단일 원본은 `custom_components/lotto_645/lotto_core/`입니다. HA의 기존 `analysis.py`, `models.py`, `methods.py` 등은 이 원본을 가리키는 호환 import일 뿐 다른 공식을 복제하지 않습니다. 배포 wheel과 ZIP은 같은 파일을 그대로 묶습니다. 코어는 Home Assistant, 네트워크, 데이터 수집, 실제 구매/리뷰 저장을 의존하지 않습니다.

## 설치와 원본 고정

정식 릴리스의 `lotto-core-1.21.0.zip` 또는 `lotto_645_core-1.21.0-py3-none-any.whl`을 사용합니다. `lotto-core-manifest.json`에는 API 버전, 코어 버전, 소스 커밋, Python/라이브러리 조건, 파일별 SHA256이 들어 있습니다. `SHA256SUMS.txt`는 배포 파일을 확인합니다. 신뢰하는 릴리스와 **정확한 Git 커밋**을 먼저 확인한 뒤 해시를 비교해야 하며, 같은 출처의 체크섬만으로 발행자의 신뢰성이 입증되는 것은 아닙니다.

```sh
python -m pip install lotto_645_core-1.21.0-py3-none-any.whl
lotto-core --describe
```

Windows에는 `tzdata==2025.2`도 설치됩니다. 사주 달력의 완전 재현에는 시간대 데이터 버전도 동일해야 합니다.

Python 3.11 이상, `lunar_python==1.4.8`, `korean-lunar-calendar==0.4.0`을 사용합니다. Lab은 새 엔진을 별도 폴더/프로세스에서 시험한 뒤 전환하고 기존 실험의 코어 버전·커밋·입력 이력 해시를 유지해야 합니다. 실험 도중 자동으로 공식을 추가하거나 엔진을 교체하지 않습니다.

## Python 계약

```python
from lotto_core import API_VERSION, CORE_VERSION, describe, generate

catalog = describe()  # api_version, core_version, min_history, methods
result = generate(
    history=prefix,            # LottoDraw 또는 저장 형식 dict의 list/tuple
    method_ids=['uniform_fisher_yates', 'constraint_uniform'],
    target_round=31,            # prefix는 반드시 1~30회, 최소 30개
    generation_nonce=7,         # 내부 재생성 순번. 사용자가 지정할 시드가 아님
    formula_options={'generation_rules': {'odd': [2, 4]}},
)
for row in result.recommendations:
    print(row.method_id, row.numbers)
```

입력은 1회부터 시간순의 연속 이력입니다. 각 회차는 `round: int`, `draw_date: YYYY-MM-DD`, 오름차순 정수 6개 `numbers`, 그 6개와 다른 `bonus: int`입니다. 날짜는 증가해야 합니다. 대상 회차는 마지막 입력 회차의 바로 다음만 허용합니다. 코어는 정답이나 미래 이력을 자동으로 자르지 않고 잘못된 범위를 거절합니다. **Lab이 먼저 이력을 분리해야 합니다.**

`method_ids`의 순서를 보존하고 알 수 없는 ID·빈 목록·부족한 합의 입력을 거절합니다. 코어의 `normalize_method_ids`는 기존 HA 설정 복원용이며 새 외부 API의 검증을 대신하지 않습니다. 사주 공식은 `requires_personal_profile=true`로 표시하며 해당 프로필 없이는 사용할 수 없습니다. HA AI는 코어 카탈로그에 없습니다.

출력 `AnalysisResult`는 `target_round`, `based_on_round`, `recommendations`, `summary`를 갖습니다. 각 `Recommendation`은 `method_id`, `numbers`, `reason`, `score`, `details`와 버전 정보를 가집니다. `to_storage()`는 JSON용 표현을 반환합니다. 엄격한 합의 조건에서 후보가 없으면 해당 추천이 없을 수 있으므로 Lab은 이를 **생성 불가**로 기록해야 하며 미당첨으로 바꾸지 않습니다. 오류를 무작위 번호로 대체하지 않습니다.

`progress_callback(event)`는 `method_start`, `method_progress`, `method_complete` 이벤트를 받습니다. `recommendation_callback(record)`는 실제 생성한 추천의 **분리된 JSON용 사본**을 공식별 한 번 받습니다. 호출자는 콜백에서 예외를 발생시켜 취소할 수 있습니다. 콜백 출력이나 부분 완료를 최종 성공으로 저장하면 안 됩니다.

`rng`는 자동 시험·동일성 검산을 위한 Python 객체 주입입니다. 생산 경로는 생략해 OS 난수를 사용합니다. 정확한 결과 재현에는 코어 버전, 공식의 순서, 모든 입력/제외 목록, 재생성 순번 및 난수 상태가 같아야 합니다. 매번 새 실행이 필요한 Lab은 자신의 새 실행 순번과 난수를 전달하고 기록합니다. 고정 시드를 사용자 설정으로 추가하지 않습니다.

## JSON 계약

`generate_json()`은 같은 입력으로 `{api_version, core_version, target_round, based_on_round, recommendations, summary}`를 반환합니다. CLI `python -m lotto_core.cli`는 stdin의 JSON 요청 한 건을 읽고 stdout으로 한 건을 반환합니다. 요청에 `api_version: 1`이 필요하며 알 수 없는 필드는 거부됩니다. 실패 종료코드는 2이고 입력 원문·개인정보·Python traceback을 출력하지 않습니다.

API의 필수 필드나 의미를 바꿀 때는 API 버전을 올립니다. 공식 수와 설명은 하드코딩하지 않고 `describe()`에서 읽습니다. 사소한 설명 필드가 늘어나는 경우에도 기존 소비자는 알지 못하는 필드를 무시할 수 있어야 합니다.

## Lotto Lab 연결

기존 Lotto Lab 1.8.0은 HA의 과거 검증 모듈을 직접 불러왔으므로 새 코어에 맞는 연결부 업데이트가 한 번 필요합니다. **삭제한 모듈을 다시 넣어 호환시키지 않습니다.** 별도 제공하는 1.8.1 연결 패치는 Lab 안에서만 이력 분할·평가를 수행하고 여기의 `generate()`를 사용합니다. 기존 리뷰 DB와 이전에 고정한 엔진은 유지합니다. 새 API를 지원하지 않는 이전 Lab은 업데이트를 보류해야 합니다.

릴리스 배포는 사용자 HA/Windows 실행 환경이 자동으로 업데이트됐다는 뜻이 아닙니다. [소프트웨어 검증](VALIDATION.md) · [실제 추천 리뷰](LOCAL_REVIEWS.md)
