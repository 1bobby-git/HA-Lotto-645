# main 보호 적용 상태

연결된 GitHub 앱으로 실제 `branches/main/protection` 조회를 시도했으나 `403 Resource not accessible by integration`이 반환되었습니다. 계정 자체가 저장소 관리자라는 것과 연결 앱이 Administration 권한을 가진다는 것은 다릅니다. 이 연결에는 브랜치 보호/규칙집 쓰기 기능이 없으므로 **보호를 적용했다고 표시하지 않습니다**. 다른 토큰·비밀을 가져오거나 GitHub Actions로 권한 제한을 우회하지 않습니다.

소유자가 가져올 수 있는 기본 규칙 파일은 `.github/rulesets/main-safety.json`입니다.

GitHub 저장소 `Settings → Rules → Rulesets → New ruleset → Import a ruleset`에서 파일을 가져오고 `Enforcement: Active`, 대상 `main`을 확인해 저장하세요. 적용 후 실제 보호 여부를 다시 조회해야 합니다.

이 기본 규칙은 **main 삭제·강제푸시를 금지**합니다. 기존 중앙 복권 미러가 main에 정상 fast-forward 데이터 업데이트를 하는 구조를 깨지 않도록 PR/필수검사 강제는 이 파일에 넣지 않았습니다. 코드 변경은 이 작업에서 계속 PR과 테스트 후 병합하며, 릴리스는 검증된 main 커밋에서만 나갑니다. PR/검사까지 서버에서 강제하려면 미러를 별도 데이터 브랜치 또는 PR 흐름으로 전환한 뒤 별도 강화 정책을 적용해야 합니다.

공식 API는 규칙집 생성에 Administration(write) 권한을 요구합니다:
https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset
