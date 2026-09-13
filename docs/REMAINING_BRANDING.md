# 원본 로고 및 main 보호 상태

v1.10.0의 빠른 추첨결과 수집/QR 패널과 다음 작업은 구분합니다.

## 원본 로고

첨부된 가로 로고와 정사각형 아이콘을 재압축·리사이즈·팔레트 축소 없이 각각의 기준 원본으로 사용합니다.

대상 경로:
- `custom_components/lotto_645/brand/logo.png`
- `custom_components/lotto_645/brand/icon.png`

원본 파일 확인 기준:
- `logo.png`: 2172 × 724 RGBA, SHA-256 `246737fadf5e336144ade59f012c66f4f4cfc85642c0d4331dc3e0c04a5c0881`
- `icon.png`: 580 × 580 RGBA, SHA-256 `0e527f721cd3372bfddc6b30a230951a7af8188e851fc0d236e3bf5eb076172d`

`scripts/render_brand.py`는 두 원본을 변경하지 않고 선택적인 `@2x` 파일만 생성합니다.

## main 보호

`.github/rulesets/main-safety.json`은 가져오기용 설정 파일이지 적용 완료 상태가 아닙니다. 연결된 GitHub 앱의 Administration 권한 부족으로 보호 설정 읽기/쓰기가 제한됩니다. 실제 보호 여부는 GitHub 저장소 설정에서 확인해야 합니다. `docs/MAIN_PROTECTION.md`의 최소 보호 규칙은 일반 미러 업데이트를 막지 않으면서 삭제/강제푸시를 금지하는 용도입니다.
