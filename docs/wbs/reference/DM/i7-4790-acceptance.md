# i7-4790 모델 성능 수용시험

## 목적

WBS의 DM-06·DM-08 완료 조건인 Intel Core i7-4790, RAM 16GB 환경의 평균·최대·p95 추론시간과 초당 처리량을 동일 명령으로 측정한다.

## 안전 조건

- CPU 이름에 `i7-4790`이 없으면 실행을 거부한다.
- 물리 RAM이 15GiB 미만이면 실행을 거부한다.
- 고정 Test가 아닌 validation 입력으로 모델 추론시간만 측정한다.
- 체크포인트 SHA-256과 실제 CPU·RAM을 결과에 함께 기록한다.
- i7-14700F 등 다른 CPU 결과를 목표 장비 승인값으로 사용할 수 없다.

## 2026-09-23 학원 Jenkins 서버 인계

목표 장비는 학원 서버 `192.168.133.106`의 **i7-4790 / RAM 16GB**다. 이전 문서의 “장비가 없다”는 판단은 잘못됐다. Jenkins에 접속할 수 있다는 사실과 실제 성능 수용시험 완료는 구분한다. 시험 결과 파일이 생기기 전까지 WBS의 CPU 수용시험은 미완료다.

데이터·모델 담당이 제공한 실행 단위는 `src/training/acceptance_cpu.py`와 v2 모델 패키지다. 새 명령은 Linux Jenkins 에이전트에서도 실행되며 **원본 AI Hub 데이터가 필요하지 않다.** 모델 입력과 동일한 `[1, 12, 3, 224, 224]` 형태의 고정 합성 텐서를 사용하여 전처리 이후 모델 순수 추론시간을 잰다. Test 사과를 측정에 사용하지 않는다.

모델 패키지 식별:

- 버전: `cqc-apple-separate12-focal-v2-candidate`
- 필요 파일: `model.json`, `model.pt`를 **같은 디렉터리**에 둔다.
- `model.pt` SHA-256: `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a`.
- 데이터 담당 보유 경로: 노트북 `C:\CQC\models\cqc-apple-separate12-focal-v2-candidate`, 집 PC `D:\Study\CQC\models\cqc-apple-separate12-focal-v2-candidate`.
- 모델 바이너리는 Git에서 제외돼 있다. Jenkins 실행 전에 위 두 파일을 학원 서버의 Jenkins 작업공간 또는 별도 모델 디렉터리에 전달해야 한다. `model.json`의 해시와 실제 바이너리 해시가 다르면 시험이 중단된다. CI가 임의 체크포인트를 내려받거나 대체하지 않는다.

### Linux Jenkins 에이전트: Docker에서 모델 수용시험

아래는 Jenkins 작업공간 루트에서 실행한다. 모델은 `models/cqc-apple-separate12-focal-v2-candidate`에 배치한 예시다. `BUILD_NUMBER`가 없는 수동 실행에서는 다른 고유한 출력 폴더명을 정한다.

```sh
docker build -f Dockerfile.inference -t cqc-inference-acceptance .
mkdir -p "outputs/i7-4790-acceptance/${BUILD_NUMBER}"
docker run --rm --network none \
  -v "$PWD/models/cqc-apple-separate12-focal-v2-candidate:/app/model:ro" \
  -v "$PWD/outputs/i7-4790-acceptance/${BUILD_NUMBER}:/app/output" \
  cqc-inference-acceptance \
  python -m src.training.acceptance_cpu \
    --package-dir /app/model \
    --output /app/output/acceptance.json
```

컨테이너에서 `/proc/cpuinfo`와 `/proc/meminfo`를 읽어 i7-4790과 15GiB 이상 RAM을 확인한다. 10회 준비 실행, 순차 100회, 동시 요청 1·2·4 각각 100회를 재현하고 평균·최대·p95·초당 처리량을 한 JSON에 저장한다. CPU나 RAM이 기준과 다르면 실제 수용시험을 실행하지 않는다. `--smoke`는 다른 장비에서 명령을 점검할 때만 사용하며 `accepted=false`로 기록된다.

실행 전 MLOps 담당 확인 항목: Jenkins 에이전트가 **학원 서버의 호스트 CPU**에서 Docker를 실행하는지, 다른 원격 Docker 데몬으로 명령을 전달하지 않는지, 모델 파일을 읽기 전용으로 마운트했는지. 동일 모델 버전과 체크섬으로 inference 컨테이너를 기동한 뒤 `/health`와 실제 Backend→Inference HTTP 지연도 별도 수용시험에서 확인한다.

### 기존 Windows 직접 실행 경로

