# Simulator Dataset 볼륨 설정 및 검증

## 1. 목적

CQC Simulator는 외부 Dataset을 Docker Volume으로 연결하여 사용한다.

`compose.yaml`에서 `cqc_simulator_dataset`을 external volume으로 참조하므로, 최초 배포 전에 해당 볼륨을 생성해야 한다.

## 2. Dataset 준비

학원 서버의 Dataset 경로:

```text
D:\realtime-apple-arrival-demo\realtime-apple-arrival-demo
```

해당 경로에 다음 항목이 존재해야 한다.

- `index.json`
- `demo-virtual-brix.csv`
- `groups/`
- `partial_groups/`

다른 PC에 배포하는 경우 실제 Dataset 저장 경로로 변경한다.

## 3. Docker Volume 생성

Jenkins가 사용하는 Docker 엔진에서 실행한다. Windows Docker Desktop에서는
PowerShell에서 다음 명령으로 일반 named volume을 생성한다.
이미 볼륨이 있으면 아래 생성·복사 단계를 생략하고 4절 검증부터 진행한다.

```powershell
docker volume create cqc_simulator_dataset
```

빈 볼륨만 생성하면 Simulator가 시작할 수 없으므로 Dataset을 복사한다.
다음 명령은 새로 만든 빈 볼륨에서만 실행한다.

```powershell
$datasetPath = 'D:\realtime-apple-arrival-demo\realtime-apple-arrival-demo'
if (-not (Test-Path -LiteralPath "$datasetPath\index.json")) {
    throw "Dataset 경로에 index.json이 없습니다."
}
docker run --rm --mount "type=bind,source=$datasetPath,target=/source,readonly" --mount "type=volume,source=cqc_simulator_dataset,target=/d" alpine:3.20 sh -c 'set -eu; test -z "$(ls -A /d)"; cp -a /source/. /d/'
if ($LASTEXITCODE -ne 0) {
    throw "Dataset 복사에 실패했습니다. 볼륨이 비어 있는지 확인하세요."
}
```

**주의사항**

- 이 명령은 Windows 호스트의 Dataset 내용을 Docker Volume에 복사한다.
- Docker Desktop에서 해당 드라이브에 접근할 수 있어야 한다.
- Jenkins 배포 전, Jenkins가 사용하는 Docker 엔진에서도 동일한 볼륨에 접근할 수 있어야 한다.
- Dataset 경로가 다른 서버에서는 `$datasetPath` 값을 해당 서버 환경에 맞게 변경한다.
- 기존 볼륨을 임의로 삭제하거나 재생성하지 않는다.

## 4. Dataset 검증

다음 명령은 Dataset을 읽기 전용으로 연결한다.

```powershell
$volume = "cqc_simulator_dataset"

docker volume inspect $volume --format '{{.Name}}'
if ($LASTEXITCODE -ne 0) {
    throw "Dataset 볼륨이 없습니다."
}

docker run --rm --mount "type=volume,source=$volume,target=/d,readonly" alpine:3.20 sh -c "find /d/groups -mindepth 1 -maxdepth 1 -type d | wc -l"

docker run --rm --mount "type=volume,source=$volume,target=/d,readonly" alpine:3.20 sh -c "find /d/partial_groups -mindepth 1 -maxdepth 1 -type d | wc -l"

docker run --rm --mount "type=volume,source=$volume,target=/d,readonly" alpine:3.20 wc -l /d/demo-virtual-brix.csv

docker run --rm --mount "type=volume,source=$volume,target=/d,readonly" alpine:3.20 sha256sum /d/index.json /d/demo-virtual-brix.csv
```

## 5. Dataset 기준 및 현재 확인 결과

아래 값은 Dataset 확인 기준이다. 2026-09-30 현재 Windows `C:\CQC`에서
연결된 Docker context `desktop-linux`의 `cqc_simulator_dataset` 볼륨을 읽기 전용으로
검사한 결과도 아래 값과 일치했다. 학원 서버에서 Jenkins가 사용하는 Docker 엔진의
볼륨은 해당 서버에서 4절 명령을 실행해 별도로 확인해야 한다.

| 항목                          | 검증 결과                                                        |
| ----------------------------- | ---------------------------------------------------------------- |
| groups                        | 869개                                                            |
| partial_groups                | 127개                                                            |
| demo-virtual-brix.csv         | 997줄                                                            |
| index.json SHA-256            | dc866e0ccd91f8cff9ce9a523d1707c4df678d564ace24016c5344537ba7e959 |
| demo-virtual-brix.csv SHA-256 | 72377db48cc9ff5bd4f4978364e41b2c1e9807cb99eebb428a6a22f1a851c346 |

제공된 SHA-256 앞자리 기준은 각각 `dc866e0ccd91f8cf`, `72377db48cc9ff5b`이며,
현재 연결된 Docker 엔진에서 확인한 전체 SHA-256은 위 표와 같다.

## 6. 배포 시 주의사항

외부 볼륨이 존재하지 않으면 Docker Compose 배포가 실패할 수 있다.

따라서 최초 배포 순서는 다음과 같다.

1. Dataset 파일 준비
2. Docker Volume 생성
3. Dataset 개수 및 SHA-256 검증
4. 실제 `.env`에 `SIMULATOR_FAULT_TOKEN` 설정
5. Jenkins 또는 Docker Compose 배포 진행

`.env.example`에는 로컬 실행용 `SIMULATOR_FAULT_TOKEN=change_me_simulator_token`이
활성화되어 있다. 실제 배포에서는 별도 토큰으로 교체한다. Jenkins는
`cqc-simulator-fault-token` Credentials 값을 Backend와 Simulator에 함께 전달한다.

## 7. 자동 재생 및 배포 성공 조건

- Simulator는 시작 시 Dataset과 저장된 위치를 검증하고 자동 재생한다.
- `/health`는 재생 중이며 최근 30초 내 Backend 검사 전송이 성공했을 때만 200을 반환한다.
- 재생 중지, 첫 검사 성공 전, 30초 넘게 검사 성공 기록이 없는 상태에서는 503을 반환한다.
- Compose healthcheck는 `/health`의 HTTP 상태와 `running`, `lastSeenAt`을 확인한다.
- Jenkins Verify 단계도 같은 재생 조건을 확인하므로 컨테이너 실행만으로 배포 성공을 판정하지 않는다.
