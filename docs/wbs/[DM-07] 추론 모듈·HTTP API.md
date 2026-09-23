# [DM-07] 추론 모듈·HTTP API

## 목적

승인된 다각도 모델을 HTTP로 제공하고 품종·품질 확률과 신뢰도, 모델 버전을 백엔드에 전달한다.

## 구현 완료

- `src/inference/predictor.py`: 모델 패키지 로딩, 동일 전처리, 마스크 패딩, 확률·신뢰도 반환
- `src/inference/api.py`: `/health`, `/v1/predict` FastAPI 어댑터
- `src/inference/README.md`: 입력·응답과 책임 범위
- 가짜 예측기를 사용한 `/health`, multipart 반복 이미지, 415 오류 HTTP 계약 테스트 완료
- PNG/JPEG multipart 입력만 허용하고 빈 그룹을 거부한다.
- HTTP 입력 장수 초과는 413으로 거부하고 부족하면 0 텐서와 마스크로 패딩한다. Predictor 내부의 균등 선택은 공개 HTTP 계약이 아니다.
- bin, 재검사, DB 정책은 포함하지 않는다.

## 실제 패키지 검증

- `cqc-apple-separate12-v1.0.0` 패키지 체크섬 검증과 CPU 로딩 성공
- validation 그룹의 실제 PNG 12장을 multipart로 보내 `/health`, `/v1/predict` HTTP 200 확인
- 단일 호출 모델 추론시간 45.8ms
- 최대 12파일·24MiB를 넘으면 HTTP 413 반환
- PNG/JPEG 외 형식은 HTTP 415, 빈 요청·손상 이미지는 HTTP 422

목표 i7-4790의 500ms 수용시험만 남는다. 최종 Test 품질 Macro F1이 승인 기준에 미달했으므로 현재 패키지는 기능 검증용이며 승인 모델이 아니다.

## 2026-09-23: 후속 후보 HTTP 계약·배포 인계

- 후보 `cqc-apple-separate12-focal-v2-candidate`를 로컬에도 수집했다. 모델 바이너리는 Git 제외를 유지한다.
- `scripts/verify_inference_http.py`가 임시 loopback Uvicorn 서버를 실행하고 종료 시 해당 자식 프로세스만 정리한다.
- 합성 PNG 12장 정상 200, 누락 대응 8장 200, 13장 413, metadata 개수 불일치 422, 잘못된 MIME 415, 손상 이미지 422를 실제 HTTP로 확인했다.
- `origin/dev`의 `2490cfe7f9a75fcbd75acb36ccf99aad758e45d9`에서 추출한 변경 없는 Backend `InferenceResponse`로 정상 응답 검증을 통과했다. 백엔드 소스는 수정하지 않았다.
- 증거: `docs/wbs/results/candidate-v2-http.json`. 합성 입력·노트북 단발 측정이며 실사과 정확도나 i7-4790 성능 승인 근거가 아니다. 손상 이미지 첫 호출은 약 2.6초로 500ms를 초과했다. 정상 요청만으로 오류 경로 지연을 보장하면 안 된다.
- 실제 Backend Client는 Mock 상태이므로 Backend 검사→Inference→제어·저장 전체 통합과 transport timeout 검증은 남아 있다.

### 독립 배포 슬롯

팀 공용 `compose.yaml`, Jenkinsfile은 수정하지 않는다. `compose.inference.yaml`은 별도 프로젝트 이름으로 실행한다. 모델은 읽기 전용이고 localhost에만 포트를 연다. 후보 사용은 통합 시험 목적이며 운영 승인이 아니다.

```powershell
$env:INFERENCE_MODEL_DIR = (Resolve-Path models/cqc-apple-separate12-focal-v2-candidate).Path
$env:INFERENCE_PORT = '8001'
docker compose -p cqc-inference-check -f compose.inference.yaml config --quiet
docker compose -p cqc-inference-check -f compose.inference.yaml up -d --build
docker compose -p cqc-inference-check -f compose.inference.yaml ps
Invoke-RestMethod http://127.0.0.1:8001/health
docker compose -p cqc-inference-check -f compose.inference.yaml logs --tail 50
```

시험 종료는 같은 프로젝트 이름·파일로 `down`한다. 공용 스택은 내리지 않는다. 모델 교체는 이전 경로를 기록한 뒤 환경변수 경로를 바꾸고 `up -d --force-recreate`한다. health 응답의 버전을 확인하고 실패하면 이전 경로로 복원 후 다시 생성한다. 체크섬 불일치 패키지는 수정해 우회하지 않는다.

로컬 Docker CLI는 없다. 집 PC Docker Engine 29.7.2에서 별도 Compose 설정 검사·이미지 빌드·기동 및 healthy 상태를 확인했다. CPU 전용 torch 2.11.0+cpu / torchvision 0.26.0+cpu를 사용하도록 Dockerfile을 수정해 불필요한 CUDA 설치를 제외했다.

- 시험 주소: 집 PC의 `127.0.0.1:18081`, 별도 프로젝트 `cqc-inference-check`.
- `/health`에서 후보 버전·CPU·12장 확인, 합성 PNG 12장 `/v1/predict` 요청 성공.
- `inspection_id=docker-smoke`, `used_frame_count=12`, 모델 추론시간 약 56.2ms. 단발 합성 입력이며 성능 수용시험 결과가 아니다.
- 이미지 ID: `sha256:1e25141b6c8417fca3bef095a4de66397ed2f7349ff304a0fd9402b400e8144f`.
- 시험 후 해당 프로젝트의 컨테이너·네트워크만 제거했다. 이미지와 모델 패키지는 보존했고 공용 서비스·운영 배포는 변경하지 않았다.
- 로컬 회귀 테스트를 최종 학습 설정까지 포함해 재실행하여 16개 통과, Python 문법·diff 공백 검사 통과.

남은 외부 의존 작업은 Backend 실제 HTTP Client 및 전체 검사 흐름, 신규 독립 평가 데이터, i7-4790 수용시험이다. 패키지 생성·컨테이너 정상 기동은 품질 승인을 의미하지 않는다.

### HTTP 시험 재현

```powershell
python -m scripts.verify_inference_http --package models/cqc-apple-separate12-focal-v2-candidate --output outputs/inference-http-new.json
```

Backend 계약도 검사하려면 원본 코드 스냅샷 루트를 `--backend-root`로, 커밋을 `--backend-revision`으로 전달한다. 결과 파일은 덮어쓰지 않으므로 매 실행에 새 경로를 지정한다. 이 도구는 테스트 환경의 `httpx`, Pillow, 추론 실행 의존성을 사용한다.