Windows 호스트에서 원본 데이터와 가상환경이 준비돼 있을 경우 기존 PowerShell 스크립트를 계속 사용할 수 있다. 이는 위 Docker 합성 입력 경로와 측정 자료·실행환경이 다르므로 결과에 실행 방식을 함께 적는다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File src\training\run_i7_4790_acceptance.ps1 `
  -Checkpoint models\<version>\model.pt
```

다음 파일이 `outputs/i7-4790-acceptance/`에 생성된다.

- `latency.json`: 10회 준비 실행 후 100회 평균·최대·p95
- `concurrency.json`: 동시 처리 1·2·4, 각 100회 p95·처리량
- `acceptance.json`: 하드웨어·체크섬·기준·최종 판정

## 통과 기준

- 순수 모델 추론 p95 500ms 이하
- 동시 처리 1의 p95 500ms 이하
- 동시 처리 1의 처리량 초당 2건 이상

평균과 최대값은 통과 여부와 별개로 모두 공개한다. 실제 HTTP·Docker 통합 지연은 MLOps 통합 수용시험에서 별도로 측정한다.

## 현재 상태

2026-09-23 학원 i7-4790 Docker 환경에서 Jenkins 저장 볼륨 `jenkins_home`의 모델 패키지를 읽기 전용으로 연결해 모델 단독 수용시험을 완료했다. `model.pt` SHA-256은 위 패키지 식별값과 일치했고, 결과는 [`results/i7-4790-model-only-20260923.json`](results/i7-4790-model-only-20260923.json)에 보존했다. 컨테이너가 i7-4790과 RAM 15.5GiB를 확인했으며 `smoke=false`, `accepted=true`였다.

| 측정 | 평균 | 최대 | p95 | 처리량 |
|---|---:|---:|---:|---:|
| 순차 추론 100회 | 122.85ms | 201.43ms | 138.50ms | — |
| 동시 처리 1, 100회 | 135.99ms | 234.29ms | 178.01ms | 7.35건/초 |
| 동시 처리 2, 100회 | 212.42ms | 301.40ms | 254.15ms | 9.36건/초 |
| 동시 처리 4, 100회 | 349.54ms | 408.93ms | 397.14ms | 11.28건/초 |

이는 전처리 후 합성 입력의 **모델 forward만** 측정한 결과다. 이미지 디코딩, HTTP 왕복, Docker 대기, Backend 시간을 포함한 통합 지연과 운영 동시 처리 수는 별도 검증이 필요하다. 시험 직후 Jenkins는 WSL Docker 소켓 마운트 오류로 재시작에 실패했지만, Docker Desktop의 Ubuntu WSL 연결을 활성화하고 소켓이 생성된 뒤 재시작했다. Jenkins 로그인 응답 HTTP 200과 컨테이너 내부 Docker 클라이언트의 엔진 연결을 확인했다.

### 별도 Inference HTTP 측정

같은 i7-4790 환경에서 실제 모델 API를 별도 Docker 컨테이너로 실행했다. 고정된 224×224 JPEG 12장을 multipart로 전송해 10회 준비 실행 뒤 순차 100회를 측정했다. 요청 크기는 약 303KB이고 결과는 [`results/i7-4790-inference-http-20260923.json`](results/i7-4790-inference-http-20260923.json)에 보존했다.

| 측정 범위 | 평균 | 최대 | p95 | 처리량 |
|---|---:|---:|---:|---:|
| Windows 호스트→Inference HTTP 왕복 | 161.90ms | 293.11ms | 198.76ms | 6.18건/초 |
| 응답에 기록된 모델 forward | 128.26ms | 227.76ms | 156.95ms | — |

이 HTTP 값에는 multipart 전송, JPEG 디코딩, 전처리, 모델 실행과 응답이 포함된다. 같은 합성 이미지를 반복했으므로 실제 촬영 데이터의 크기와 내용에 따른 성능은 아직 확인하지 않았다. 공용 Compose의 Inference와 Backend가 현재 placeholder이므로 이 측정값을 전체 배포 경로의 500ms 승인 근거로 사용하지 않는다.

같은 시험을 다시 실행하려면 프로젝트 루트의 Windows PowerShell에서 아래 명령을 사용한다. `scripts/benchmark_inference_http.py` 실행 환경에는 Pillow가 필요하다. 출력 파일명은 실행마다 새로 지정한다.

