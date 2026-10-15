# MO-07 Jenkins 테스트 및 이전 배포 복구

Jenkinsfile은 Python API·Simulator·배포 스크립트·서비스 로깅 테스트와 웹 테스트를 실행한 뒤 이미지를 빌드한다. 웹 테스트에는 저장소 전체를 읽기 전용으로 연결하고 node_modules만 임시 쓰기 영역으로 제공한다. Python 테스트 환경은 서비스 이미지와 동일한 Python 3.11이다. 학습·추론의 torch 기반 전체 테스트와 실제 MySQL 통합 테스트는 이 단계의 필수 범위에 포함하지 않는다.

## 배포와 복구 동작

배포 직전에 Docker에서 실제 기존 서비스의 이미지 ID, 환경변수, 실행 명령, entrypoint, 작업 디렉터리, 사용자, 재시작 정책, healthcheck, 포트, 볼륨, 네트워크를 읽어 `.cqc-deploy-state/rollback.json`에 보존한다. 이미지 ID는 고정하고 볼륨·네트워크는 기존 리소스를 외부 참조한다. 현재 Compose 파일이 변경돼도 이전 실행 설정으로 복구한다. 기존 서비스가 unhealthy이거나 지원하지 않는 구성(특권·디바이스·host network·서비스 다중 인스턴스 등)이면 배포 전에 중단한다.

`pending` 표시는 컨테이너 교체 전에 생성한다. 일반 실패, 수동 취소, 20분 CI/CD 시간 초과 시 Jenkins `post.unsuccessful`에서 복구를 시도한다. 복구에는 별도 5분 제한이 적용된다. 복구 완료 후 이전 서비스의 healthcheck를 확인한 경우에만 기록을 제거한다. 실패하면 기록을 유지하며 다음 실행은 새 빌드 전에 먼저 복구를 시도한다. 에이전트 단절·강제 종료 직후 자동 복구는 보장되지 않으며 같은 워크스페이스로 다음 실행 시 재시도한다.

기존 컨테이너의 교체와 복구 과정에 서비스 중단이 있을 수 있다. 이 구현은 무중단 배포가 아니다. 첫 배포에는 이전 버전이 없어 실패 시 복구 불가를 명시적으로 보고한다. 최초 실패 기록은 원인을 해결하고 서비스를 수동 확인한 뒤에만 정리한다.

복구 기록에는 비밀번호 등 실행 자격 증명이 포함되므로 디렉터리 권한을 700, 파일 생성 권한을 600으로 제한하고 Git 및 Docker build context에서 제외한다. Jenkins 로그·artifact로 업로드하지 않는다. DB 데이터와 마이그레이션은 되돌리지 않는다. 특히 backend 기동의 `alembic upgrade head`는 이전 이미지와 호환되는 migration이어야 한다.

## 서버 검증

Jenkins와 Docker가 같은 서버에 있거나, Jenkins workspace 경로를 Docker daemon도 읽을 수 있어야 한다. Python 3.11 및 Node 24 테스트 이미지 다운로드가 가능해야 한다. 현재 파이프라인은 기존 서버와 동일한 `docker-compose` 명령을 사용한다.

1. 서버 저장소의 현재 브랜치와 미커밋 변경을 확인한다. 전달된 파일을 비교 후 적용한다. 이번 변경은 커밋·푸시하지 않았으므로 `git pull`만으로는 전달되지 않는다. Jenkins가 `Pipeline script from SCM`이면 서버 파일 복사만으로 새 Jenkinsfile을 읽지 않으며 checkout이 로컬 수정본을 덮어쓸 수도 있다. 커밋·푸시 전 검증은 동일한 Docker·Credentials를 가진 별도 수동 검증 Job에서 수정본을 `Pipeline script`로 사용하고, 적용한 서버 저장소를 custom workspace로 지정하며 `skipDefaultCheckout()`을 활성화해 진행한다. 기존 배포 Job과 동시에 실행하지 않는다. 실제 SCM 반영은 별도 승인 이후 진행한다. 처음 새 파라미터를 표시하는 실행이 필요할 수 있다.
2. 정상 서비스가 실행 중인 상태에서 두 실패 주입 파라미터를 모두 끄고 실행한다. Python Test, Web Test, Docker Build, Deploy, Verify가 통과해야 한다. 이후 `.cqc-deploy-state/pending`이 없어야 한다.
3. 컨테이너 상태를 아래 명령으로 기록한다. 전체 `docker inspect`는 비밀번호를 노출하므로 출력하지 않는다.

```sh
for id in $(docker-compose -f compose.yaml ps -q); do
    docker inspect --format='{{index .Config.Labels "com.docker.compose.service"}} {{.Id}} {{.Image}} {{.State.Health.Status}}' "$id"
done
```

4. `FORCE_BUILD_FAILURE=true`, `FORCE_HEALTH_FAILURE=false`로 실행한다. Build 단계가 의도적으로 실패하고 Deploy가 건너뛰어져야 한다. 실행 전후 컨테이너 ID·이미지 ID가 동일하고 health가 healthy인지 확인한다. 이 옵션은 Build 단계 오류 처리를 검증하며 실제 Dockerfile 실패를 생성하지는 않는다.
5. `FORCE_BUILD_FAILURE=false`, `FORCE_HEALTH_FAILURE=true`로 실행한다. Deploy 후 Verify가 의도적으로 실패하고 복구가 실행돼야 한다. Jenkins 결과는 실패로 남는 것이 정상이다. 이전 이미지 ID·실행 설정·health가 복구되어야 한다. 컨테이너 ID는 복구 중 재생성되므로 달라질 수 있다.
6. 실패 주입을 끄고 Deploy 또는 Verify 중에 Jenkins 실행을 중단한다. `unsuccessful` 복구가 실행되고 이전 서비스가 healthy인지 확인한다. 에이전트 강제 종료와 Jenkins 중단 버튼은 다른 시나리오다.
7. 마지막으로 두 옵션을 끄고 정상 실행한 뒤 관제 화면, Backend health, Simulator 재생을 확인한다.

복구 자체가 실패했으면 남은 `.cqc-deploy-state`를 지우거나 새 배포로 덮지 않는다. 같은 워크스페이스에서 다음 실행으로 재시도하거나 다음 명령으로 직접 복구한다.

```sh
sh scripts/ci/compose-rollback.sh
```

기록표에는 Jenkins build 번호, 배포 전후 이미지 ID, 테스트 통과·skip 수, 실패 주입 종류, 복구 결과 및 관제 확인 결과를 남긴다.
