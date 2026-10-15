# MO-03 배포 경계와 BE-10 4/4 기준선

## Jenkins Job 설정 확인

2026-10-06 Jenkins 관리자 로그인 화면에서 읽기 전용으로 확인했다. 아래 확인값은 설정 변경 없이 관찰한 것이다.

| 항목 | 확인할 값 |
| --- | --- |
| 배포 Job | `CQC-CICD`, `http://192.168.133.106:8080/job/CQC-CICD/`, Pipeline script from SCM, Git `*/dev`; GitHub hook trigger와 Poll SCM (`* * * * *`) 활성. [SCM Poll 로그](http://192.168.133.106:8080/job/CQC-CICD/scmPollLog/)는 `refs/heads/dev`의 `be4415d`만 확인하고 #109 이후 변경 없음. [GitHub Hook 로그](http://192.168.133.106:8080/job/CQC-CICD/GitHubPollLog/)에는 수신 기록이 없어 실제 Webhook 전달은 미확인 |
| PR 검사 | Jenkins 대시보드에는 PR 전용 Job이 없음. 로컬 `.github/workflows/pr-checks.yml`은 dev 대상 PR에서 Python/Web 검사만 실행하도록 작성. 닫힌 PR #107의 [실행 기록](https://github.com/yuudong123/CQC/actions/runs/37421627596)에서 동일 워크플로의 두 Job 모두 성공. PR #107은 병합되지 않았고 PR용 브랜치는 삭제됨 |
| 병합 제한 | GitHub `dev` 보호 규칙의 필수 검사 및 1명 승인 설정은 미확인. 현재 로그인 가능한 계정은 저장소 관리자 설정에 접근할 수 없음 |
| 사람 확인 | GitHub review 또는 별도 확인 기록의 위치와 담당자는 미확인 |

로컬 GitHub Actions 워크플로는 dev 대상 PR에서 Python/Web 검사만 실행하고 배포하지 않는다. 로컬 `Jenkinsfile`의 Docker Build·Deploy·Verify와 복구는 `dev`에서만 실행하도록 수정했다. 브랜치는 `BRANCH_NAME`, `GIT_BRANCH`, Job의 SCM Branch Specifier 순으로 확인하고 PR의 `CHANGE_ID`가 있으면 배포하지 않는다. 배포 Job SCM은 현재 `*/dev`다. PR 검사가 실패한 경우 병합을 막으려면 GitHub `dev` 보호 규칙의 필수 검사 설정이 필요하다.

## 실제 배포 증거

| 항목 | 값 / 증거 링크 |
| --- | --- |
| 확인 시각, 확인자 | 2026-10-06, Jenkins 관리자 로그인으로 읽기 전용 조회 |
| 배포된 dev 전체 commit SHA | #109 checkout 및 Deploy SHA `be4415dbaf946a5b38d90862cc72f106c8e45e55`; 조회 시 실행 중인 3개 컨테이너 ID가 #109 Verify 로그와 일치 |
| Jenkins build 번호 / URL | `#109` / `http://192.168.133.106:8080/job/CQC-CICD/109/` |
| Python → Web → Build → Deploy → Verify 결과 | [#109 Console Output](http://192.168.133.106:8080/job/CQC-CICD/109/console)에서 모두 성공, 전체 `SUCCESS`; Python 413 passed/91 skipped, Web 52 passed. PR #94의 병합 커밋 `51c6e325213d50ac1781a223f454d7eaeaf64285`는 #109 배포 SHA의 조상임을 확인 |
| Backend container ID / image ID | `88b0baaa6c01a0ae3800807d00c5fd62a3dfaeb32e21735a7d825f84c9026540` / `sha256:ddeaa7a01eebdbbc94c0c2dd00dd3df04f821590084e762ac81e216f612359c7` |
| Frontend container ID / image ID | `ed13c2066740b73acbc4f81d2b6fe6d8b17efc2ed4cb583e63cc99f5d50d263f` / `sha256:c5c6ceeb2c239b9f7cd3026261496c8a77d37396f5c909e7710c7e5c80cbe338` |
| Inference container ID / image ID | `fe40a445097cb684c0dcbc5c8a6bf0258c1ce12bab82d00d2484f7f1654aff18` / `sha256:f185082afb129c955d80ffd1dc74ec87f66387002d2d4cf9ebd9498cf92c551a` |
| 각 image와 build/commit 연결 | 위 container ID는 #109 Verify 로그와 조회 시 `docker inspect`에서 일치. 이미지 ID는 #109 Docker Build 로그와 조회 시 `docker inspect`에서 일치 |
| MySQL `alembic_version` | `20260929_02` (실행 중 Backend의 DB 연결에서 조회) |
| 이전 정상 버전 복구용 image ID | Backend `sha256:e29ccb95ea21551b893d5efadddd71cd02323b54cca1873aa5af64573bb55752`, Frontend `sha256:121ba30b5ddd8e776c4e24dbb71f209974cedc332f6c4df088da901bf964d763`, Inference `sha256:57a80f37f0ff5d73c7792c68d65a7eb96b251e4beb621fa5952955122b51f04e` |
| `.cqc-deploy-state/pending` 존재 여부 | `false` (Jenkins 작업공간에서 조회) |
| feat PR 검사 성공·실패 및 배포 미실행 증거 | 닫힌 PR #107에서 [Python](https://github.com/yuudong123/CQC/actions/runs/37421627596/job/112132038516)·[Web](https://github.com/yuudong123/CQC/actions/runs/37421627596/job/112132038757) 성공. 워크플로에 배포 단계가 없음. 실패 시 병합 차단 증거는 미확인 |
| main/feat push에서 배포 미실행 증거 | 배포 Job SCM Branch Specifier `*/dev` 확인. `feat/mlops` 변경 후 SCM Poll 로그는 `dev`만 조회하고 #109 이후 변경 없다고 기록. main push 비교 기록은 미확인 |

서버 작업 디렉터리에서 `git rev-parse HEAD`, `docker-compose -f compose.yaml ps -q backend logistics-web inference`, 각 ID에 대한 `docker inspect --format '{{.Id}} {{.Image}}' <container-id>`, `test -e .cqc-deploy-state/pending`, `cat .cqc-deploy-state/rollback.json`(비밀값 확인 후 필요한 image ID만 공유)로 수집한다. MySQL migration은 DB 관리자가 `SELECT version_num FROM alembic_version;` 결과만 공유한다. Jenkins stage 화면과 build URL을 함께 기록해 SHA가 실제 배포 실행과 연결되도록 한다.

현재 적용 설정은 실행 중 Backend의 `Settings`에서 필요한 값만 조회했다. connect/business/hard timeout은 각각 `200/500/2000 ms`, cultivar/quality confidence threshold는 `0.50/0.60`, inspection history limit/delete batch는 `86400/8640`, system error/low-confidence image limit는 `100/200`, Virtual Control/late-result history limit는 `200/200`이다. 인증 정보는 출력하지 않았다. 이 값은 조회 시점의 기준선이며 새 배포 후 다시 확인해야 한다.

Jenkins Script Console에서 실제 Job SCM의 `*/dev`를 새 가드 식에 대입해 `normalized=dev`, `deploy=true`를 확인했다. 이 평가는 배포를 실행하지 않았다. 새 Jenkinsfile과 워크플로는 `feat/mlops`에서 작성했으며, `dev` 반영 후 새 Jenkinsfile의 Pipeline 실행 증거를 추가해야 한다.

## 완료를 위한 저장소 관리자 설정과 검증

현재 GitHub 로그인 계정에는 저장소 관리 권한이 없다. 저장소 관리자는 `Settings → Branches`에서 `dev` 보호 규칙을 만들고 **Require a pull request before merging**, **Required approvals: 1**, **Require status checks to pass before merging**를 켠 뒤 실제 실행된 검사 이름 `PR checks / python`, `PR checks / web`을 필수로 지정해야 한다. 규칙 저장 후 실패한 PR에서 병합 버튼이 차단되는지, 승인 전에도 차단되는지 확인한다. 확인 기록은 이 문서에 빌드·PR URL과 함께 추가한다. 사용자가 새 PR 생성을 원하지 않아 이 검증은 수행하지 않았다.

Webhook 연결은 사용자 요청에 따라 이번 완료 판정에서 제외한다. Jenkins Job에는 hook 트리거가 켜져 있지만 Hook 로그에는 수신 기록이 없었으며 실제 연결 완료로 판단하지 않는다. Poll SCM이 `dev`를 매분 확인하는 것은 로그로 검증됐다.
