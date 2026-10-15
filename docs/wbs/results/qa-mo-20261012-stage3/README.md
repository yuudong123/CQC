# ALL-04 3단계 — 정상 100건 측정 결과 및 실패 증거

2026-10-12 정상 100건 관찰 완료. **QA-SIM-02·QA-SIM-13 기준 미충족**. 실행자 홍유나. 최대 완료 간격 및 SIM-02 p90 초과 원인 미확정.

## 기준선과 측정 시각

- 배포: Jenkins `CQC-CICD #139` / SHA `b5f1995a7e4a494ef116d62819b169fa9d5a788e`
- [2단계 배포 확인 증거](../qa-mo-20261012-stage2/README.md): 실행 이미지↔빌드 digest 4/4 일치
- 관찰 시작 **09:46:15.465 KST**, 첫 완료 **09:46:17.031 KST**, 마지막 완료 **09:49:46.616 KST**
- Jenkins 감시 12회 모두 #139 유지, 새 빌드 겹침 없음 확인
- 측정 전후 4개 서비스 컨테이너·이미지 ID 동일 및 healthy 유지
- Jenkins 실시간 대기열 직접 조회는 인증으로 차단. 실행·대기 작업 없음은 실행 직전 사용자 확인. 저장된 queue.xml은 별도 과거 스냅샷으로 구분.

## 정상 100건 결과

| 항목 | 실측 | 기준 | 결과 |
|---|---:|---|---|
| 완료 간격 중앙값 | 1.995초 | 2.0±0.1초 | 충족 |
| 최대 완료 간격 | **5.755초** | 4초 미만 | **미충족** |
| 처리량 | 0.472362건/초 | 0.5±0.05건/초 | 충족 |
| 재검사 | 9/100건 (9%) | 20% 이하 | 충족 |
| 시간 초과·추론 오류 | 0건 | 0건 | 충족 |
| QA-SIM-02 p90 | **2.5258초** | 2.2초 이하 | **미충족** |

최대 간격 발생 구간: **09:49:30.139~09:49:35.894 KST**. 원인 미확정. 새 빌드가 없다는 결과를 다른 부하도 없었다는 증명으로 해석하지 않음. 이번 실패 기록 유지 및 DM 최종 판정·지연 구간 분석 필요.

측정은 정상 운영의 저장 이력 100건을 읽기 전용으로 관찰한 결과. 장애 주입·설정 변경·이미지 삭제 미실행. 이 결과만으로 저장되지 않은 요청의 부재나 전체 장애·복구 시험의 통과를 증명하지 않음.

## 회차별 증거

### 정상 100건 재실행: normal-100-run/

| 파일 | 내용 |
|---|---|
| [normal-100.json](normal-100-run/normal-100.json) | 정상 100건 원자료와 측정 수치 |
| [all04-rows.md](normal-100-run/all04-rows.md) | 자동 생성 QA 기록표 |
| [results.json](normal-100-run/results.json) | 케이스별 자동 판정 및 부분 검증 범위 |
| [acceptance-review.json](normal-100-run/acceptance-review.json) | 확정 기준 대조·최대 간격 구간·배포 전후 확인 |
| [jenkins-build-monitor.json](normal-100-run/jenkins-build-monitor.json) | 측정 중 빌드 감시 12회 원자료 |
| [preflight.json](normal-100-run/preflight.json) | 측정 전 컨테이너·이미지 대조 및 사용자 대기열 확인 근거 |
| [deployment-provenance.json](normal-100-run/deployment-provenance.json) | #139 배포 출처 확인 원자료 사본 |
| [run.json](normal-100-run/run.json) | 실제 실행 시각·로컬 소스 SHA·dirty 상태 |
| [runner-and-deployment.json](normal-100-run/runner-and-deployment.json) | 로컬 실행 스크립트 SHA-256 및 배포 SHA 구분 |

실제 실행 스크립트의 로컬 HEAD는 `381edd07991d76c223ffd5cdc67f3a9e2ea9a37b`, 배포 SHA는 위 #139 SHA. 자동 결과 원문의 과거 `제안 기준: 10-08 합의 전 예비 측정` 및 `deployed SHA unverified` 문구는 변경하지 않고 보존. 10-07 확정 기준과 별도 이미지↔SHA 증거를 `acceptance-review.json`에서 연결. 부분 검증 행은 전체 QA 통과로 전환하지 않음.

### 첫 실행 차단: initial-blocked-run/

- 실행 **09:44:10~09:44:30 KST**. 모델·Backend 상태 및 체크섬 확인 후 snapshot 조회 20초 timeout으로 차단. 정상 100건 관찰 미진입.
- [results.json](initial-blocked-run/results.json)·[all04-rows.md](initial-blocked-run/all04-rows.md)·[run.json](initial-blocked-run/run.json) 원문 보존.
- [후속 HTTP 진단](initial-blocked-run/http-diagnostic-summary.json): snapshot HTTP 200 / 1.402초 확인 후 새 회차로 재실행. 진단의 history `pageSize=5` 요청 422는 진단 입력으로 발생한 응답이며 정상 100건 QA 실패 항목으로 집계하지 않음.
- [빌드 감시](initial-blocked-run/jenkins-build-monitor.json)와 [Backend health 응답](initial-blocked-run/backend-health-diagnostic.json) 보존.

## 검증과 공유

- 원본: `outputs/mo09-acceptance/20261012-094559/` 및 `outputs/mo09-acceptance/20261012-094408/`.
- 공유한 원자료 파일 15개는 원본 바이트 그대로 복사. 전체 상태 snapshot 진단 응답은 포함하지 않음.
- 정상 100건 원자료로 중앙값·p90·최대 간격·처리량·재검사·오류 건수 재계산 대조.
- [manifest.sha256](manifest.sha256)에 이 폴더의 파일별 SHA-256 보존. Git 저장 시 원본 개행 유지 설정 적용.
- 추가 제품 코드 수정·재측정·배포 미실행.

## 후속 작업

- 최대 간격·p90 초과 구간 원인 분석, 실패 이슈 등록 및 QA 기록표 6.4 반영
- 원인 확인 후 재측정 조건·일정 협의
- BE·MO 격리 E2 장애 5종·순환 삭제·재시작 복구 검증
- DM 최종 수용 판정 및 전체 결과 취합

[최종 수용시험 #65](https://github.com/yuudong123/CQC/issues/65)