```powershell
docker run -d --name cqc-inference-http-benchmark -p 127.0.0.1:18001:8001 -e OMP_NUM_THREADS=1 -e MKL_NUM_THREADS=1 --mount 'type=volume,source=jenkins_home,target=/jenkins,readonly' cqc-inference-acceptance python -m src.inference.api --model-dir /jenkins/workspace/CQC-CICD/models/cqc-apple-separate12-focal-v2-candidate --device cpu --host 0.0.0.0 --port 8001
Invoke-RestMethod http://127.0.0.1:18001/health
.\.venv\Scripts\python.exe scripts\benchmark_inference_http.py --output outputs\i7-4790-acceptance\new-run\inference-http.json
docker rm -f cqc-inference-http-benchmark
```

### Backend→Inference 실제 HTTP 연결 예비 측정

Backend에 선택형 `HttpInferenceClient`를 추가했다. 기본값은 기존 Mock이며, `INFERENCE_CLIENT_MODE=http`와 `INFERENCE_URL`을 설정했을 때 실제 `/v1/predict`에 multipart 요청을 보낸다. 같은 i7-4790 장비에서 Backend를 Windows 프로세스(포트 18000), Inference를 별도 Docker 컨테이너(포트 18001)로 실행하고 호스트→Backend→Inference→Backend 응답을 측정했다. [결과 JSON](results/i7-4790-backend-inference-http-20260923.json)은 준비 실행 10회 뒤 순차 요청 100회다.

| 측정 범위 | 평균 | 최대 | p95 | 처리량 |
|---|---:|---:|---:|---:|
| 호스트→Backend→Inference→Backend 응답 | 182.85ms | 291.96ms | 244.07ms | 5.47건/초 |
| 응답에 기록된 모델 forward | 134.76ms | 230.64ms | 180.95ms | — |

이 예비 결과는 12장의 동일 합성 JPEG와 Mock Virtual Control을 사용한다. Backend가 Windows 프로세스이므로 공용 Compose의 컨테이너 간 네트워크, DB 저장, simulator 입력, 실제 촬영 파일 및 동시 요청은 포함하지 않는다. 따라서 전체 운영 수용시험은 여전히 남아 있다.

재현 시 Inference 컨테이너를 위 명령으로 기동한 뒤 다른 PowerShell에서 아래 명령을 실행한다. Backend가 준비되면 별도 PowerShell에서 벤치마크를 실행한다.

```powershell
$env:INFERENCE_CLIENT_MODE='http'
$env:INFERENCE_URL='http://127.0.0.1:18001/v1/predict'
$env:APP_PORT='18000'
.\.venv\Scripts\python.exe -m src.api.main
```

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_inference_http.py --url http://127.0.0.1:18000/v1/inspections --output outputs\i7-4790-acceptance\new-run\backend-inference-http.json
```

### 별도 Compose의 컨테이너 간 HTTP 측정

`Dockerfile.backend`와 `compose.integration.yaml`로 실제 Backend와 Inference를 같은 Docker 네트워크에서 실행했다. 모델 패키지를 읽기 전용으로 마운트했고 두 서비스의 healthcheck가 통과한 상태에서 호스트→Backend 컨테이너→Inference 컨테이너→Backend 응답을 100회 측정했다. [결과 JSON](results/i7-4790-compose-backend-inference-http-20260923.json)은 준비 실행 10회를 제외한 값이다.

| 측정 범위 | 평균 | 최대 | p95 | 처리량 |
|---|---:|---:|---:|---:|
| 별도 Compose의 Backend→Inference 경로 | 166.61ms | 235.42ms | 205.76ms | 6.00건/초 |
| 응답에 기록된 모델 forward | 128.34ms | 195.51ms | 166.85ms | — |

재현하려면 모델 패키지 경로를 지정하고 이미지가 없으면 `Dockerfile.inference`로 `cqc-inference-acceptance:latest`를 먼저 빌드한다. 아래 PowerShell 명령은 공용 `compose.yaml`을 변경하지 않는다.

```powershell
docker build -f Dockerfile.inference -t cqc-inference-acceptance .
$env:INFERENCE_MODEL_DIR='C:\CQC\models\cqc-apple-separate12-focal-v2-candidate'
docker compose -p cqc-integration -f compose.integration.yaml up -d --build
.\.venv\Scripts\python.exe scripts\benchmark_inference_http.py --url http://127.0.0.1:18000/v1/inspections --output outputs\i7-4790-acceptance\new-run\compose-backend-inference-http.json
docker compose -p cqc-integration -f compose.integration.yaml down
```

이는 고정 합성 JPEG, Mock Virtual Control, 순차 요청의 예비 통합 측정이다. 공용 Compose 배포, DB 저장, simulator, 실제 촬영 이미지와 동시 요청의 운영 수용시험은 별도로 진행한다.
