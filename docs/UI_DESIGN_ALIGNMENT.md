# SmartThings 웹과 로또 패널의 디자인 통일

## 기준과 적용 범위

참조 화면은 사용자가 지정한 SmartThings Web Bridge v1.8.52이며, 실제 값은
[status-page.ts](https://github.com/1bobby-git/HA-SmartThings_Web/blob/v1.8.52/bridge/src/server/status-page.ts)의
body, hc-topbar, hc-brand-logo, hc-tabs, hc-title-row, hc-card에서 확인했다.
검토한 소스 blob은 `b70a68a3a8691729c90d0a2d4e96c1c80d0718e5`다.

첨부된 Home Assistant Component Web UI Design System v1.0의
Host/Component 분리, 로고 원본 보존, 중립 배경, 접근성 규칙을 함께 적용한다.
가이드의 예시 높이와 실제 참조 화면의 값이 다른 곳은 **실제 화면**을 우선한다.
카드 그림자는 가이드의 약한 그림자(0 8px 28px / 6%)를 유지한다.
참조 소스의 전역 shadow 제거 규칙을 HA나 로또의 모든 요소에 복사하지 않는다.

## 공통 시각 규칙

| 항목 | 적용값 |
|---|---|
| 서체 순서 | -apple-system, BlinkMacSystemFont, Pretendard, Noto Sans KR, Noto Sans CJK KR, Malgun Gothic, sans-serif |
| 기본 본문 | 15px / 1.65 |
| 제목 | 28~38px, 780, 줄높이 1.3 |
| 작은 영문 제목 | 12px, 800, 파란색, 자간 .12em |
| 설명문 | 모바일에서도 15px |
| 보조 정보 | 12~13px. 기존 9~11px 안내문 확대 |
| 컴포넌트 상단 행 | 데스크톱 76px, 모바일 68px |
| 로고 | 높이 38px / 모바일 32px / 초소형 30px, 원본 비율, object-fit: contain |
| 헤더 내용 | 로고 / HA 연결 상태 / 실제 통합 버전 / 설정 |
| 탭 | 높이 48px, 글자 14px, 간격 30px / 모바일 24px, 3px 밑줄 |
| 본문 시작 여백 | 데스크톱 38px / 모바일 28px |
| 최대 폭과 좌우 여백 | 1248px, 40 / 28 / 20 / 16px |
| 주요 카드 | radius 18px / 모바일 16px |
| 일반 카드 | radius 14px |
| 버튼·입력 | radius 10px, 조작 높이 최소 44px |
| 컴포넌트 헤더 | 라이트·다크 모두 흰 배경과 진한 글자, 얇은 구분선 |

폰트 파일을 추가하거나 외부 웹폰트를 다운로드하지 않는다. 같은 운영체제와
설치된 글꼴 환경에서 같은 font-family 순서를 사용한다. 서로 다른 운영체제에서
픽셀 단위로 같은 글꼴이 표시된다는 의미는 아니다.

## HA 헤더는 별도 계층

`lotto-panel-shell.js`의 기존 `narrow`, `dockedSidebar`, `kioskMode` 판정을 보존한다.
컴포넌트 폭을 재서 HA의 헤더를 강제 표시하지 않는다. HA Host Header는 HA의
폰트·색상 변수를, 그 아래 브랜드와 탭은 공통 컴포넌트 규격을 사용한다.

특히 브라우저가 871px이어도 사이드바를 제외한 로또 패널 폭은 약 615px일 수 있다.
이때 로또 내부는 compact 배치가 되어도 HA 헤더는 넓은 화면 상태를 유지해야 한다.
부모 DOM, HA의 Shadow DOM, 외부 CSS를 조회·수정하지 않는다.

## 구현과 보존 사항

컴포넌트의 최종 시각 규칙은 `www/lotto-panel-design.js` 한 곳에서 관리한다.
진입 모듈이 이를 동기적으로 가져와 로또의 Shadow Root에만 한 번 적용한다.
버전과 설정 글자는 기존 헤더에 추가하지만 새로운 상태 조회나 이벤트 리스너는 만들지 않는다.

기존 컨트롤러, 스마트 동기화 정책, API, 추천/AI, 구매번호와 revision, 원본 로고,
번호 공의 단색·흰색 숫자, 흰색 추첨 카드, 센서 ID와 README 추첨 공식 문서를 보존한다.
좁은 패널에서는 번호 공 크기/간격만 가용 폭에 맞춰 조정한다.

## 회귀 검증

`scripts/smoke_ticket_panel.py`는 실제 배포 entry와 모든 모듈을 실행한다.
기존 QR PNG 판독, 명시적 저장, 작성 초안과 revision, HA 헤더 메뉴/전환,
안전 영역 검사를 계속 수행한다.

추가 `smoke_panel_design_system.py`는 12개 viewport/할당 패널 폭 조합 × 2개 테마에서
브라우저가 실제 계산한 글꼴, 글자 크기, 헤더/탭 높이, 로고, 여백, 카드/버튼 radius,
상태 표시, 숫자 색상과 가로 넘침을 검사한다. 870/871 경계와 871/615 조합을 포함한다.

이 검증은 브라우저 fixture다. 실제 사용자 HA나 물리 iPhone/Safari 검증으로 간주하지 않는다.
