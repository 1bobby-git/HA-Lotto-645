# 브랜치 이력 통합 · 2026-09-20

사용자의 모든 브랜치 main 통합·정리 요청에 따른 이력 대조다.
현재 2.4.0 실행 파일·기능·태그를 변경하지 않는다. 이미 배포된 squash 변경과 폐기된 이전 아키텍처는 현재 구현을 우선하는 history-only 병합으로 부모 이력을 연결한다.
브랜치를 단순 삭제하거나 v1 과거검증·공개 Core·임시 workflow를 재도입하지 않는다. 미반영으로 보였던 44개 고유 tip의 처리 근거는 아래와 같다.

| 이전 브랜치 | tip | 처리 근거 |
| --- | --- | --- |
| feat/home-ticket-swiper | b8d0c4353ef3 | 기반 PR #58 병합 완료; squash/후속 수정 유지. |
| feat/jev-membership-tier-20260918 | 4ecf649e54c5 | 회원 티어 변경 7개 경로는 main의 2e5f6fa와 동일. 후속 2.3.4/2.4.0 유지. |
| fix/advanced-selector-options | a2d27b30e462 | 기반 PR #56 병합 완료; squash/후속 수정 유지. |
| release/2.2.2 | c00d4ee46002 | 기반 PR #55 병합 완료; squash/후속 수정 유지. |
| ad8f096 | 4dcbfb7fbe8e | 패치 동등·메타데이터 브랜치. |
| codex/source-snapshot | ba4b10afa66e | 폐기된 일회성 공개 소스/의존성 수집 workflow. |
| docs/method-guides-readme-cleanup | 27b54866ce45 | 기반 PR #18 병합 완료; squash/후속 수정 유지. |
| feat/consolidate-formulas-1.14.0 | 44b504c99a93 | 공식 정리 v1.15의 main b107ad1 및 비공개 Core 이전으로 대체. |
| feat/core-separation-1.21.0 | 6ff51aa93309 | 기반 PR #42 병합 완료; squash/후속 수정 유지. |
| feat/historical-validation-1.13.0 | 05e8056a75c5 | 기반 PR #33 병합 완료; squash/후속 수정 유지. |
| feat/korean-birthplace-prune-sensors-v1.19.0 | 17b43f6f263e | 기반 PR #40 병합 완료; squash/후속 수정 유지. |
| feat/panel-guides-countdown-1.11.8 | 30e1a92f84e4 | 기반 PR #24 병합 완료; squash/후속 수정 유지. |
| feat/recommended-formulas-1.20.0 | 0316863284d7 | 기반 PR #41 병합 완료; squash/후속 수정 유지. |
| feat/research-ac-formula | f77f54c8db40 | 기반 PR #32 병합 완료; squash/후속 수정 유지. |
| feat/research-formulas-1.12.0 | 718c9d3347fb | 기반 PR #28 병합 완료; squash/후속 수정 유지. |
| feat/unified-validation-review-v1.17.0 | f6b498cea0b5 | 기반 PR #37 병합 완료; squash/후속 수정 유지. |
| feat/v1.10.0-fast-results-qr | d0ea28009f8c | 기반 PR #13 병합 완료; squash/후속 수정 유지. |
| feat/v1.6.0-saju-formula-audit | 0ee8ab67dce4 | main 60de048/7e8d7b6의 감사 결과 및 현재 비공개 Core로 대체. |
| feat/v1.7.0-selected-median-consensus | a0ac4cc27e3b | 기반 PR #9 병합 완료; squash/후속 수정 유지. |
| feat/v1.9.0-purchased-ticket-results | d64b385acbd6 | 기반 PR #12 병합 완료; squash/후속 수정 유지. |
| feat/wallet-redesign-1.11.0 | 5e1c4d547503 | 기반 PR #15 병합 완료; squash/후속 수정 유지. |
| feature/purchase-formula-match | 50d324a18f04 | 기반 PR #54 병합 완료; squash/후속 수정 유지. |
| feature/researched-formulas | f59f8629639e | 실행 기능 없는 일회성 source/test wheel 수집 workflow. |
| fix/flat-draw-balls-1.11.1 | 156eccbaa366 | 기반 PR #16 병합 완료; squash/후속 수정 유지. |
| fix/force-screenshot-ball-palette-1.11.12 | 4a2564468aa5 | 기반 PR #29 병합 완료; squash/후속 수정 유지. |
| fix/ios-safe-area-1.11.3 | ae64eccd38eb | 기반 PR #19 병합 완료; squash/후속 수정 유지. |
| fix/managed-core-connection | fda245a2c08a | 기반 PR #44 병합 완료; squash/후속 수정 유지. |
| fix/reactive-consensus-1.12.1 | deeb1343dabe | 기반 PR #30 병합 완료; squash/후속 수정 유지. |
| fix/session-completion-1.15.0 | bfae3308e223 | 기반 PR #34 병합 완료; squash/후속 수정 유지. |
| fix/sidebar-layout-regression-1.11.9 | 01d9fff01934 | 기반 PR #25 병합 완료; squash/후속 수정 유지. |
| fix/smart-panel-sync-1.11.5 | d15ac8104f74 | 기반 PR #21 병합 완료; squash/후속 수정 유지. |
| fix/two-tier-header-1.11.4 | 43dff7cbabc7 | 기반 PR #20 병합 완료; squash/후속 수정 유지. |
| fix/v1.10.1-exact-user-branding | 09389a74c848 | PR #14 및 이후 정식 브랜딩으로 대체된 .release-work 임시 증거. |
| fix/v1.10.1-panel-review-recovery | 04f1cb2f0517 | 기반 PR #14 병합 완료; squash/후속 수정 유지. |
| fix/v1.9.1-exact-branding-final | d57d8177cdc4 | 현재 정식 브랜드를 교체하지 않는 폐기된 일회성 이미지 전송 workflow. |
| fix/validation-details-v1.17.1 | 135b77599e26 | 기반 PR #38 병합 완료; squash/후속 수정 유지. |
| fix/validation-hot-upgrade-v1.18.1 | 648b02249f24 | 기반 PR #39 병합 완료; squash/후속 수정 유지. |
| fix/validation-muted-misses-v1.15.1 | da527cb5bf00 | 기반 PR #35 병합 완료; squash/후속 수정 유지. |
| fix/white-draw-card-1.11.2 | cb8322aca43a | 기반 PR #17 병합 완료; squash/후속 수정 유지. |
| fix/winning-number-visuals-1.12.2 | cc4b595fe1ef | 기반 PR #31 병합 완료; squash/후속 수정 유지. |
| style/official-lotto-ball-colors-1.11.10 | ef5d7b581761 | 기반 PR #26 병합 완료; squash/후속 수정 유지. |
| style/screenshot-lotto-ball-colors-1.11.11 | efe7174064e3 | 기반 PR #27 병합 완료; squash/후속 수정 유지. |
| style/smartthings-design-alignment-1.11.7 | 16b313427dfa | 기반 PR #23 병합 완료; squash/후속 수정 유지. |
| work/research-formula-verification | 4adce18aad0b | 균등 샘플링은 비공개 Core의 uniform_* 공식으로 이전. 공개 sampling.py와 감사 workflow를 복원하지 않음. |

기타 이미 main의 조상인 브랜치는 별도 코드 병합이 필요 없다. 모든 tip을 최종 main에서 도달 가능한지 확인한 다음 remote/local branch를 삭제한다.
2.2.x release worktree의 미추적 dist-local 파일은 Formulab .local/archive/retired-worktrees에 해시와 함께 옮겨 보존한 뒤 worktree 등록을 해제한다. 로컬 refs/archive도 유지한다.
실제 HA 업데이트·재시작과 새 HACS 버전 발행은 수행하지 않는다. 기존 v2.4.0 배포물은 그대로 사용한다.
