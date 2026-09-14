# Home Assistant AI 추천

`method_id: home_assistant_ai` · 분류: AI 설명 + 백엔드 CCSS 추첨 공식 · 로컬 23종과 별도

## 1. 번호와 설명의 분리

**번호는 Python 백엔드의 CCSS 공식과 OS CSPRNG가 생성하고, Home Assistant AI는 확정된 번호의 실행 근거만 설명합니다.** 현재 선택할 자연어 선호 입력이 없으므로 AI에게 별도의 공식 선택을 맡기지 않고 균등 CCSS를 기본으로 고정합니다. 과거 빈도·사주·AI 텍스트 샘플링을 난수원으로 사용하지 않습니다.

## 2. 설정과 실행

통합 구성에서 AI 추천 기능을 활성화하고 기본 데이터 생성 AI 또는 사용할 `ai_task.*` 엔티티를 선택합니다.

```yaml
action: lotto_645.generate_ai_recommendation
```

설명을 열어 보는 것만으로 AI 호출이나 재생성은 일어나지 않습니다. 일반 `lotto_645.refresh`는 기존 AI 추천을 유지합니다. AI 제공자별 비용·지연은 연결 설정에 따릅니다.

## 3. 개인정보 보호·검증과 프롬프트

백엔드에서 먼저 범위·중복·과거 1등 완전일치·로컬 및 직전 AI 조합 중복을 검사합니다. 프롬프트에는 확정 번호, 추첨 공식 ID·버전, 기준 회차, 실제 난수원과 제외 조건만 전달합니다. 원본 생년월일·출생시간·출생지·토큰은 보내지 않습니다.

AI 응답은 `formula_id=calibrated_stratified`, `reason`, 선택적 `basis`만 허용합니다. `numbers`나 `number_1` 같은 추가 필드, 공식 변경, 빈 설명은 거절합니다. 최대 2번의 설명 재시도에도 번호는 바뀌지 않습니다. AI 장애는 오류로 표시하고 로컬 추첨 공식은 계속 사용할 수 있습니다.

`base_formula_id`, `formula_version`, `rng`, `number_source=backend_formula_engine`, `ai_role=explanation_only`, `history_used_for_weighting=false`를 결과 속성에서 확인합니다. 과거 제외가 있으므로 전체 공간이 아닌 허용 조합 공간에서 균등합니다. AI 문장의 사실성을 완전히 증명하는 검증기는 아니며 항상 고정된 확률·주의사항을 병행 표시합니다.

## 4. 호환성과 한계

기존 AI 엔티티·서비스·`method_id`는 유지합니다. 이전 버전에서 저장한 AI 추천은 과거 기록으로 보존하며 새 CCSS 생성 결과라고 소급 표시하지 않습니다. AI는 선택 공식 중앙값에 들어가지 않습니다.

모든 유효한 한 게임의 1등 확률은 공정·독립 추첨에서 **1/8,145,060**입니다. AI 설명의 설득력이나 과거 리뷰 별점은 미래 당첨확률을 뜻하지 않습니다.

## 구현과 사용 근거

[ai_formula.py](../custom_components/lotto_645/ai_formula.py), [추첨 공식 엔진](../custom_components/lotto_645/sampling.py), [README의 Home Assistant AI 안내](../README.md#home-assistant-ai), [리뷰 해석](LOCAL_REVIEWS.md).
