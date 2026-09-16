# HA 배포 경로: 유료 Actions 불필요

2026-09-16. Core와 HA 작업·GitHub 소스/배포물 게시가 현재 범위다. Lab 웹·도메인·Proxmox 서비스 구축을 먼저 완료하라는 요구가 아니다.

## 원인과 정책

Core Actions의 사용자 제공 오류는 계정 결제 실패 또는 지출 한도 때문에 job이 시작되지 않았다는 내용이다. 저장소/Release 쓰기 권한이나 테스트 실패로 취급하지 않는다. 결제·한도 상향·반복 재실행은 해결 절차로 요구하지 않는다.

Core는 private 저장소에 유지한다. 로컬 개발 PC/이미 보유한 실행기에서 검사·빌드하고 GitHub CLI로 Release를 직접 올린다. Wrangler는 Cloudflare용이며 GitHub 릴리스 발행에 필요하지 않다. Tailscale은 연결 수단으로만 사용하며, 공개 웹서비스의 선행 설치물이 아니다.

## HA 준비물 생성

```sh
# 전체 HA 저장소의 작업 브랜치에 있는, 커밋된 깨끗한 checkout
python scripts/prepare_local_release.py
```

출력은 시스템 임시 폴더의 `lotto_645-preview.zip`, `BUILD_INFO.json`, `SHA256SUMS.txt`다. 정확한 Git 커밋의 컴포넌트 파일만 묶고 태그·릴리스·워크플로를 실행하지 않는다. 작업 폴더/사용자 .storage/개인 복권을 업로드하지 않는다. 이것은 검사나 정상 동작 인증을 대신하지 않는다.

## 현재 PR #43의 상태

현재 PR은 서비스 계약·HTTP 클라이언트·요청 복구 준비다. **coordinator/설정/실제 생성은 아직 새 서버 경로에 연결되지 않았다.** 현 브랜치에서 만든 preview에는 기존 공개 코어가 포함될 수 있으며 BUILD_INFO에 그 여부를 표시한다. 이는 새 private 계산 구현을 공개하겠다는 정책이 아니다.

이 준비물은 HACS 정상 업데이트나 비공개 Core 전환 완료본으로 배포하지 않는다. 기존 v1.21.0을 덮어쓰거나 태그를 다시 지정하지 않는다. HA main과 운영 사용자 기록은 그대로 둔다.

## Release 발행은 준비 완료 후 별도 단계

실제 생성 경로·QR·리뷰·데이터 보존을 해당 커밋에서 확인한 뒤 인증된 개발 PC에서 `gh release create`를 사용한다. 정확한 `--target <commit>`, 새 태그, 초기 `--draft --prerelease --latest=false`를 사용하고 파일·체크섬을 확인한 뒤 공개 상태로 전환한다. 승인 전에는 stable/latest로 표시하지 않는다. 해당 시점의 컴포넌트 version과 배포 태그 정책도 일치시킨다.

이 문서는 Release를 이미 만들었다는 보고가 아니다. Core 패키지 게시, HA 개발 브랜치 게시, HA 실제 동작 완료, Lab 운영 배포를 구분한다. 서버 전용 계산 구조에서는 HA 실제 생성 확인에 최소 실행 API가 필요하지만, 웹사이트·회원 커뮤니티를 먼저 만들 필요는 없다.

자동 HA Release 워크플로는 이 전환 브랜치에서 제거한다. 공개 저장소의 기존 검증·당첨 데이터 미러 워크플로는 이번 변경으로 삭제하지 않는다. 기본 public 표준 러너는 현재 GitHub 공식 문서상 무료이며 private Core 코드/자격정보를 그곳으로 옮기지 않는다. 수동 빌드·발행은 Actions 검사 통과를 가장하거나 필수 실제 동작 검사를 생략하는 수단이 아니다.

근거: https://cli.github.com/manual/gh_release_create · https://docs.github.com/en/billing/concepts/product-billing/github-actions
