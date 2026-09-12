# 원본 로고 및 main 보호 상태

v1.10.0의 빠른 추첨결과 수집/QR 패널과 다음 작업은 구분합니다.

## 원본 로고

현재 저장소의 작은 PNG가 첨부 원본과 동일하다고 확인되지 않았습니다. 이번 빠른 결과 기능에서 기존 파일을 다른 재제작 이미지로 덮어쓰지 않습니다. 가로 원본은 재압축/리사이즈/팔레트 축소 없이 그대로 적용하고, 정사각만 좌측 심볼 영역을 크롭해야 합니다.

대상 경로:
- `images/logo-horizontal.png`
- `images/icon-square.png`
- `custom_components/lotto_645/brand/logo.png`
- `custom_components/lotto_645/brand/icon.png`

원본 파일 확인 기준:
- 2048 × 682 RGBA
- SHA-256: `88f442d0d73cb9c4b378059297dfa1b8d3f334fb5e2dc9599404e5eee042ed3d`

이 원본이 실제로 업로드되기 전에는 로고 수정 완료로 표시하지 않습니다. 원본 교체 후에는 `scripts/render_brand.py`가 가로 원본까지 축소하지 않도록 별도 점검해야 합니다.

## main 보호

`.github/rulesets/main-safety.json`은 가져오기용 설정 파일이지 적용 완료 상태가 아닙니다. 연결된 GitHub 앱의 Administration 권한 부족으로 보호 설정 읽기/쓰기가 제한됩니다. 실제 보호 여부는 GitHub 저장소 설정에서 확인해야 합니다. `docs/MAIN_PROTECTION.md`의 최소 보호 규칙은 일반 미러 업데이트를 막지 않으면서 삭제/강제푸시를 금지하는 용도입니다.
