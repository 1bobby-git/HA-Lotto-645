# 사이드바 뒤로 가려지는 패널 수정 (v1.11.9)

## 원인

v1.11.8의 이중 스크롤 수정에서 패널 호스트에 `position:absolute; inset:0`을 적용했다.
하지만 HA의 본문 영역은 사이드바 자리를 padding 또는 margin으로 확보하며,
중간 `partial-panel-resolver`와 `ha-panel-custom`이 위치 기준을 생성하지 않을 수 있다.
그때 절대 배치가 본문 대신 전체 화면을 기준으로 계산되어 로고·탭·제목·카드의 왼쪽이
사이드바 뒤에 놓인다. 브라우저 캐시가 원인인 문제는 아니다.

확인한 HA 참조:
[ha-drawer.ts](https://github.com/home-assistant/frontend/blob/dev/src/components/ha-drawer.ts)의
`.app-content`는 `position:relative` 없이 `padding-inline-start`와 높이 100%를 사용한다.
검토한 blob: `2bc8823a80e922a08649d6d274815b7b10ecddfa`.

## 수정 범위

패널 호스트를 `position:relative; inset:auto`로 정상 문서 흐름에 복귀시켰다.
기존 너비·높이 100%, `min-height:0`, 크기/레이아웃 containment, 패널 내부 스크롤은 유지한다.
사이드바 너비를 256px로 하드코딩하거나 HA/부모 DOM을 측정·수정하지 않는다.
추가 ResizeObserver, 타이머 또는 네트워크 요청을 만들지 않는다.

원본 로고, 폰트·색·카드·버튼, HA narrow 헤더 조건, 안전 영역, 공식 설명과 Markdown,
카운트다운의 정규 일정 기준, QR·구매번호 저장·revision·추천/AI·센서·동기화 정책은 변경하지 않는다.
수정 모듈의 캐시 키와 통합 버전만 함께 갱신한다.

## 재발 방지

기존 `#allocated` 검사는 위치가 지정된 부모 안에서만 검사하여 이 결함을 놓쳤다.
이를 삭제하지 않고 실제 배포 모듈을 사용하는 `smoke_panel_host_layout.py` 검사를 추가했다.

- Shadow DOM slot + 위치 미지정 본문 + inline resolver/custom wrapper 구조.
- padding / margin / flex의 3개 공간 배분 구조 × 10개 화면·사이드바 조합.
- 펼친 사이드바, 접힌 아이콘 레일, 항상 숨김, 870/871 경계, 임의 너비와 RTL.
- 한눈에 / 내 복권 / 추천 리뷰의 좌우 경계, 높이, 로고·탭·제목·카운트다운 위치.
- 긴 리뷰의 마지막 footer 접근, 바깥 문서 넘침 없음, 사이드바의 독립 스크롤.
- 예전 absolute 규칙을 잠시 되살리는 대조 검사에서 사이드바 침범이 반드시 감지되어야 함.
- 같은 검사 중 WebSocket 요청이 늘지 않아야 함.

이는 격리된 브라우저의 HA 구조 재현 검사이며 사용자 HA 서버나 실기기 검증은 아니다.
기존 QR/저장/상세 설명/안전 영역/카운트다운 검사는 그대로 이어서 실행한다.
