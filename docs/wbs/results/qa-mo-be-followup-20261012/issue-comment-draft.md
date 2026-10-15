**[MO] 결과 — 잔여 Backend QA 배포·기존 증거·전용 환경 준비 (2026-10-12)**

## 한 일

- [BE 잔여 QA 협조 요청](https://github.com/yuudong123/CQC/issues/103#issuecomment-6119487084)의 MO 요청 항목 대조
- 최신 성공 빌드·실행 이미지·Backend 파일·OPS-13 수정 포함 근거 확인
- 측정·서버 QA·새 빌드 없음 사용자 확인 후 날짜 없는 통계 CSV 읽기 검증
- SIM-03·12 및 SIM-06 기존 원자료 조사·부족 조건 분리
- 전용 Simulator·Backend·MySQL 구성·후속 절차·SIM-05 요청표 작성
- 전달자료 `feat/mlops` 커밋·푸시 완료

## 결과 (수치)

### OPS-13 배포 및 읽기 확인

- Jenkins **#143 SUCCESS**, 완료 **2026-10-12 14:37:57.400 KST** 확인
- 실제 배포 기준 SHA: `0094807a159e4bedadd2700fd689b3c848ee803f`
- OPS-13 수정 `ee2987fb820e2fa1654184edbfdfddffaf9d29d4` 포함 확인
- 실행 이미지와 #143 빌드 digest **4/4 일치**, 실제 Backend 파일과 checkout 파일의 바이트·SHA-256 일치 확인
- 읽기 확인: **16:25:13~16:25:15 KST**, 날짜 없는 CSV·동일 snapshotAt 통계 JSON GET 각 1회
- `CULTIVAR_SUSPECT`·`QUALITY_SUSPECT`·`OTHER` 각각 정확히 **1행**, 모두 **0** 출력 및 JSON 대조
- today·품종·등급·bin 집계, 재검사율·평균 추론시간, 헤더·BOM·CRLF·모든 칸 따옴표 포함 **18개 검토 항목 충족**
- 기존 기간/분 단위 CSV 증거 재사용 유지, 신규 검사·설정 변경 없음
- Jenkins 실시간 queue API는 403으로 직접 확인 불가, 사용자 일정 확인 및 조회 후 #143 유지 근거 분리

### SIM-03·12 기존 증거

- 10/07 E2 재시작 후 `intervalMs=2000`·`concurrency=1`·장애 초기화·정상 실행 근거 확보
- 재시작 전 마지막 묶음 index 20 → 재시작 후 **21·22·23** 이어 재생 근거 확보
- SIM-03 정지 10초·최대 1건·unhealthy·수동 재개와 SIM-12 3000/1000ms 각 60초 조건은 추가 증거 필요
- 현재 #143과 다른 회차로 구분 보존

### SIM-06 기존 장애 증거

- 10/06 11:32 상세 E2 회차의 지정 검사 ID·NEXT 해제·후속 정상 저장 기록 추가 확보
- 추론 timeout/error 검사별 이미지 개수 **12장** 기록 확보
- 제어 거부 **2회**, 무응답·실패 각각 **1회**의 제어 시도 개수 기록 확보
- 개별 이미지 ID 목록·control_attempts 전체 필드·성공 bin 통계 제외·DB_ERROR 검사 ID와 실패 로그 연결은 추가 확보 미완료
- 요약 수치만으로 전체 SIM-06 PASS 확대 없음

### 전용 환경

- 기존 데이터셋 **869묶음**, 첫·마지막 묶음 이미지 각각 **12장** 및 index/CSV 해시 확인
- `cqc-mo103-e2-20261012` 전용 DB·position·이미지·로그·내부 네트워크 구성 작성
- 현재 배포 이미지 ID 고정, build/pull 없음, 데이터셋 RO 공유 확인
- 루프백 28000/28001/28002 미사용 및 Compose 정적 검증 **12개 충족**
- 현재 `SIMULATOR_AUTO_START=false` 기능 없음 확인, 정지 기동 필요 여부와 기동 후 정지 대안 협의 필요
- 실제 기동·재시작·DB 중단·장시간 시험은 미실행, BE와 환경·일정 확정 필요

## 다른 파트 영향

- BE: OPS-13 최종 판정 및 기존 증거의 항목별 재사용 범위 검토 가능
- BE·MO: SIM-03·04·05·06·07·09·11·12의 전용 환경·실행 순서·원자료 형식 협의 가능
- FE: SIM-07 ALL 웹 경고 캡처·영상과 회차 연결 필요
- DM: #65 정상 100건 재측정과 전용 시험의 실행 시간 분리 필요

## 남은 일

- [ ] BE의 OPS-13 최종 판정·QA 기록표 반영
- [ ] BE와 실제 E2 또는 새 격리 환경·정지 기동 방식·실행 일정 확정
- [ ] 부족 조건에 한정한 새 회차 실행 및 검사별 원자료 확보
- [ ] FE 웹 경고 캡처·회차 연결
- [ ] #65 기존 공식 FAIL 유지 및 재측정 일정 별도 협의

## 관련 PR / 문서

- [BE 협조 요청](https://github.com/yuudong123/CQC/issues/103#issuecomment-6119487084)
- [현재 배포 소스](https://github.com/yuudong123/CQC/commit/0094807a159e4bedadd2700fd689b3c848ee803f)
- [OPS-13 수정](https://github.com/yuudong123/CQC/commit/ee2987fb820e2fa1654184edbfdfddffaf9d29d4)
- [전달자료 전체](https://github.com/yuudong123/CQC/tree/feat/mlops/docs/wbs/results/qa-mo-be-followup-20261012)
- [결과 보고서](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-be-followup-20261012/README.md)
- [배포 확인 증거](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-be-followup-20261012/deployment-provenance.json)
- [OPS-13 CSV 대조 결과](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-be-followup-20261012/ops13-review.json)
- [기존 장애 증거·부족 조건](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-be-followup-20261012/sim06-evidence-review.json)
- [전용 환경 구성 검증](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-be-followup-20261012/isolated-preflight.json)
- [후속 실행 절차·일정안](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-be-followup-20261012/execution-plan.md)
- 전달 ZIP: `qa-mo-be-followup-20261012.zip` — 필요 시 별도 첨부
- 핵심 파일: `README.md`, `deployment-provenance.json`, `ops13-review.json`, `historical-detailed-fault-evidence.json`, `sim06-evidence-review.json`, `isolated-preflight.json`, `execution-plan.md`
