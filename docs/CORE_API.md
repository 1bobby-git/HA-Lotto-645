# Core 공개 서비스 계약

HA는 private 패키지 대신 HTTPS 서비스만 사용합니다. service_contract.py가 공개 반환값의 번호·회차·버전·요청 ID를 확인합니다. 내부 가중치·후보 점수·전체 details/summary는 전달하지 않습니다.

- GET /v1/formulas: 공개 카탈로그·입력 스키마.
- GET /v1/service: 기기 만료·코어·이력·한도.
- POST /v1/validate: 사용자 옵션 검사.
- POST /v1/generations: 같은 Idempotency-Key/request_key로 작업 접수.
- GET /v1/generations/by-key/{key}: 접수 응답 유실 복구.
- GET /v1/generations/{id}: 본인 생성 결과 조회.
- POST /v1/generations/{id}/cancel: 본인 작업 취소.

확정 결과의 core_version/formula_version/target_round/based_on_round/generated_at을 보존합니다. 임시 결과·생성 불가는 확정 성적에 넣지 않습니다.

reconcile은 같은 코어·입력·대상 회차의 소유한 원본만 이용하고 기본 공식의 번호를 유지합니다. 명리 원문은 별도 동의한 실행에서만 사용하며 서버 작업 원장에 저장하지 않습니다.

현재 인증은 기기별 만료·철회 가능한 토큰입니다. 회원/OAuth·웹사이트가 완성되었다는 의미가 아닙니다.
