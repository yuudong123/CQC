# MO SIM-03·12 Docker 보완 증거 (2026-10-14)

**SIM-03의 실제 Docker unhealthy 전환과 SIM-12의 Compose 재시작 후 2000ms 기본값 복원을 확인했다.** 기존 BE 로컬 시험과 다른 회차이며 공식 QA 전체 PASS·37/44 집계 변경은 하지 않는다.

## 실행 기준

- 요청: [BE의 Docker 보완 및 환경 인정 범위 협조 요청](https://github.com/yuudong123/CQC/issues/103#issuecomment-6141661792).
- 실행자: 홍유나(Codex). 보완 시험: **2026-10-14T09:41:24.715897+09:00 ~ 2026-10-14T09:43:05.254233+09:00 KST**. 정지 요청·준비 관찰은 앞선 기동 단계에서 수행했으며 각 파일의 실제 시각을 따른다.
- Jenkins **#155 SUCCESS**, 소스 `9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0`. Backend·Inference·Simulator 이미지 digest 3/3 일치. [배포 출처](deployment-provenance.json).
- `cqc-mo103-sim0312-20261014-093721`: 신규 전용 MySQL·position·검수 이미지·서비스 로그·internal network. 데이터셋만 읽기 전용 공유하고 호스트 포트를 열지 않았다. [Compose](isolated-compose.json).
- Simulator·Backend·Inference의 Docker healthcheck는 공용 배포 설정과 동일하다. 실제 컨테이너의 설정 일치를 검증했고 주기·재시도 횟수를 변경하지 않았다. 새 MySQL에는 초기화용 TCP SELECT 1 확인·600초 유예를 적용했고 보완 시험 판정 대상이 아니다. HTTP는 전용 Backend 컨테이너에서 실제 호출했다.
- [소스 대조](source-attestation.json): 실행 중 Simulator·Backend의 Python 소스 68개가 Jenkins 소스 및 BE 로컬 실행 기준 `f8a2002`의 해당 파일과 모두 일치한다. 이 대조는 관련 소스에 한하며 라이브러리·모델·자원·환경 동등성을 증명하지 않는다.

## 관찰 결과

| 보완 범위 | 확인 항목 | 판정 한계 |
|---|---|---|
| SIM-03-Docker-supplement | 12/12 충족 | 해당 보완 조건만 확인 |
| SIM-12-Docker-restart-supplement | 12/12 충족 | 해당 보완 조건만 확인 |

### SIM-03 Docker unhealthy

- 정지 HTTP 200, revision 0→1, 실제 Simulator running=false·status=stopped와 Backend snapshot 일치.
- HTTP `/health` 503은 별도로 기록하고, **`docker inspect`의 Health.Status=unhealthy 및 실제 healthcheck 실패 로그**를 확인했다. [Docker 관찰](sim03-docker-unhealthy-observations.json) · [조건 대조](sim03-checks.json).
- drain 이후 검사 수 **4건**, jobs 0. 15.857초 동안 6회 관찰해 검사 수 불변을 확인했다. [정지 관찰](sim03-stopped-samples.json).
- 재개 HTTP 200, revision 1→2, Docker healthy 복귀와 검사 수 **10건으로 증가**를 확인했다.
- 진행 중 요청을 의도적으로 만들거나 재개 첫 묶음의 source_reference를 다시 검증하지 않았다. 기존 BE 로컬 기능 증거를 이번 Docker 회차와 합쳐 한 회차처럼 기록하지 않는다.

### SIM-12 Docker 재시작 기본값 복원

- 준비용 live 변경 HTTP 200, revision 2→3, running=true·intervalMs=1000 확인.
- **같은 전용 Simulator 컨테이너에 `docker compose restart --timeout 20 simulator`를 실행**해 exit 0을 확인했다. container ID 동일·StartedAt 변경을 기록했다. [재시작 명령 결과](sim12-compose-restart.json) · [전](sim12-docker-before-restart.json) · [후](sim12-docker-after-restart-observations.json).
- 재시작 전 실제 intervalMs=1000, 재시작 후 **intervalMs=2000·revision=0·running=true**, concurrency=1·faults=[]·scope=ALL. Backend snapshot도 일치하고 Docker healthy였다. [조건 대조](sim12-checks.json).
- 환경변수 `SIMULATOR_INTERVAL_MS=2000`을 별도 저장했다. 3000ms·1000ms의 1분 정량 측정은 이번에 반복하지 않았다. 기존 1000ms 간격 1.1110초와 명목 1.000초 불일치는 그대로 남긴다.

## MO 검토 의견 및 팀 확인 항목

1. **WSL 증거 인정 범위 제안:** 소스·격리 자원·원자료 출처·기대값이 확인된 항목은 해당 로컬 환경의 기능 증거로 검수한다. Docker unhealthy와 Compose restart처럼 환경 자체가 기대값인 조건은 실제 Docker 증거를 별도로 연결한다. 이번 소스 대조와 두 보완 결과를 BE 검수에 제공하되 E2 대체 인정·공식 판정은 BE·DM 공동 확인 후 결정한다.
2. **SIM-07·11:** 기존 WSL 기능 결과만으로 실제 웹 경고나 Docker 실행 확인을 완료 처리하지 않는다. SIM-07의 실제 상단 경고는 FE 전용 웹 확인이 남아 있다. 관련 원자료는 BE가 보존하고 아직 미Push라고 밝혔으므로 이번 문서에서 그 파일·해시를 직접 재검수했다고 주장하지 않는다.
3. **SIM-12 처리시간 정의:** 실행 소스상 `send()` worker는 HTTP 응답 후 position 저장까지 완료한다. 이미지 묶음 준비(`dataset.load`)는 worker 생성 전에 수행된다. HTTP 왕복·worker 점유시간·연속 요청 시작 간격은 서로 다른 측정 구간이다. [실행 중 runner 원문](deployed-simulator-source.py). 기존 약 0.111초 차이의 원인은 이번에 특정하지 않았다.
4. **팀 결정 요청:** QA의 '한 건 처리시간'에 포함할 구간과 1000ms 정량 기준을 명시한다. 3000ms의 ±0.1초를 가져오거나 기존 결과를 사후 PASS로 바꾸지 않는다. 합의 전 기존 불일치·보류를 유지한다. [#103 답글 초안](issue-comment-draft.md).

## 종료와 영향 확인

- 마지막 설정은 정지·intervalMs=2000·concurrency=1·faults=[]·scope=ALL. jobs 0 및 검사 수 14건이 3회 연속 같은지 확인 후 DB dump·position·로그를 보존했다.
- 전용 컨테이너 **4개 모두 exited**, 전용 볼륨은 증거와 함께 보존. [종료 상태](qa-stopped-runtime.json), [종료 코드](qa-stop-exit-codes.json): simulator-1: 0 (OOMKilled=False), backend-1: 137 (OOMKilled=False), mysql-1: 0 (OOMKilled=False), inference-1: 0 (OOMKilled=False).
- exit 137이 있으면 정상 종료로 확대하지 않는다. 종료 지연은 보완 시험 후 정리 단계의 관찰이며 원인 분석은 별도 범위다.
- 공용 E1 7개 서비스의 ID·이미지·StartedAt·상태·health 전후 동일 및 모두 healthy. [전](e1-before.json) · [후](e1-after.json). 호스트 CPU·메모리·디스크는 공유하므로 순간 부하 영향이 전혀 없었다는 뜻은 아니다.
- 제품 코드·공용 서비스·공용 DB·배포·공식 QA 기록표는 변경하지 않았다. #65 FAIL·INS-13 보류 및 BE 공식 37/44를 유지한다.

## 준비 중단 기록과 증거 보존

- 준비 회차 `qa-mo-sim03-sim12-20261014-093128`는 배포 healthcheck의 `$`를 Compose용 `$$`로 옮기지 못했고, 두 번째 `...093341`는 공용 MySQL용 30초 유예가 새 DB 초기화 완료 전에 만료돼 MySQL 준비 중 중단됐다. 두 회차 모두 **SIM 시험 요청 및 cases 없음**. 제품 QA 실패가 아닌 시험 준비 오류이며 원본 로그·요약·전후 E1 확인을 `setup-attempts/`에 보존한다.
- DB 초기화 전용 준비 설정을 적용한 후 새 프로젝트에서 실행했다. Simulator·Backend·Inference는 배포 healthcheck와 실제 전용 컨테이너 healthcheck의 완전 일치를 확인했다. 통과 회차를 찾기 위한 성능 재측정을 하지 않았다.
- 요청·응답·상태·snapshot·DB·Docker health 로그·모델 체크섬·소스 대조·실행 스크립트·Compose를 보존했다. [전체 요약](summary.json) · [SHA-256 목록](manifest.sha256).
- 결과·증거는 별도 MO 커밋으로 공유한다. 외부 댓글 초안은 게시하지 않았으며 팀 합의도 아직 확정되지 않았다.
