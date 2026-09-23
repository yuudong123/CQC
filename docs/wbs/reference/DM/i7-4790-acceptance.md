# i7-4790 모델 성능 수용시험

## 목적

WBS의 DM-06·DM-08 완료 조건인 Intel Core i7-4790, RAM 16GB 환경의 평균·최대·p95 추론시간과 초당 처리량을 동일 명령으로 측정한다.

## 안전 조건

- CPU 이름에 `i7-4790`이 없으면 실행을 거부한다.
- 물리 RAM이 15GiB 미만이면 실행을 거부한다.
- 고정 Test가 아닌 validation 입력으로 모델 추론시간만 측정한다.
- 체크포인트 SHA-256과 실제 CPU·RAM을 결과에 함께 기록한다.
- i7-14700F 등 다른 CPU 결과를 목표 장비 승인값으로 사용할 수 없다.

## 실행

저장소 루트의 가상환경과 원본 데이터가 준비된 i7-4790 PC에서 실행한다.

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

스크립트 준비만 완료했다. 현재 연결된 집 PC는 i7-14700F이므로 이 시험을 실행하지 않는다.
