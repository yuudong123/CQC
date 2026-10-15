# BE 후속 시험용 환경·절차·증거 계획

이 문서는 준비된 절차이며 실제 시험 결과가 아니다. [BE 협조 요청](https://github.com/yuudong123/CQC/issues/103#issuecomment-6119487084)에 답변하기 위한 구성안이다. 실제 시험 회차·사용 환경은 BE와 확정하며, #65 정상 100건 측정과 시간을 분리한다.

## 준비된 전용 구성

- 프로젝트: `cqc-mo103-e2-20261012`
- 파일: `isolated-compose.json`, 빈 환경 파일: `empty.env`
- Backend `127.0.0.1:28000`, Inference `127.0.0.1:28001`, Simulator `127.0.0.1:28002`
- MySQL은 외부 포트 미공개, 서비스명 `mysql`, 전용 DB `cqc_mo103_qa`
- Backend·Inference·Simulator·MySQL 이미지는 현재 E1의 이미지 ID로 고정, build/pull 없음
- MySQL·position·장애 이미지·로그는 모두 새 프로젝트의 전용 볼륨
- 기존 `cqc_simulator_dataset`만 읽기 전용 공유
- 내부 네트워크, 전용 임시 인증정보 사용. `CQC_QA_MYSQL_PASSWORD`, `CQC_QA_MYSQL_ROOT_PASSWORD`, `CQC_QA_FAULT_TOKEN`은 실행 환경에서 별도 설정. 값은 증거 파일에 기록하지 않음
- 비밀번호는 DB URL에 그대로 사용되므로 URL-safe 값으로 생성
- CPU·메모리·디스크는 E1과 같은 Docker 호스트에서 공유되므로 장시간 실행과 정상 100건 측정은 시간 분리 필요
- 실제 컨테이너 기동·볼륨 생성·runtime health 검증은 미실행. `docker compose config`의 정적 검증 12개만 통과

현재 Simulator에는 `SIMULATOR_AUTO_START=false` 옵션이 없다. 유효 데이터셋으로 기동하면 자동으로 입력을 시작한다. 정지 기동이 필수라면 기능 반영을 BE와 따로 협의해야 한다. 이번 구성은 자동 입력이 **새 전용 DB에만** 들어가도록 분리했으며, 기동 후 기존 설정 API로 정지한 다음 SIM-04·05를 진행하는 대안도 협의 대상으로 둔다.

## 회차 시작 전

1. #65 정상 100건 측정·다른 서버 QA·Jenkins 빌드/대기열이 없는 시간 확정 및 시작 공지
2. E1 컨테이너 ID·이미지·health와 자원 상태 기록
3. 예정 프로젝트 이름·포트·새 볼륨이 기존 업무/E2/AUTO-02 자원과 겹치지 않는지 재확인
4. 전용 인증정보 설정 후 `docker compose --env-file empty.env -p cqc-mo103-e2-20261012 -f isolated-compose.json config` 재검증. 출력을 공유할 때 인증정보 제거
5. 합의된 회차에서만 MySQL·Inference·Backend 기동, DB migration·13개 mapping·모델 health·체크섬 확인
6. Simulator 기동 후 필요하면 정상 전용 입력 기준선 확보·정지. Backend `/health`, Inference `/health`, Simulator `/state` 및 Docker health 각각 기록

Simulator를 정상적으로 정지하면 `/health` 503 및 Docker unhealthy가 예상된다. 이때 준비·revision 확인은 `/state`로 수행한다. unhealthy 자체를 새 장애로 판단하지 않는다.

## 항목별 실행 및 원자료

| 항목 | 절차 | 보존할 원자료 |
|---|---|---|
| SIM-03 | running=false PUT → 10초 동안 2초 간격 기록 → running=true PUT | 응답 200·R+1·stopped, 시점별 검사 수·진행 중 job, 최대 1건 추가, Docker unhealthy, 정지 전·재개 첫 DB source_reference 및 dataset 순번 |
| SIM-04 | 실제 R 기록 → concurrency=2 PUT → 같은 R로 concurrency=1 재요청 → 최신 R로 기존 설정 복원 | 첫 200/R+1, 두 번째 409/REVISION_CONFLICT, 실제 Simulator GET /state 및 설정 유지·복원 |
| SIM-05 | `sim05-request-matrix.json`의 10종을 순서대로 요청 | 각 422/INVALID_SETTINGS, 요청 전후 실제 Simulator revision·설정 불변, Cache-Control |
| SIM-06 부족분 | 기존 자료가 부족한 필드만 합의된 새 회차에서 확인 | timeout/error 검사별 이미지 ID 12개·metadata·해시, control_attempts 순서·bin·상태, 무응답 전후 성공 bin 집계, DB_ERROR 검사 ID와 저장 실패 로그·후속 정상 저장 |
| SIM-07 | 두 장애를 ALL로 적용하고 10초 관찰 후 faults=[] 복원 | 적용 전후 상태·revision, 기간 내 모든 검사 ID·faults·시간 초과 기록, FE의 웹 경고 캡처 연결 |
| SIM-09 | **전용 프로젝트 MySQL만** 20초 중단 → 복구 후 30초 관찰 | 중단/복구 시각, 실제 입력 지속·정상 bin 판정·저장 실패 로그, 복구 후 DB 저장 증가, Backend/Simulator 컨테이너 ID·StartedAt 불변 |
| SIM-11 | 전용 데이터셋 869묶음의 전체 순환 관찰 | index/CSV 해시, 전체 source_reference 순서, 경계 전후 첫/마지막 묶음과 새 inspection_id, 대기열·자원·종료 시각 |
| SIM-12 | intervalMs=3000 60초 → 1000 60초 → Simulator 재시작 | 구간별 DB 완료 시각·간격 중앙값·처리량·job 수/대기열·처리시간, PUT 응답·revision, 재시작 후 2000 기본값·faults/concurrency 초기화 |

SIM-11은 현재 실제 이미지가 지원하는 concurrency 1·2·4 범위에서 QA 원문의 4 조건을 사용한다. 충분한 주기 관찰 시간이 필요하며 중간 종료한 회차를 전체 869묶음 통과로 기록하지 않는다.

## 일정안

- OPS-13 날짜 없는 CSV 읽기 확인: **16:25:13~16:25:15 KST 완료**, 신규 검사·설정 변경 없음
- 후속 경량 회차: 환경·health 확인 후 SIM-03·04·05를 약 5~10분 창으로 협의
- SIM-12: 별도 5분 이상 창(60초×2 및 재시작 확인 포함)
- SIM-06 부족분·SIM-07·SIM-09: BE·FE 참여와 장애/DB 중단 창을 별도로 협의
- SIM-11: 전체 순환이 확인될 때까지의 장시간 전용 창을 별도로 확보

위 시간은 예약·확정이 아닌 협의안이다. 실제 E2를 연결할지 새 격리 구성을 사용할지 먼저 확정하고, 다른 환경의 기존 증거와 신규 회차를 분리한다.

## 종료 및 정리

1. 설정을 정상 기본값으로 복원하고 E1 정상 상태·배포 동일성 재확인
2. 새 전용 회차의 DB·이미지·position·로그·컨테이너 출처를 먼저 export하고 해시 기록
3. 현재 E2/AUTO-02 잔여 기록 및 업무 DB는 유지. 프로젝트 종료가 필요하면 생성한 프로젝트 이름을 확인한 뒤 컨테이너만 중지하고 볼륨은 증거 보존 기간 동안 유지
4. 결과를 BE에 전달하고 최종 QA 판정 및 기록표 반영은 BE 검토 후 진행
