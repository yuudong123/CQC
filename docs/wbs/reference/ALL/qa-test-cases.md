# 확정 범위 QA 테스트 케이스

- 기준: dev `2c859dd` (2026-10-06, PR #100 검사 ID 규칙·중복 409, #101 FE 검사 ID, #102 진단 기록 상한까지 반영). 학원 서버 모델 `cqc-apple-separate12-focal-v2-cal-20260930`, 임계값 품종 0.50·품질 0.60
- 작성: 조현재 (2026-09-30), 10-06 QA 목록 초안으로 갱신. 상태: **QA 목록 초안 — 10-08 회의에서 기준(QA-SIM-13)·분담 확정 후 실행**
- 목적: 구현과 계약이 확정된 기능을 ALL-04 수용시험(#65)으로 검증한다. 분담은 [6.1](#61-파트별-분담), BE-10 3·4단계와 겹치는 케이스는 [6.2](#62-be-10과-겹치는-케이스)를 따른다.
- 검토 요청: [Issue #103](https://github.com/yuudong123/CQC/issues/103), QA 초안 `0091e8f` 반영. 담당·QA-SIM-13 수용 기준·E2 진행 방식은 **10-08 회의 확정 전**이다.
- 진행 상태는 [ALL-03](../../ALL-03.md)에만 적는다. 이 문서에는 케이스와 실행 증거를 두고, 최종 결과는 [ALL-04 #65](https://github.com/yuudong123/CQC/issues/65)에 모은다.

## 1. 범위

### 1.1 포함: 확정된 기능

| 영역 | 케이스 | 근거 | 확정 이유 |
|---|---|---|---|
| 배포·상태 | QA-DEP | MO-02·04·05, NFR-05·06 | Compose 7개 서비스(품질 4·물류 3), healthcheck, migration, 볼륨이 dev에 있다 |
| Inference API | QA-INF | DM-07·08, FR-03·38·51, NFR-01·22 | OpenAPI 계약, 보정 패키지, 서버컴 지연 측정이 끝났다 |
| 검사 API | QA-INS | BE-04, FR-02·04·05·13·14·19·26·28·34·37·39·44·45·53·55, NFR-18·24 | `POST /v1/inspections`, 임계값, 12-bin seed, 라인 속도 기한(#87)이 구현됐다 |
| 관제 조회 API | QA-OPS | BE-05, FR-07~10·21·22·29·31·32, NFR-14 | 관제 OpenAPI의 snapshot·이력·통계·CSV가 구현됐다 |
| 검수 이미지 | QA-IMG | BE-06, FR-16·42, NFR-09 | 시스템 오류·저신뢰 재검사 저장·목록·미리보기·선택 삭제·종류별 100/200장 순환이 구현됐다(#55) |
| Simulator·검수 | QA-SIM, QA-OPS-16 | BE-07, FR-15·18·23·24·33·46~49·54 | 독립 Simulator(자동 재생·정지/재개·위치 복구·장애 6종·다음 1건·라인 속도 1·2·3초), `PUT /simulator`, 검수 API가 구현·배포됐다 |
| 웹 관제 화면 | QA-WEB | FE-02~08, FR-06·20~22·35·36·41, NFR-11·12 | 학원 서버 3100이 실제 Backend에 연결된 API 모드로 배포되어 있다(10-02~) |
| 자동 시험 | QA-AUTO | 전체 | 저장소 시험으로 재현할 수 있다 |

### 1.2 제외: 미확정·미구현 (구현되면 케이스 추가)

| 제외 항목 | 이유 | 추가 시점 |
|---|---|---|
| 지연 결과 DB 저장 (FR-27) | BE-08에서 기존 검사 행의 진단 필드에 저장하도록 구현. 화면·API에는 노출하지 않는다 | 자동 시험 `tests/api/test_late_results.py`(QA-AUTO)로 갈음 |
| 이력 순환 삭제 86,400/8,640건 (FR-30) | 구현(BE-09, PR #52). 서버에서 86,400건을 채우려면 라인 속도 2초로 약 48시간이 걸려 수용시험에서 재현하지 않는다 | PR #52 실DB 검증(86,400 → 77,760건)과 자동 시험으로 갈음 |
| 로그 순환 (NFR-15), 실패 시 이전 버전 유지 (MO-07) | 구현(#57, #69). MO-07은 10-02 서버에서 빌드·상태 확인 실패 주입으로 기존 유지·이전 이미지 복구를 확인했다 | 로그 순환·장애 시험은 MO-08(#70) 결과로 갈음 |
| 초당 2건 처리량 (FR-01·NFR-19 목표) | 서버컴 실측 초당 0.63건으로 미달(결정 기록 09-30). 수용시험은 라인 속도 2초 기준으로 판정한다(QA-SIM-13, 10-08 회의 확정 예정) | 처리 구조를 바꿀 때 |
| 물류(출품·경매·배차) | MVP 제외 확정(10-01, #48). 시연 목업만 유지 | 범위에 다시 넣기로 하면 |

### 1.3 이미 알려진 결함

아래 표는 통합 점검에서 나온 결함과 현재 상태다. **열림** 상태인 결함 때문에 케이스가 실패하면 새 결함으로 올리지 말고 번호를 적는다. 출처는 [파트별 협업 요청](../../협업공지/파트별-협업-요청.md) 09-30 절과 PR #37이다.

| 번호 | 현상 | 상태 (10-02) | 관련 케이스 |
|---|---|---|---|
| KI-1 | MySQL 중단 중 `POST /v1/inspections`가 HTTP 500으로 선별이 멈춤 | 해결(#37 LKG: 마지막 정상 bin mapping 사용). PR #52(#45)에서 Compose MySQL 약 58초 중단 중 선별·가상 제어 지속, 복구 후 Backend 재시작 없이 저장 재개를 검증. 서버컴 확인은 ALL-04 QA-INS-13 | QA-INS-13, QA-SIM-09 |
| KI-2 | snapshot `throughput`이 진행 중인 1초 구간을 써서 낮게 나옴 | 해결(#37, 직전 완료 구간). 단 KI-6 참고 | QA-OPS-15 |
| KI-3 | Inference 컨테이너 정지 시 오류 코드가 `INFERENCE_TIMEOUT`으로 기록 | 해결(#67, 연결 단계 timeout 기본 200ms 및 연결 실패 분류 적용; 10-02 로컬 Compose 재검증) | QA-INS-11 |
| KI-4 | snapshot `components.Inference`가 항상 `unknown` | 해결(#37, Inference `/health` 확인. 학원 서버 `healthy` 확인) | QA-WEB-07 |
| KI-5 | Simulator가 보낸 검사 1건이 실패하면 Simulator 전체가 정지 | 해결(#37, 실패 건만 기록하고 계속 전송) | QA-SIM-09 |
| KI-6 | 입력 간격 2초에서 1초 단위 `throughput`이 0 또는 1만 나와 `현재 처리량`이 0건/초로 자주 보임 | 해결(#49, 화면 `현재 처리량`을 최근 10초 평균으로 표시). snapshot `throughput` 값 자체는 1초 구간이라 처리량 판단은 `periodTotals`로 한다 | QA-OPS-15, QA-WEB-05 |
| KI-7 | 고정 500ms 기한 때문에 서버 CPU가 바쁠 때 시간 초과 4.1% | 해결(#87, 제한시간 = 라인 간격. 10-05 배포 후 535건 중 0건) | QA-INS-12, QA-SIM-02·13 |
| KI-8 | Windows 개발 PC에서 검수 이미지 시험 2개가 폴더 이름 변경 권한 오류(WinError 5) | 개발 환경 한정(#99 닫힘). 서버 Linux에서는 재현되지 않음. QA-AUTO-01에서 다시 확인 | QA-AUTO-01 |
| KI-9 | DB 장애 중 Simulator 설정 변경(정지·재개·라인 속도·동시 처리·장애 토글)이 503 `DB_UNAVAILABLE` | 의도된 동작(10-07 결정, #65). 성공 응답이 전체 snapshot이라 DB가 필요. 장애 중에도 판정·가상 제어는 계속되고 화면은 연결 경고 표시. Backend 수정 없음, 필요 시 QA·동결 뒤 "정지만 허용" 재논의 | QA-WEB-09·10, QA-SIM-09 |
| KI-10 | DB(MySQL) 중단 중 검사 HTTP 응답이 4.3~4.9초로 QA-INS-13의 2초 기준 초과 | **최종까지 보류 확정(10-08, #117)**. 원인은 MySQL 컨테이너 중단 시 Docker 내부 이름 조회 지연(약 3.3초)으로, 프로젝트 범위에서 해결하지 않는다. 판정·LKG 선별·가상 제어 지속, 저장 실패 분리, 재시작 없는 복구는 통과. 수용시험에서는 응답시간 조건만 예외로 기록한다 | QA-INS-13 |

## 2. 환경

| 환경 | 구성 | 용도 | 주의 |
|---|---|---|---|
| E1 학원 서버 | `192.168.133.106` Backend 8000·Inference 8001·웹 3100(API 모드). Jenkins가 dev를 자동 배포 | 기본 기능·화면 확인 | 공용 MySQL에 기록이 남는다. `inspection_id`는 `qa-` 접두사를 붙인다. 재배포 중이면 기다린다. **Simulator가 2초마다 검사를 넣고 있어** 오늘 집계 증가량은 E1에서 판정하지 않는다. Simulator 설정(정지·장애)도 E1에서 바꾸지 않는다 |
| E2 로컬 Compose | dev 체크아웃, `.env`는 `.env.example` 복사, `INFERENCE_MODEL_DIR`에 보정 패키지 폴더 | 장애 주입(DB·Inference 정지, 기한·주소 변경) | 모델 폴더는 DM(조현재)에게 받는다. 학원 서버에서 장애 주입을 하지 않는다 |
| E3 웹 API 모드 | 읽기 확인은 학원 서버 `http://192.168.133.106:3100`을 그대로 쓴다. 조작·장애 확인은 `apps/web`을 E2 Backend에 연결해 로컬 실행 | 웹 화면 확인 | E1 웹에서는 Simulator 조작·이미지 일괄 삭제를 하지 않는다(공용) |

### 2.1 E2 장애 주입 설정

공용 `cqc-cicd`와 다른 프로젝트·DB·상태 볼륨을 사용한다. 동일 PC에서 실행한다면 Git Bash에서 아래 값을 먼저 설정한다. 이후 이 문서의 `docker compose` 명령은 `COMPOSE_PROJECT_NAME`으로 지정한 시험 프로젝트에 적용된다. 시험 전 `.env`의 `DATABASE_URL`이 공용 DB를 가리키지 않는지 확인하고, 시험용 DB 계정·Simulator 토큰을 사용한다.

```bash
export COMPOSE_PROJECT_NAME=cqc-qa-$(date +%Y%m%d%H%M)
export BACKEND_PORT=127.0.0.1:18000
export INFERENCE_PORT=127.0.0.1:18001
export LOGISTICS_API_PORT=127.0.0.1:18100
export LOGISTICS_WEB_PORT=127.0.0.1:13100
```

공통 준비의 E2 주소도 `BE=http://127.0.0.1:18000`, `INF=http://127.0.0.1:18001`로 바꾼다. E3 로컬 웹을 붙일 때도 Backend 포트 18000을 쓴다. 외부 `cqc_simulator_dataset` 볼륨은 읽기 전용으로 공유할 수 있다. QA-DEP-01은 전체 7개 서비스를 띄워 판정하고, 품질 서비스 4개만 띄운 환경은 장애 시험에 한해 사용한다. 변경·중단·재시작 전에 `docker compose ps`의 컨테이너 이름이 시험 프로젝트인지 확인한다. 종료 시 `docker compose down -v`는 시험 프로젝트에만 실행하며 외부 데이터 볼륨은 제거하지 않는다.

저장소에 올리지 않는 `compose.qa.yaml`을 만들어 필요한 줄만 켠다. 적용 후 `docker compose -f compose.yaml -f compose.qa.yaml up -d backend`로 Backend만 다시 만든다. 케이스가 끝나면 파일 없이 `docker compose up -d backend`로 되돌린다.

```yaml
services:
  backend:
    environment:
      # QA-INS-12, QA-IMG-06: 직접 보낸 요청(간격 헤더 없음)을 시간 초과로 만든다 (hard timeout 2000ms보다 작아야 함)
      # Simulator 요청은 라인 속도 기한(#87)을 쓰므로 이 값의 영향을 받지 않는다
      INFERENCE_BUSINESS_DEADLINE_MS: "50"
      # QA-INS-10: 닫힌 포트로 즉시 연결 실패
      # INFERENCE_URL: http://inference:9/v1/predict
      # QA-INS-06: 품종 저신뢰를 만든다
      # CULTIVAR_CONFIDENCE_THRESHOLD: "0.9995"
```

### 2.2 E3 실행

```bash
cd cqc-logistics-platform/apps/web
npm ci
CQC_QUALITY_MODE=api CQC_QUALITY_BACKEND_URL=http://192.168.133.106:8000 npm run build
CQC_QUALITY_MODE=api CQC_QUALITY_BACKEND_URL=http://192.168.133.106:8000 npx next start -p 3200
```

E1 읽기 확인은 이 빌드 없이 `http://192.168.133.106:3100`을 연다. E2에 붙일 때는 주소를 `http://localhost:8000`으로 바꾼다. 브라우저는 Chrome 최신판을 쓰고 `http://localhost:3200`을 연다.

## 3. 공통 준비

### 3.1 명령 도구

모든 명령은 dev 최신 `C:\CQC`에서 Git Bash로 실행한다. 사진 경로는 상대 경로로 둔다(`/c/...` 절대 경로는 curl이 파일을 못 여는 경우가 있다). `jq`가 없으면 `python -m json.tool`로 본다.

```bash
DEMO=data/processed/realtime-apple-arrival-demo/groups
BE=http://192.168.133.106:8000        # E2는 http://localhost:8000
INF=http://192.168.133.106:8001       # E2는 http://localhost:8001

# 사용법: send <URL> <inspection_id> <묶음 폴더> [virtual_brix] [장수]
# 응답 헤더와 본문을 출력한다. virtual_brix를 비우면 필드를 보내지 않는다.
send() {
  local url=$1 id=$2 dir=$3 brix=$4 n=${5:-12}
  local meta
  meta=$(python -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1]))['metadata'][:int(sys.argv[2])]))" "$dir/request.json" "$n")
  local args=(-F "inspection_id=$id" -F "metadata=$meta")
  [ -n "$brix" ] && args+=(-F "virtual_brix=$brix")
  for i in $(seq 0 $((n - 1))); do
    args+=(-F "images=@$dir/frame_$(printf %02d "$i").png;type=image/png")
  done
  curl -s -D - -X POST "$url" "${args[@]}"
  echo
}

# 첫 사진만 잘린 PNG로 바꾼 손상 묶음. Inference가 422를 반환한다.
mkdir -p qa-tmp && rm -rf qa-tmp/broken && cp -r "$DEMO/demo-601031008000-000" qa-tmp/broken
head -c 20000 "$DEMO/demo-601031008000-000/frame_00.png" > qa-tmp/broken/frame_00.png

RUN=qa-$(date +%m%d%H%M)   # 실행 회차 접두사. 모든 inspection_id 앞에 붙인다
```

`qa-tmp/`는 시험이 끝나면 지운다. 저장소에 올리지 않는다.

### 3.2 DB 조회 (E2, 또는 서버 접근 권한이 있는 MO)

```bash
sql() { docker compose exec -T mysql sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "$0"' "$1"; }
sql "SELECT inspection_id, inspection_status, target_bin_code, error_code FROM inspections ORDER BY created_at DESC LIMIT 5"
```

### 3.3 시험 묶음

시연 묶음 중 09-30 보정 시험 36개의 실제 결과([원본](../../results/v2-cal-demo-dry-run-20260930.json))에서 골랐다. 같은 모델이면 신뢰도가 ±0.005 안에서 재현되어야 한다. 폴더는 `$DEMO/<묶음 ID>`이다.

| 기호 | 묶음 ID | 정답 | 모델 예측 | 품종 신뢰도 | 품질 신뢰도 | 용도 |
|---|---|---|---|---:|---:|---|
| B-FL | `demo-601031008000-000` | 부사·특 | 부사·특 | 1.000 | 0.990 | 정상 |
| B-FM | `demo-601032016000-000` | 부사·상 | 부사·상 | 1.000 | 0.994 | 정상 |
| B-FS | `demo-601033004000-000` | 부사·보통 | 부사·보통 | 1.000 | 0.998 | 정상 |
| B-YL | `demo-601141012000-000` | 양광·특 | 양광·특 | 1.000 | 0.919 | 정상 |
| B-YM | `demo-601142007000-000` | 양광·상 | 양광·상 | 0.999 | 0.946 | 정상 |
| B-YS | `demo-601143013000-000` | 양광·보통 | 양광·보통 | 1.000 | 1.000 | 정상 |
| B-LQ | `demo-601031028000-000` | 부사·특 | 부사·특 | 1.000 | **0.464** | 품질 저신뢰 |
| B-LQ2 | `demo-601033026000-000` | 부사·보통 | 부사·보통 | 1.000 | **0.583** | 품질 저신뢰 (기준 바로 아래) |
| B-MIS | `demo-601141014000-000` | 양광·특 | 양광·**상** | 0.998 | **0.514** | 오분류가 저신뢰로 걸러지는 예 |
| B-EDGE | `demo-601031014000-000` | 부사·특 | 부사·특 | 1.000 | 0.630 | 기준 바로 위 통과 |
| B-EDGE2 | `demo-601033014000-000` | 부사·보통 | 부사·보통 | **0.998** | 0.649 | 기준 위 통과, E2 품종 기준 0.9995에서 품종 저신뢰 |
| B-BROKEN | `qa-tmp/broken` | - | - | - | - | 손상 사진 (Inference 422) |

현재 시연 묶음에는 품종 신뢰도가 0.50 미만인 것이 없다(최소 0.995). 품종 저신뢰는 E2에서 품종 기준을 올려 확인한다(QA-INS-06).

### 3.4 기대 bin (12-bin seed)

가상 당도 14.0 미만은 `less_sweet`, 14.0 이상은 `sweet`이다. 재검사 bin은 `TEST_REINSPECTION_BIN` 하나다.

| 품종 | 등급 | less_sweet (<14.0) | sweet (≥14.0) |
|---|---|---|---|
| fuji | L (특) | DEMO_BIN_01 | DEMO_BIN_02 |
| fuji | M (상) | DEMO_BIN_03 | DEMO_BIN_04 |
| fuji | S (보통) | DEMO_BIN_05 | DEMO_BIN_06 |
| yanggwang | L (특) | DEMO_BIN_07 | DEMO_BIN_08 |
| yanggwang | M (상) | DEMO_BIN_09 | DEMO_BIN_10 |
| yanggwang | S (보통) | DEMO_BIN_11 | DEMO_BIN_12 |

## 4. 판정 규칙과 기록

- **통과:** 모든 기대 결과를 만족한다.
- **실패:** 기대 결과와 하나라도 다르다. 1.3 알려진 결함이면 번호를 적는다.
- **차단:** 환경 문제로 실행하지 못했거나 전체 기대값을 아직 검증하지 못했다(재배포 중, 접근 권한 없음, 부분 검증·자동 회귀만 실행, 수용 기준 합의 전 등). 확인한 범위와 남은 조건을 적는다. 부분 검증의 실패는 그대로 실패로 기록한다.
- 증거는 응답 본문·헤더, 화면 캡처, CSV 파일을 `qa-tmp/<케이스 ID>/`에 모으고, 실패 건만 팀 공유 드라이브에 올린다.
- 우선순위: **P1** 시연·판정 결과가 틀려짐, **P2** 기록·표시가 틀려짐, **P3** 문구·편의.

결함 기록 양식:

```text
[QA-XXX-00] 한 줄 요약
환경: E1/E2/E3, dev 커밋, 모델 버전
재현: 1) ... 2) ...
기대: ...
실제: ... (응답·캡처 경로)
우선순위: P1/P2/P3, 담당: DM/FE/BE/MO
```

## 5. 테스트 케이스

각 케이스는 **근거 · 환경 · 사전 조건 · 절차 · 기대 결과** 순서다. 표로 묶은 입력 검증은 행마다 따로 판정한다.

### 5.1 배포·상태 (QA-DEP)

#### QA-DEP-01 컨테이너 구성과 재시작 정책 · P1

- 근거: MO-02·04, Compose 7개 서비스
- 환경: E2 (E1은 MO가 서버에서 실행)
- 절차:
  1. `docker compose ps --format "table {{.Service}}\t{{.Status}}"`
  2. `docker inspect -f '{{.Name}} {{.HostConfig.RestartPolicy.Name}}' $(docker compose ps -q)`
- 기대 결과:
  - 서비스 7개: `mysql`, `inference`, `backend`, `simulator`, `logistics-mongodb`, `logistics-api`, `logistics-web`
  - 7개 모두 `(healthy)`. 품질 관제 화면은 `logistics-web`(3100)이 Backend에 붙어 제공한다(별도 `frontend` 서비스 없음)
  - `simulator`의 healthy는 재생 중이고 최근 30초 안에 검사 전송이 성공했다는 뜻이다
  - 모든 컨테이너의 재시작 정책이 `unless-stopped`
- 판정 범위: Simulator가 정상 재생 중일 때 확인한다. QA-SIM-03에서 의도적으로 정지한 동안의 unhealthy를 이 케이스의 새 결함으로 기록하지 않는다.

#### QA-DEP-02 Inference 상태와 모델 버전 · P1

- 근거: DM-07·08, MO-05
- 환경: E1
- 절차: `curl -s $INF/health`
- 기대 결과 (모든 필드 일치):

| 필드 | 값 |
|---|---|
| `status` | `ready` |
| `model_loaded` | `true` |
| `model_name` | `mobilenet_v3_small_multiview` |
| `model_version` | `cqc-apple-separate12-focal-v2-cal-20260930` |
| `device` | `cpu` |
| `views` | `12` |
| `approval_status` | `unverified_candidate` |
| `threshold_status` | `calibrated_dev_oof` |
| `checkpoint_sha256` | `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a` |
| `quality_temperature` | 0.3908 (소수 넷째 자리까지) |
| `cultivar_temperature` | 0.3840 |
| `decode_workers` | 1 이상 (서버컴 8) |

#### QA-DEP-03 모델 파일 체크섬 · P1

- 근거: MO-05 모델 버전·체크섬
- 환경: E2 또는 서버 모델 폴더
- 절차: 모델 폴더에서 `sha256sum model.pt`, `python -c "import json;print(json.load(open('model.json'))['checkpoint_sha256'])"`
- 기대 결과: 두 값과 QA-DEP-02 `checkpoint_sha256`이 모두 같다.

#### QA-DEP-04 Backend 상태와 임계값 전달 · P1

- 근거: DM-08 임계값 결정, `compose.yaml`
- 환경: E2 (E1은 MO)
- 절차:
  1. `curl -s $BE/health`
  2. `docker compose exec backend env | grep -E "THRESHOLD|INFERENCE_URL|FAULT_IMAGE"`
- 기대 결과:
  1. `{"status":"ok","service":"CQC Backend","environment":...}`
  2. `CULTIVAR_CONFIDENCE_THRESHOLD=0.50`, `QUALITY_CONFIDENCE_THRESHOLD=0.60`, `INFERENCE_URL=http://inference:8001/v1/predict`, `FAULT_IMAGE_STORAGE_ROOT=/data/fault-images`
- 비고: 값이 다르면 QA-INS-03·04 판정이 모두 달라지므로 먼저 실행한다. `/health`만 성공한 결과는 임계값·주소·저장 경로 확인까지 포함한 전체 통과로 기록하지 않는다.

#### QA-DEP-05 migration과 bin seed · P1

- 근거: BE-02, FR-05
- 환경: E2
- 절차:
  1. `docker compose exec backend alembic current`
  2. `sql "SELECT bin_code, cultivar, quality_grade, sweetness_band, is_reinspection, is_active FROM bin_mappings ORDER BY bin_code"`
- 기대 결과:
  1. `20260929_02 (head)`
  2. 13행. `DEMO_BIN_01~12`는 3.4 표와 같은 조합이고 `is_reinspection=0`, `TEST_REINSPECTION_BIN` 1행만 `is_reinspection=1`이며 품종·등급·당도가 NULL. 13행 모두 `is_active=1`

#### QA-DEP-06 재시작 후 데이터 보존 · P2

- 근거: MO-05 볼륨, NFR-06
- 환경: E2
- 사전 조건: 검사 이력과 장애 이미지가 1건 이상 있다(QA-INS-08 이후).
- 절차:
  1. E2 Simulator를 정지하고 진행 중 검사가 끝날 때까지 기다린다. 이력 수·시험 검사 ID와 장애 이미지 ID·미리보기 URL을 기록한다.
  2. `docker compose restart backend mysql`
  3. MySQL·Backend가 healthy가 되면 같은 기록을 다시 조회하고, 새 고유 ID로 정상 검사 1건을 보낸다.
  4. 확인 뒤 Simulator를 재개한다.
- 기대 결과: 새 검사 전 이력 수와 장애 이미지 수가 같고 기존 검사·이미지 ID가 남아 있다. 기록한 미리보기는 HTTP 200이다. 재시작 후 첫 `POST /v1/inspections`가 정상 처리·저장된다. 재생 중의 단순 건수 증가는 보존 실패 근거로 쓰지 않는다.

#### QA-DEP-07 비밀값 저장소 제외 · P2

- 근거: NFR-05
- 절차: `git ls-files | grep -E "(^|/)\.env$"`, `git grep -n -I -E "MYSQL_(ROOT_)?PASSWORD=[^c$]" -- . ':!*.md'`. 두 번째 명령에 일치 항목이 있으면 값을 공유하지 말고 해당 줄이 고정 비밀값인지, 환경변수·동적 시험 비밀번호를 구성하는 코드인지 확인한다.
- 기대 결과: 추적된 `.env`가 없고, 검토한 일치 항목에 고정 비밀값이 없다. `.env.example`의 MySQL 비밀번호는 `change_me`뿐이다. 단순 정규식의 출력 자체를 곧바로 유출 판정으로 사용하지 않는다.

### 5.2 Inference API (QA-INF)

#### QA-INF-01 정상 12장 예측 응답 · P1

- 근거: FR-03·38·51, [Inference OpenAPI](../../../contracts/inference-openapi.json)
- 환경: E1
- 절차: `send $INF/v1/predict $RUN-inf01 $DEMO/demo-601031008000-000`
- 기대 결과:
  - HTTP 200
  - 본문 키가 정확히 `inspection_id`, `crop_type`, `predicted_cultivar`, `cultivar_confidence`, `cultivar_probabilities`, `predicted_grade`, `quality_confidence`, `quality_probabilities`, `inference_time_ms`, `model_name`, `model_version`, `preprocessing_version`, `used_frame_count` 13개다. bin·재검사·DB 관련 필드가 없다(FR-38).
  - `inspection_id`가 보낸 값과 같다. `crop_type=apple`, `used_frame_count=12`
  - `predicted_cultivar=fuji`, `predicted_grade=L`, `cultivar_confidence`≈1.000, `quality_confidence`≈0.990 (±0.005)
  - `cultivar_probabilities` 키는 `fuji`·`yanggwang`, `quality_probabilities` 키는 `L`·`M`·`S`
  - `model_version=cqc-apple-separate12-focal-v2-cal-20260930`

#### QA-INF-02 확률 일관성 · P1

- 근거: FR-03, 모델 카드 보정 설명
- 환경: E1, QA-INF-01 응답 사용
- 기대 결과:
  - 품종 확률 합, 품질 확률 합이 각각 1.000±0.001
  - `cultivar_confidence` = 품종 확률 최댓값, `quality_confidence` = 품질 확률 최댓값
  - `predicted_cultivar`·`predicted_grade`가 각 확률의 최댓값 라벨

#### QA-INF-03 재현성 · P1

- 근거: NFR-01
- 환경: E1
- 절차: B-FL, B-LQ, B-MIS를 각각 3번씩 `$INF/v1/predict`로 보낸다.
- 기대 결과: 같은 묶음의 3번 응답에서 예측 라벨이 같고 모든 확률 차이가 1e-6 이하다. 3.3 표의 신뢰도와 ±0.005 안에서 같다.

#### QA-INF-04 단계별 시간 헤더 · P2

- 근거: DM-08 `Server-Timing`
- 환경: E1
- 절차: QA-INF-01 응답 헤더를 본다.
- 기대 결과: `server-timing: decode;dur=<수>, model;dur=<수>, total;dur=<수>` 형식이다. `total` ≥ `model`이고, `inference_time_ms`가 `model` 값과 ±1ms 안에서 같다.

#### QA-INF-05 12장 미만 입력 · P2

- 근거: NFR-22, DM-04 누락 뷰 마스킹
- 환경: E1
- 절차: B-FL을 장수 1, 4, 8, 11로 보낸다. 예: `send $INF/v1/predict $RUN-inf05-4 $DEMO/demo-601031008000-000 "" 4`
- 기대 결과: 모두 HTTP 200이고 `used_frame_count`가 보낸 장수와 같다. 예측 라벨은 판정하지 않는다(장수가 줄면 달라질 수 있다).

#### QA-INF-06 입력 검증 · P1

- 근거: FR-02, Inference OpenAPI 오류 응답
- 환경: E1. 각 행은 B-FL 사진을 쓰고 `-F` 인자를 바꿔 curl로 직접 보낸다.

| # | 입력 | 기대 HTTP | 기대 `detail` |
|---|---|---|---|
| a | `images` 없이 `inspection_id`·`metadata`만 | 422 | 필드 누락 검증 오류 |
| b | 사진 13장, metadata 13개 | 413 | `images는 최대 12장까지 허용합니다` |
| c | `metadata=not-json` | 422 | `metadata는 JSON 배열이어야 합니다` |
| d | 사진 2장, metadata 1개 | 422 | `metadata 항목 수는 images 수와 같아야 합니다` |
| e | metadata 한 항목에서 `horizontality_angle` 제거 | 422 | `metadata[0] 필수 필드가 누락되었습니다` |
| f | 사진 2장, metadata의 `view_index`를 1, 0 순서로 | 422 | `metadata의 view_index는 images 순서와 일치해야 합니다` |
| g | `angle_direction=left` | 422 | `angle_direction은 top 또는 bottom이어야 합니다` |
| h | `verticality_angle=90.5` | 422 | `촬영 각도는 정수여야 합니다` |
| i | 사진 1장을 `type=image/gif`로 | 415 | `PNG 또는 JPEG만 지원합니다` |
| j | 25MiB 더미 PNG 1장 (아래 명령으로 생성) | 413 | `전체 이미지는 최대 24MiB입니다` |
| k | 잘린 PNG 1장 (`qa-tmp/broken/frame_00.png`) | 422 | `image file is truncated` |
| l | 텍스트 파일을 `type=image/png`로 | 422 | `cannot identify image file …` |
| m | `inspection_id=` (빈 값) | 422 | 검증 오류 |

- 각 행 공통: 오류 응답 뒤 바로 QA-INF-01을 다시 보내 200이 나온다(서버가 오류로 멈추지 않음).
- 25MiB 더미 PNG 만들기: `python -c "open('qa-tmp/big.png','wb').write(b'\x89PNG\r\n\x1a\n'+b'0'*(25*2**20))"`

#### QA-INF-07 예측 중 상태 확인 응답 · P3

- 근거: DM-07 추론을 스레드풀에서 실행
- 환경: E1
- 절차: B-FL 예측 3건을 백그라운드로 동시에 보내고(`send ... &` 3번), 바로 `curl -s -w "%{time_total}\n" -o /dev/null $INF/health`
- 기대 결과: `/health`가 1초 안에 200으로 응답한다.

#### QA-INF-08 서버컴 서버 내부 지연 · P1

- 근거: NFR-07·13, DM-08 동시 처리 1 결정
- 환경: E1. Jenkins 재배포 중이 아닐 때(3분 이상 `/health` 안정)
- 절차:
  1. 36개 묶음 ID: `python -c "import json;[print(b['bundle_id']) for b in json.load(open('docs/wbs/results/v2-cal-demo-dry-run-20260930.json',encoding='utf-8'))['bundles_detail']]" > qa-tmp/ids36.txt`
  2. 준비 실행 3건 후 순차로 보낸다: `while read id; do send $INF/v1/predict $RUN-$id $DEMO/$id | grep -i server-timing; done < qa-tmp/ids36.txt > qa-tmp/timing.txt`
  3. `total;dur=` 값 36개의 평균·p95·최대를 계산한다.
- 기대 결과: 36건 모두 HTTP 200, `total` 최대가 라인 간격(2000ms) 안. 기준값: 09-30 측정 평균 271.4·p95 308.8·최대 324.9ms([원본](../../results/server-real-photos-20260930.json)). p95가 기준값보다 30% 이상 크면 통과여도 기록하고 DM에게 알린다. 500ms 고정 기준은 #87로 없어졌다(결정 기록 10-05·10-06).
- 비고: 노트북에서 잰 왕복 시간은 업로드가 대부분이라 판정에 쓰지 않는다.

### 5.3 검사 API (QA-INS)

`POST $BE/v1/inspections`. 응답의 `inspection_status`·`decision_reason`·`target_bin_code`·`control_status`·`persistence_status`를 매번 확인한다.

#### QA-INS-01 정상 판정과 12-bin 전체 · P1

- 근거: FR-04·05·13·55, 12-bin 정책
- 환경: E1
- 절차: 정상 묶음 6개를 가상 당도 13.9와 14.0으로 한 번씩, 모두 12건 보낸다.

```bash
for pair in FL:demo-601031008000-000 FM:demo-601032016000-000 FS:demo-601033004000-000 \
            YL:demo-601141012000-000 YM:demo-601142007000-000 YS:demo-601143013000-000; do
  key=${pair%%:*}; id=${pair#*:}
  for brix in 13.9 14.0; do send $BE/v1/inspections $RUN-ins01-$key-$brix $DEMO/$id $brix; done
done
```

- 기대 결과 (12건 공통): HTTP 200, `inspection_status=COMPLETED`, `review_required=false`, `decision_reason=NORMAL`, `exclude_from_normal_stats=false`, `control_status=SUCCEEDED`, `persistence_status=SUCCEEDED`, `brix_is_measured=false`, `virtual_brix`가 보낸 값, 예측 필드가 Inference 응답과 같은 값.
- 기대 bin:

| 묶음 | 13.9 → `sweetness_band=less_sweet` | 14.0 → `sweetness_band=sweet` |
|---|---|---|
| FL | DEMO_BIN_01 | DEMO_BIN_02 |
| FM | DEMO_BIN_03 | DEMO_BIN_04 |
| FS | DEMO_BIN_05 | DEMO_BIN_06 |
| YL | DEMO_BIN_07 | DEMO_BIN_08 |
| YM | DEMO_BIN_09 | DEMO_BIN_10 |
| YS | DEMO_BIN_11 | DEMO_BIN_12 |

#### QA-INS-02 가상 당도 입력 범위 · P1

- 근거: FR-55, 가상 당도 9~18°Brix
- 환경: E1, 묶음 B-FL

| # | `virtual_brix` | 기대 |
|---|---|---|
| a | `9` | 200, `less_sweet`, DEMO_BIN_01 |
| b | `18` | 200, `sweet`, DEMO_BIN_02 |
| c | `14` (정수) | 200, `sweet`, DEMO_BIN_02 |
| d | `8.9` | 422 |
| e | `18.1` | 422 |
| f | `abc` | 422 |
| g | `nan` | 422 |
| h | `inf` | 422 |

- 422 행은 DB에 기록되지 않는다(QA-OPS-03 목록에 해당 ID가 없다).

#### QA-INS-03 가상 당도 누락 · P1

- 근거: 요구사항 2절 "가상 당도 누락 건은 재검사 bin"
- 환경: E1
- 절차: `send $BE/v1/inspections $RUN-ins03 $DEMO/demo-601031008000-000` (당도 없이)
- 기대 결과: `inspection_status=REINSPECTION_REQUIRED`, `review_required=true`, `decision_reason=VIRTUAL_BRIX_MISSING`, `exclude_from_normal_stats=false`, `target_bin_code=TEST_REINSPECTION_BIN`, `control_status=SUCCEEDED`, `virtual_brix=null`, `sweetness_band=null`, 예측 필드는 부사·특으로 채워짐.

#### QA-INS-04 품질 저신뢰 분기 · P1

- 근거: FR-04·28, DM-08 품질 기준 0.60
- 환경: E1, 당도 15.0

| 묶음 | 기대 `decision_reason` | 비고 |
|---|---|---|
| B-LQ (0.464) | `LOW_QUALITY_CONFIDENCE` | |
| B-LQ2 (0.583) | `LOW_QUALITY_CONFIDENCE` | 기준 바로 아래 |
| B-MIS (0.514) | `LOW_QUALITY_CONFIDENCE` | 오분류(정답 특, 예측 상)가 재검사로 걸러짐 |

- 공통 기대: `inspection_status=REINSPECTION_REQUIRED`, `review_required=true`, `exclude_from_normal_stats=false`(통계 포함), `target_bin_code=TEST_REINSPECTION_BIN`, `control_status=SUCCEEDED`, 예측 필드와 `sweetness_band=sweet`가 채워짐.

#### QA-INS-05 기준 바로 위 통과 · P2

- 근거: FR-04 "기준 미만"만 보류
- 환경: E1, 당도 13.0
- 절차: B-EDGE(0.630), B-EDGE2(0.649)
- 기대 결과: 둘 다 `COMPLETED`, `NORMAL`. B-EDGE는 DEMO_BIN_01, B-EDGE2는 DEMO_BIN_05.

#### QA-INS-06 품종 저신뢰와 둘 다 저신뢰 · P1

- 근거: FR-04, 판정 사유 3종
- 환경: E2, `CULTIVAR_CONFIDENCE_THRESHOLD=0.9995` 적용(2.1)
- 절차와 기대:

| 묶음 | 품종 / 품질 신뢰도 | 기대 `decision_reason` |
|---|---|---|
| B-EDGE2 | 0.998 / 0.649 | `LOW_CULTIVAR_CONFIDENCE` |
| B-MIS | 0.998 / 0.514 | `LOW_BOTH_CONFIDENCE` |
| B-FL | 1.000 / 0.990 | `NORMAL` (DEMO_BIN_01, 당도 13.0) |

- 공통 기대(앞 두 건): `REINSPECTION_REQUIRED`, `TEST_REINSPECTION_BIN`, `exclude_from_normal_stats=false`.
- DB: `sql "SELECT inspection_id, applied_cultivar_threshold, applied_quality_threshold FROM inspections WHERE inspection_id LIKE '$RUN-ins06%'"` → `0.999500`, `0.600000`.
- 끝나면 설정을 되돌린다.

#### QA-INS-07 요청 검증 · P1

- 근거: FR-02, FR-52
- 환경: E1, B-FL 사진으로 curl 인자를 바꿔 보낸다.

| # | 입력 | 기대 HTTP | 기대 `detail` |
|---|---|---|---|
| a | `inspection_id="   "` (공백만) | 422 | 검증 오류(허용 문자 아님) |
| b | `images` 없음 | 422 | 필드 누락 |
| c | 사진 13장 | 413 | `images는 최대 12장까지 허용합니다` |
| d | 합계 24MiB 초과 (QA-INF-06 j 더미) | 413 | `multipart 요청이 허용된 최대 크기를 초과했습니다` |
| e | 사진 1장을 `type=image/gif` | 415 | `images는 PNG 또는 JPEG만 지원합니다` |
| f | `metadata=not-json` | 422 | `metadata는 유효한 이미지 metadata JSON 배열이어야 합니다` |
| g | metadata 항목에 `"extra":1` 추가 | 422 | 같은 문구 (추가 필드 금지) |
| h | `angle_direction=left` | 422 | 같은 문구 |
| i | 사진 2장, metadata 1개 | 422 | `images와 metadata 개수는 같아야 합니다` |
| j | 사진 2장, `view_index` 0, 0 | 422 | `view_index는 중복될 수 없습니다` |
| k | 사진 2장, `view_index` 1, 2 | 422 | `view_index는 현재 이미지 순서에 따라 0부터 연속되어야 합니다` |
| l | `inspection_id`가 `qa/bad`, `qa bad`, `qa*bad` | 422 | 검증 오류. 허용 문자는 영문·숫자·`_`·`.`·`-`(#100) |
| m | `inspection_id` 65자 | 422 | 검증 오류(최대 64자) |
| n | `inspection_id=$RUN.ins07.n`(점 포함) | 200 | 정상 판정. 점은 허용 |
| o | n과 같은 ID를 한 번 더 | 409 | `inspection_id가 이미 존재합니다`. 기존 행·이미지가 바뀌지 않고 Inference를 다시 부르지 않는다(KB-01) |

- 공통 기대: 검증 오류(422·413·415)와 중복(409)은 Inference를 호출하지 않고 DB·장애 이미지에 새 기록을 남기지 않는다(QA-OPS-03 목록과 QA-IMG-02 목록에 해당 ID가 없거나 n의 1건뿐이다).

#### QA-INS-08 Inference 오류 응답 → 시스템 오류 재검사 · P1

- 근거: FR-39, FR-28 통계 제외, FR-16
- 환경: E1
- 절차: `send $BE/v1/inspections $RUN-ins08 qa-tmp/broken 15.0 1` (손상 사진 1장)
- 기대 결과:
  - HTTP 200, `inspection_status=REINSPECTION_REQUIRED`, `decision_reason=INFERENCE_HTTP_ERROR`, `exclude_from_normal_stats=true`, `target_bin_code=TEST_REINSPECTION_BIN`, `control_status=SUCCEEDED`, `persistence_status=SUCCEEDED`
  - `predicted_cultivar`·`predicted_grade`·신뢰도·`model_version`이 모두 `null`
  - 장애 이미지 목록에 `inspectionId=$RUN-ins08`, `imageIndex=0`, `errorCode=INFERENCE_HTTP_ERROR` 1건 추가(QA-IMG-02)
  - 이력에서 `processingStatus=ERROR`, `errorCode=INFERENCE_ERROR`, `status=FAIL`, `excluded=true`(QA-OPS-04)

#### QA-INS-09 Inference 응답 불일치 검출 · P2

- 근거: FR-37 동일 `inspection_id`, Backend 응답 검증
- 환경: 자동 시험 `tests/api/test_inspection_service.py::test_service_rejects_mismatched_inference_response`
- 기대 결과: 통과. Inference가 다른 ID나 다른 장수를 돌려주면 `INFERENCE_INVALID_RESPONSE` 재검사가 된다.

#### QA-INS-10 Inference 연결 실패 · P1

- 근거: FR-39
- 환경: E2, `INFERENCE_URL=http://inference:9/v1/predict` 적용
- 절차: `send $BE/v1/inspections $RUN-ins10 $DEMO/demo-601031008000-000 15.0`
- 기대 결과: 1초 안에 HTTP 200, `decision_reason=INFERENCE_CONNECTION_ERROR`, `exclude_from_normal_stats=true`, `TEST_REINSPECTION_BIN`. 장애 이미지 12장 저장(`errorCode=INFERENCE_CONNECTION_ERROR`). 이력 `processingStatus=ERROR`, `errorCode=INFERENCE_ERROR`.

#### QA-INS-11 Inference 컨테이너 정지 · P1

- 근거: FR-39 (KI-3 해결, #67)
- 환경: E2
- 절차: `docker compose stop inference` → `send $BE/v1/inspections $RUN-ins11 $DEMO/demo-601031008000-000 15.0` → `docker compose start inference`
- 기대 결과: HTTP 200, `decision_reason=INFERENCE_CONNECTION_ERROR`, 재검사 bin, `exclude_from_normal_stats=true`, 이력 `errorCode=INFERENCE_ERROR`·`processingStatus=ERROR`·`excluded=true`. TCP 연결 실패 또는 연결 단계 timeout은 `INFERENCE_ERROR`로, 연결 후 응답 지연과 업무 기한 초과(Simulator 요청은 라인 간격, 간격 헤더 없는 직접 요청은 500ms)는 `INFERENCE_TIMEOUT`으로 분류한다.
- 추가 확인: Inference 재시작 후 healthy가 되면 Backend 재시작 없이 다음 정상 요청이 `COMPLETED`.

#### QA-INS-12 Inference 시간 초과 · P1

- 근거: FR-19·26, BE-04 제한시간(직접 요청 기본값)
- 환경: E2, `INFERENCE_BUSINESS_DEADLINE_MS=50` 적용. `send`는 간격 헤더를 보내지 않아 이 기본값이 적용된다
- 절차:
  1. `send $BE/v1/inspections $RUN-ins12 $DEMO/demo-601031008000-000 15.0`, 응답 시간을 잰다(`curl -w "%{time_total}"`).
  2. 3초 기다린 뒤 이력에서 같은 ID를 조회한다.
- 기대 결과:
  1. HTTP 200, `decision_reason=INFERENCE_DEADLINE_EXCEEDED`, `exclude_from_normal_stats=true`, `TEST_REINSPECTION_BIN`, 예측 필드 `null`. 응답이 Inference 완료를 기다리지 않는다(Inference 처리 시간보다 짧다).
  2. 이력 `processingStatus=TIMEOUT`, `errorCode=INFERENCE_TIMEOUT`, `variety=null`, `bin=TEST_REINSPECTION_BIN`. 늦게 도착한 추론 결과가 bin·예측값을 바꾸지 않는다(FR-26).
  3. 장애 이미지 12장, `errorCode=INFERENCE_TIMEOUT`(QA-IMG-02).
- 지연 결과 추적 한도·hard timeout은 자동 시험 `tests/api/test_late_results.py`로, 라인 속도별 기한(1·2·3초 → hard 2·3·4초)은 `tests/api/test_line_deadlines.py`로 확인한다.

#### QA-INS-13 DB 중단 중 선별 지속 · P1

- 근거: FR-34·53, NFR-16 (알려진 결함 KI-1)
- 환경: E2
- 절차:
  1. `docker compose stop mysql`
  2. `send $BE/v1/inspections $RUN-ins13-a $DEMO/demo-601031008000-000 15.0`, 응답 시간 기록
  3. `docker compose start mysql`, healthy 후 `send ... $RUN-ins13-b ...`
- 기대 결과:
  2. HTTP 200, 모델 판정대로 `COMPLETED`·`DEMO_BIN_02`·`control_status=SUCCEEDED`, `persistence_status=FAILED`. DB를 기다리느라 응답이 라인 간격을 넘기지 않는다(#37 LKG, 실제 검증은 #45).
  3. `$RUN-ins13-b`는 `persistence_status=SUCCEEDED`. `$RUN-ins13-a`는 이력에 없어도 된다(유실 허용).

#### QA-INS-14 제어 명령 기록과 응답 시간 · P2

- 근거: FR-13·43, NFR-18 가상 제어 100ms
- 환경: E2, QA-INS-01 이후
- 절차: `sql "SELECT inspection_id, attempt_no, requested_bin_code, command_type, control_status, response_time_ms FROM control_attempts WHERE inspection_id LIKE '$RUN-ins01%' ORDER BY inspection_id"`
- 기대 결과: 검사마다 1행, `attempt_no=1`, `command_type=ROUTE_TO_BIN`, `control_status=SUCCEEDED`, `requested_bin_code`가 응답 `target_bin_code`와 같다. `response_time_ms` 최대 < 100.

#### QA-INS-15 제어 거부·무응답 안전 동작 · P1

- 근거: FR-14·44·45. 실행 중 제어 장애를 켜는 기능은 BE-07 이후라 지금은 자동 시험으로 확인한다.
- 절차: `python -m pytest tests/api/test_virtual_control.py tests/api/test_inspection_service.py -k "reject or retry or no_response or fallback" -v`
- 기대 결과: 모두 통과. 확인 내용: 정상 bin 거부 시 재검사 bin 1회 대체, 대체 거부는 재시도 없음, 무응답·실패는 재시도 없음, 두 시도가 순서대로 저장됨.

#### QA-INS-16 모델 버전·임계값·시각 기록 · P2

- 근거: FR-10, NFR-02·14, 요구사항 8.3
- 환경: E2
- 절차: `sql "SELECT inspection_id, model_version, preprocessing_version, applied_cultivar_threshold, applied_quality_threshold, created_at, completed_at, brix_is_measured FROM inspections WHERE inspection_id='$RUN-ins01-FL-13.9'"`
- 기대 결과: `model_version=cqc-apple-separate12-focal-v2-cal-20260930`, 임계값 `0.500000`/`0.600000`, `created_at`·`completed_at`이 밀리초 3자리, `completed_at ≥ created_at`, `brix_is_measured=0`.

#### QA-INS-17 검사 ID 추적 · P2

- 근거: NFR-24
- 절차: QA-INS-08의 `$RUN-ins08`을 응답, 이력 API(`/v1/quality/inspections?errorCode=INFERENCE_ERROR`), 이력 CSV, 장애 이미지 목록, DB `inspection_errors`에서 찾는다.
- 기대 결과: 다섯 곳 모두 같은 ID로 찾는다.

### 5.4 관제 조회 API (QA-OPS)

공용 DB라 절대 건수 대신 **시험 전후 증가량**으로 판정한다. 모든 응답 헤더에 `Cache-Control: no-store`가 있어야 한다.

#### QA-OPS-01 snapshot 구조 · P1

- 근거: BE-05, [관제 OpenAPI](../../../contracts/quality-operations.openapi.json)
- 환경: E1
- 절차: `curl -s -D - $BE/v1/quality/snapshot`
- 기대 결과:
  - `contractVersion="1"`, `source="backend"`, `revision`은 Simulator revision(기동 직후 0. 자동 시작은 revision을 올리지 않는다)
  - `capabilities`: `control=true`, `faults=true`, `review=true`, `deleteImages=true`, `concurrency=[1,2,4]`, `intervals=[1000,2000,3000]`
  - `components.Simulator.status=healthy`(`detail`: `검사 전송 중`, `lastSeenAt` 30초 이내), `Inference`는 `healthy`(`detail`: `추론 서비스 준비 완료`), `Backend`·`MySQL`은 `healthy`, `lastSeenAt`이 `capturedAt`과 같다
  - `state.running=true`, `state.concurrency=1`, `state.intervalMs=2000`, `state.faults=[]`, `state.scope=ALL`
  - `periodTotals` 키 `1`·`5`·`10`·`30`, 값은 1 ≤ 5 ≤ 10 ≤ 30 순서로 줄지 않는다
  - `state.points` 30개, `at`이 1000ms 간격으로 오름차순, 마지막 `at` ≤ `capturedAt`
  - `state.history` ≤ 200건 최신순, `state.errors` ≤ 50건, `state.dbDown=false`
  - `state.jobs`는 처리 중인 검사(0~`concurrency`건, 미리보기 포함), `state.recentCompletedJobs`는 미리보기가 아직 살아 있는 최근 완료 검사(≤ 64건, #88)
  - `state.today.date`가 오늘 KST 날짜(`YYYY-MM-DD`)
  - `retention.images`가 QA-IMG-02 목록 수와 같고 300 이하(시스템 오류 100 + 저신뢰 200)

#### QA-OPS-02 오늘 집계 증가량 · P1

- 근거: FR-21·28·29
- 환경: E2. 먼저 Simulator를 정지하고(QA-SIM-03 절차 1) 끝나면 재개한다.
- 절차:
  1. snapshot `state.today`를 저장(전)
  2. 정상 2건(B-FL 13.9, B-YS 14.0), 품질 저신뢰 1건(B-LQ 15.0), 당도 누락 1건(B-FM), Inference 오류 1건(B-BROKEN 1장) 보낸다.
  3. snapshot `state.today`를 다시 저장(후)
- 기대 증가량 (후 − 전):

| 필드 | 증가 | 설명 |
|---|---:|---|
| `total` | 5 | 저장된 전체 |
| `normal` | 4 | 통계 제외(오류) 1건 뺌 |
| `excluded` | 1 | Inference 오류 |
| `review` | 2 | 통계 포함 건 중 검수(저신뢰·당도 누락) |
| `reinspection` | 3 | 검수 2 + 오류 1 |
| `varieties.부사` / `양광` | 3 / 1 | 통계 포함 건만 |
| `grades.특` / `상` / `보통` | 2 / 1 / 1 | |
| `bins.DEMO_BIN_01` / `DEMO_BIN_12` / `TEST_REINSPECTION_BIN` | 1 / 1 / 3 | 제어 성공 명령 기준 |
| `inferenceCount` | 4 | 통계 포함 + 추론 시간 있음 |

- Simulator가 돌고 있거나 다른 사람이 동시에 보내면 결과가 흔들린다. 증가량이 크면 `$RUN` 이력만 세어 다시 판정한다.

#### QA-OPS-03 이력 목록과 표시값 변환 · P1

- 근거: FR-07·08, NFR-14
- 환경: E1
- 절차: `curl -s "$BE/v1/quality/inspections?pageSize=50" | jq '.items[] | select(.id=="'$RUN'-ins01-FL-13.9")'`
- 기대 결과 (B-FL 13.9 행):
  - `variety=부사`, `grade=특`, `bin=DEMO_BIN_01`, `status=PASS`, `processingStatus=COMPLETED`, `errorCode=NONE`
  - `confidence`≈99.0, `cultivarConfidence`≈100.0 (확률×100)
  - `virtualBrix=13.9`, `brixMeasured=false`, `modelVersion=cqc-apple-separate12-focal-v2-cal-20260930`, `inferenceMs` > 0
  - `control=SUCCEEDED`, `persistence=SAVED`, `faults=[]`, `misclassification=NONE`, `reviewRequired=false`, `excluded=false`
  - `date`는 KST 날짜, `time`은 `HH:MM:SS.mmm`(KST), `timestamp`는 epoch ms이고 `date`·`time`과 같은 순간
  - 목록이 `timestamp` 내림차순이다. `bins`에 `DEMO_BIN_01`이 있다.

#### QA-OPS-04 상태별 변환 · P1

- 근거: FR-06·28, BE-05 상태 매핑
- 환경: E1(E2 행은 E2), 앞 케이스에서 만든 기록을 조회한다.

| 기록 | `status` | `processingStatus` | `errorCode` | `variety`/`grade` | `excluded` | `bin` |
|---|---|---|---|---|---|---|
| QA-INS-01 정상 | PASS | COMPLETED | NONE | 값 있음 | false | DEMO_BIN_xx |
| QA-INS-04 저신뢰 | REVIEW | COMPLETED | NONE | 값 있음 | false | TEST_REINSPECTION_BIN |
| QA-INS-03 당도 누락 | REVIEW | COMPLETED | NONE | 값 있음 | false | TEST_REINSPECTION_BIN |
| QA-INS-08 Inference 오류 | FAIL | ERROR | INFERENCE_ERROR | null | true | TEST_REINSPECTION_BIN |
| QA-INS-10 연결 실패 (E2) | FAIL | ERROR | INFERENCE_ERROR | null | true | TEST_REINSPECTION_BIN |
| QA-INS-12 시간 초과 (E2) | FAIL | TIMEOUT | INFERENCE_TIMEOUT | null | true | TEST_REINSPECTION_BIN |

- 오류 행은 `faults`에 `errorCode`와 같은 값이 첫 번째로 들어 있고 `confidence`·`cultivarConfidence`·`inferenceMs`·`modelVersion`이 `null`이다.

#### QA-OPS-05 이력 필터 · P1

- 근거: FR-31
- 환경: E1. 오늘 날짜를 `D=$(date +%F)`로 두고 `from=$D&to=$D`를 모든 행에 붙인다.

| # | 조건 | 기대 |
|---|---|---|
| a | `variety=부사` | 모든 행 `variety=부사`. 오류 행(variety null) 제외 |
| b | `variety=양광&grade=보통` | 모든 행 양광·보통, `$RUN-ins01-YS-*` 포함 |
| c | `bin=DEMO_BIN_02` | 모든 행 `bin=DEMO_BIN_02` |
| d | `bin=TEST_REINSPECTION_BIN` | 저신뢰·당도 누락·오류 기록 포함 |
| e | `processingStatus=COMPLETED` | TIMEOUT·ERROR 행 없음 |
| f | `processingStatus=ERROR` | `$RUN-ins08` 포함, 모든 행 ERROR |
| g | `processingStatus=TIMEOUT` (E2) | `$RUN-ins12` 포함 |
| h | `processingStatus=INFERENCING` | `items=[]`, `total=0` |
| i | `errorCode=NONE` | 오류 기록이 있는 행 없음. 저신뢰·당도 누락 행은 포함 |
| j | `errorCode=INFERENCE_ERROR` | `$RUN-ins08` 포함 |
| k | `errorCode=INFERENCE_TIMEOUT` (E2) | `$RUN-ins12` 포함 |
| l | `misclassification=NONE` / `OTHER` | `NONE`은 지정 안 한 행만, `OTHER`는 QA-OPS-16에서 지정한 행 포함 |
| m | `from=2026-01-01&to=2026-01-01` | `total=0` |
| n | `variety=부사&grade=특&bin=DEMO_BIN_01` | 세 조건 모두 만족하는 행만 |

- 공통: 각 응답의 `total`이 `items` 수와 페이지 계산에 맞는다(`total` ≤ 50이면 `items` 수 = `total`).

#### QA-OPS-06 페이지와 행 수 · P2

- 근거: FE-03 50/100/200건
- 환경: E1 (이력 101건 이상일 때)

| # | 요청 | 기대 |
|---|---|---|
| a | `pageSize=50&page=1`, `page=2` | 각 50건, 두 페이지 ID 중복 없음, `total` 같음 |
| b | `pageSize=100`, `pageSize=200` | 각 100·200건 이하, `pageSize` 값 그대로 반환 |
| c | `pageSize=20` | 422 `{"code":"INVALID_QUERY"}` |
| d | `page=0` | 422 `INVALID_QUERY` |
| e | 마지막 페이지 + 1 | 200, `items=[]`, `total` 같음 |

#### QA-OPS-07 조회 기준 시각 고정 · P1

- 근거: FE-03 목록 시점 고정
- 환경: E1
- 절차:
  1. `curl -s "$BE/v1/quality/inspections?pageSize=50"`에서 `snapshotAt`(S)과 `total`(T) 기록
  2. 새 검사 1건(`$RUN-ops07`, B-FL 13.9)
  3. `?pageSize=50&snapshotAt=S` 조회
  4. `?pageSize=50` 조회
- 기대 결과: 3은 `total=T`이고 `$RUN-ops07`이 없다. 4는 `total=T+1` 이상이고 `$RUN-ops07`이 첫 페이지에 있다.

#### QA-OPS-08 조회 입력 오류 · P2

- 근거: 관제 OpenAPI 오류 코드
- 환경: E1. `/v1/quality/inspections`, `/statistics`, `/inspections.csv`, `/statistics.csv`에 각각 보낸다.

| # | 쿼리 | 기대 |
|---|---|---|
| a | `foo=1` | 422 `UNKNOWN_QUERY_FIELD` |
| b | `from=2026-09-30&to=2026-09-29` | 422 `INVALID_DATE_RANGE` |
| c | `snapshotAt=<현재 ms + 600000>` | 422 `INVALID_SNAPSHOT` |
| d | `variety=사과` | 422 `INVALID_QUERY` |
| e | `from=2026-13-01` | 422 `INVALID_QUERY` |
| f | `/statistics?minutes=1` | 422 `UNKNOWN_QUERY_FIELD` (`minutes`는 통계 CSV 전용) |

- 공통: 본문이 `{"code":...}` 하나이고 `Cache-Control: no-store`.

#### QA-OPS-09 KST 날짜 경계 · P2

- 근거: NFR-14, BE-05 한국시간
- 환경: E1
- 절차: 오늘 KST `D`, 어제 `Y`로 `from=$D&to=$D`와 `from=$Y&to=$Y`를 조회한다.
- 기대 결과: 오늘 만든 `$RUN` 기록은 `D`에만 있고 `Y`에는 없다. KST 00:00~08:59에 실행하면 UTC 날짜와 달라도 KST 날짜로 묶인다(가능하면 이 시간대에 한 번 실행).

#### QA-OPS-10 검사 이력 CSV · P1

- 근거: FR-32, BE-05 UTF-8 BOM
- 환경: E1
- 절차: `curl -s -D qa-tmp/csv.h "$BE/v1/quality/inspections.csv?from=$D&to=$D" -o qa-tmp/inspections.csv`
- 기대 결과:
  - 헤더 `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="cqc-inspections.csv"`, `Cache-Control: no-store`
  - 파일이 UTF-8 BOM(`EF BB BF`)으로 시작하고 줄바꿈이 CRLF, 모든 칸이 큰따옴표로 감싸짐
  - 첫 줄 열 순서: `inspection_id, date, time_kst, variety, grade, cultivar_confidence_pct, quality_confidence_pct, inference_ms, model_version, target_bin, processing_status, control_status, persistence_status, error_codes, misclassification, virtual_brix, brix_is_measured`
  - 데이터 행 수 = 같은 필터의 `/inspections` `total` (200건을 넘어도 전체)
  - `brix_is_measured`는 모두 `false`, 오류 행의 `error_codes`는 `|`로 이음, 이미지 파일·URL 열이 없다
  - Excel로 열었을 때 한글(부사·특 등)이 깨지지 않는다

#### QA-OPS-11 CSV 수식 주입 방지 · P2

- 근거: BE-05 CSV 안전 출력
- 환경: E1
- 절차: `inspection_id=-$RUN-ops11`(하이픈으로 시작)로 B-FL 13.9를 보내고 CSV를 받는다.
- 기대 결과: 해당 행 첫 칸이 `"'-qa-…-ops11"`처럼 작은따옴표로 시작한다. Excel에서 수식으로 실행되지 않는다.

#### QA-OPS-12 기간 통계 일관성 · P1

- 근거: FR-09·28·29
- 환경: E1
- 절차: `curl -s "$BE/v1/quality/statistics?from=$D&to=$D"`와 같은 시점 snapshot `state.today` 비교
- 기대 결과:
  - `total`·`normal`·`excluded`·`reinspection`·`varieties`·`grades`·`bins`·`inferenceCount`가 snapshot `today`와 같다(두 요청 사이 신규 건이 없을 때)
  - `total = normal + excluded`
  - `varieties` 합 = `grades` 합 = `normal`
  - `bins`에는 제어 성공 명령만 센다
  - `variety=부사`를 붙이면 `varieties`에 부사만 남고 `total`이 줄어든다

#### QA-OPS-13 통계 CSV 두 형식 · P2

- 근거: FR-32, FE-05 1·5·10·30분
- 환경: E1

| # | 요청 | 기대 |
|---|---|---|
| a | `/statistics.csv?from=$D&to=$D` | 첫 줄 `mode,from_kst,to_kst,group,key,value`. `total` 그룹에 `reinspection_ratio`·`average_inference_ms` 행 |
| b | `/statistics.csv` (날짜 없음) | 첫 줄 `mode,date_kst,section,key,value,last_saved_at`. `today` 섹션, `grades`·`varieties`·`bins`·`suspicions` 섹션 |
| c | `/statistics.csv?minutes=5` | b 형식에 `last_5_minutes` 섹션 300행(1초 단위) |
| d | `minutes=1`·`10`·`30` | 각각 60·600·1,800행 |
| e | `minutes=2` | 422 `INVALID_QUERY` |

- 공통: BOM·CRLF·모든 칸 따옴표, `mode` 값 `BACKEND`, `reinspection_ratio` = `reinspection / total`.

#### QA-OPS-14 DB 중단 시 조회 API · P1

- 근거: FR-36, NFR-04
- 환경: E2
- 절차: `docker compose stop mysql` 뒤 snapshot·inspections·statistics·inspections.csv·statistics.csv를 호출하고, `docker compose start mysql` 후 다시 호출한다.
- 기대 결과: 중단 중 모두 503 `{"code":"DB_UNAVAILABLE"}`와 `no-store`. 재시작 후 Backend 재시작 없이 200으로 돌아온다. Backend 로그에 DB 조회 실패가 원인과 함께 남는다(NFR-10).

#### QA-OPS-15 최근 처리량과 기간 합계 · P2

- 근거: FR-22, FE-05 (알려진 결함 KI-2)
- 환경: E1
- 절차: B-FL을 1초 간격으로 10건 보내고 끝난 직후 snapshot과 history를 받는다. dev 푸시·Jenkins 빌드·다른 QA와 겹치지 않는 시간에 한다(#65 기준, 겹친 회차는 판정에서 뺀다).
- 기대 결과: 보낸 10건의 ID가 모두 history에 저장된다. `periodTotals["1"]`은 snapshot 시각 기준 직전 60초 동안 저장된 history 건수와 같다(구간 경계 ±1). `points` `count` 합도 같은 시간 범위의 history 저장 건수와 같다(±1). `state.throughput`은 직전 완료 1초 구간 건수다(#37). 간격 2초에서는 0 또는 1이라 처리량 판단에는 `periodTotals`를 쓴다(KI-6).
- 판정 메모: `periodTotals["1"]`은 이동 1분 구간이라 새 건이 들어오는 동안 1분 지난 기존 건이 빠진다. 보내기 전과의 차이(+10)로 판정하지 않는다(10-07 #103 BE 지적). 부하 없는 회차에서 10건의 시간 초과는 0건이어야 하며, 시간 초과가 나면 같은 시간대 서버 부하(Jenkins 빌드 등)를 먼저 확인한다.

#### QA-OPS-16 오판 의심 검수 API · P2

- 근거: FR-15, BE-07 검수 API
- 환경: E1 (본인 `$RUN` 기록만)
- 절차와 기대 (`R=$RUN-ins01-FL-13.9`):

| # | 요청 | 기대 |
|---|---|---|
| a | `curl -s -X PATCH $BE/v1/quality/inspections/$R/review -H "Content-Type: application/json" -d '{"misclassification":"OTHER"}'` | 200 `{"inspectionId":"<R>","misclassification":"OTHER"}`, `Cache-Control: no-store` |
| b | a 뒤 이력 조회 | 해당 행 `misclassification=OTHER`. 품종·등급·bin·상태는 그대로(판정 결과를 바꾸지 않음) |
| c | a 뒤 오늘 통계 `suspicions.OTHER` | 1 증가 |
| d | `{"misclassification":"NONE"}` | 200, 행이 `NONE`으로 돌아가고 `suspicions.OTHER`가 다시 줄어든다 |
| e | `{"misclassification":"WRONG"}` | 422 `INVALID_REVIEW` |
| f | `{"misclassification":"OTHER","extra":1}` | 422 `INVALID_REVIEW` |
| g | 없는 ID `qa-no-such-id` | 404 `INSPECTION_EXPIRED` |
| h | ID에 허용 안 되는 문자 `qa*bad` | 422 `INVALID_REVIEW` (점 `.`은 허용 문자라 `qa.bad`는 404, #100) |

### 5.5 검수 이미지 (QA-IMG)

#### QA-IMG-01 저장 조건 · P1

- 근거: FR-16 정상 이미지 즉시 삭제·저신뢰 재검사 보관(#55), BE-06
- 환경: E1
- 절차: 검수 이미지 수를 기록하고 QA-INS-01 정상 12건, QA-INS-03·04를 보낸 뒤 다시 센다.
- 기대 결과: 정상·당도 누락 요청의 사진은 저장되지 않는다. 저신뢰 요청(QA-INS-03)의 사진만 12장 늘고, 그 항목은 `category=LOW_CONFIDENCE`, `errorCode=null`, `decisionReason`이 `LOW_*_CONFIDENCE` 중 하나다.

#### QA-IMG-02 목록 · P1

- 근거: BE-06 개별 검수 이미지 계약(#55)
- 환경: E1, QA-INS-08 이후
- 절차: `curl -s -D - $BE/v1/quality/fault-images`
- 기대 결과:
  - `items` ≤ 300(시스템 오류 100 + 저신뢰 200), 최신 `createdAt` 순
  - 항목 키: `id`(`32자리 16진수_두 자리 번호`), `inspectionId`, `imageIndex`(0~11), `createdAt`(epoch ms), `errorCode`(저신뢰는 `null`), `previewUrl`(`/api/quality/previews/<id>`), `category`(`SYSTEM_ERROR`·`LOW_CONFIDENCE`), `decisionReason`, `cultivarConfidence`·`qualityConfidence`·`appliedCultivarThreshold`·`appliedQualityThreshold`(0~1 또는 `null`)
  - `?category=LOW_CONFIDENCE`, `?inspectionId=<id>`로 걸러진다
  - `$RUN-ins08` 항목: `imageIndex=0`, `errorCode=INFERENCE_HTTP_ERROR`
  - 시간 초과 기록(E2)은 `errorCode=INFERENCE_TIMEOUT`으로 보인다

#### QA-IMG-03 미리보기 · P1

- 근거: BE-06, FR-42
- 환경: E1
- 절차: QA-IMG-02의 `$RUN-ins08` 항목 `id`로 `curl -s -D - $BE/v1/quality/previews/<id> -o qa-tmp/preview.png`
- 기대 결과: 200, `Content-Type: image/png`, `Cache-Control: no-store`. `sha256sum qa-tmp/preview.png`가 보낸 `qa-tmp/broken/frame_00.png`와 같다.

| # | 잘못된 id | 기대 |
|---|---|---|
| a | `0000` | 410 `IMAGE_EXPIRED` |
| b | 형식은 맞지만 없는 id (`<32자리 0>_00`) | 410 `IMAGE_EXPIRED` |
| c | `..%2F..%2Fetc` | 404 또는 410. 저장소 밖 파일을 읽지 않는다 |

#### QA-IMG-04 선택 삭제 · P1

- 근거: FE-07·BE-06 삭제 후 이력 유지
- 환경: E1 (본인이 만든 `$RUN` 이미지만 지운다)
- 절차:
  1. `$RUN`으로 만든 장애 이미지 id 2개(A, B)를 고른다.
  2. `curl -s -X DELETE $BE/v1/quality/fault-images -H "Content-Type: application/json" -d '{"ids":["A","B","B","ffffffffffffffffffffffffffffffff_00"]}'`
  3. 목록·미리보기·이력을 조회한다.
- 기대 결과:
  2. 200 `{"deletedIds":["A","B"]}` (중복·없는 id는 무시)
  3. 목록에서 A·B만 사라지고 나머지는 그대로, A·B 미리보기는 410 `IMAGE_EXPIRED`, 해당 검사 이력은 목록·CSV에 그대로 남는다. snapshot `retention.images`가 2 줄어든다.

#### QA-IMG-05 삭제 입력 검증 · P2

- 환경: E1

| # | 본문 | 기대 |
|---|---|---|
| a | `{"ids":[]}` | 200 `{"deletedIds":[]}` |
| b | `{"ids":["../x"]}` | 422 `INVALID_IDS` |
| c | id 301개 | 422 `INVALID_IDS` |
| d | `{"ids":["A"],"all":true}` | 422 `INVALID_IDS` (추가 필드 금지) |
| e | 본문 없음 | 422 `INVALID_IDS` |

#### QA-IMG-06 시스템 오류 100장 순환 · P1

- 근거: NFR-09
- 환경: E2 (학원 서버의 기존 장애 이미지를 지우므로 E1에서 하지 않는다)
- 사전 조건: 장애 이미지를 모두 지워 0장으로 만든다(QA-IMG-04 방법으로 전체 id 삭제).
- 절차: 손상 묶음 12장 요청을 9번 보낸다: `for n in 1 2 3 4 5 6 7 8 9; do send $BE/v1/inspections $RUN-img06-$n qa-tmp/broken 15.0 > /dev/null; done`
- 기대 결과:
  - 목록 100장 (12×9=108 중 오래된 8장 삭제)
  - `$RUN-img06-1`은 `imageIndex` 8~11의 4장만 남고, `-2`~`-9`는 12장씩 모두 남는다
  - 시스템 오류 이미지가 100장이다. 저신뢰 재검사 이미지(최대 200장)는 따로 세며 이 순환에 밀려나지 않는다
  - 웹 검수 이미지 창 요약 `시스템 오류 100/100`
  - 검사 이력 9건은 모두 남는다

#### QA-IMG-07 재시작 보존 · P2

- 환경: E2, QA-IMG-06 이후
- 절차: `docker compose restart backend` 후 목록과 미리보기를 확인
- 기대 결과: 100장 그대로이고 미리보기 응답이 HTTP 200이다(볼륨 `fault_images`).
- 판정 준비: E2 Simulator를 정지하고 진행 중 검사가 끝난 뒤 이미지 ID를 기록한다. 재시작 후 동일 ID·미리보기를 확인하고 Simulator를 재개한다. 단순 목록 수만으로 파일 보존까지 통과 처리하지 않는다.

### 5.6 웹 관제 화면 (QA-WEB)

> 10-08 관리자 페이지 분리: 관제 화면(`/`)은 계속 지켜볼 정보(요약 카드·재검사·오류 목록·시스템 상태·처리 현황·처리 중 사과)만 둔다. 검사 이력·기간 통계·검수 이미지·시연 설정(입력 정지/재개 포함)과 통계 CSV는 관리자 페이지(`/admin`, 상단 메뉴 `품질 관리`)의 같은 이름 탭에서 실행한다. 아래 절차의 "창·버튼"은 해당 탭으로 읽고, 기대값은 그대로다. 해당 케이스(QA-WEB-06·09·12~15)는 PR #118 배포 뒤 10-08에 다시 확인했다(6.4 기록표).

E3에서 실행한다. 달리 적지 않으면 창 크기는 1600×900이다.

#### QA-WEB-01 연결 표시 · P1

- 근거: FE-05
- 절차: 첫 화면을 연다.
- 기대 결과(PR #115 배포 후): 제목 `<농장명> 품질 관제`(기본 `CQC 사과농장 품질 관제`, `NEXT_PUBLIC_FARM_NAME`으로 변경), 부제 `우리 농장 전용 · 선별 라인 1`, 배지 `서버 관제`(초록). 첫 응답 전 잠깐 `서버 연결 중`. Backend 주소를 비우고 실행하면 배지가 `서버 연결 중`에 머물고 상단에 연결 경고가 뜬다.

#### QA-WEB-02 1초 갱신과 요청 중첩 없음 · P1

- 근거: FR-22, FE-05
- 절차: 개발자 도구 Network에서 `snapshot` 필터를 켜고 30초 관찰한다. 그동안 검사 1건을 보낸다.
- 기대 결과: `/api/quality/snapshot` 요청이 약 1초 간격이고 이전 요청이 끝나기 전에 다음 요청이 시작되지 않는다. 보낸 검사가 2초 안에 `검사 이력` 창 첫 행에 나타난다(재검사·오류면 `재검사·오류 사과` 첫 줄에도).

#### QA-WEB-03 재검사·오류 사과 목록 · P1

- 근거: FR-06, FE-05 표시 자리수, 10-01 멘토링 피드백(정상 판정은 실시간으로 볼 필요가 적음, #54)
- 절차: QA-INS-01·04·08 기록을 좌상단 `재검사·오류 사과`에서 찾는다(PR #115 배포 전에는 좌하단).
- 기대 결과:

| 기록 | 목록 | 구분 | 사유 | 품종 / 품질 신뢰도 | 목적지 |
|---|---|---|---|---|---|
| 정상 B-FL 13.9 | 보이지 않음 | — | — | — | — |
| 저신뢰 B-LQ | 보임 | `재검사`(노랑) | `품질 신뢰도 미달` | `100.0% / 46.4%`, 46.4%만 빨간 굵은 글씨 | `재검사함`(마우스를 올리면 `TEST_REINSPECTION_BIN`) |
| 오류 B-BROKEN | 보임 | `오류`(빨강) | `추론 오류` | `—` | `재검사함` |

- 사유 기준: 품종 신뢰도 50% 미만 `품종 신뢰도 미달`, 품질 60% 미만 `품질 신뢰도 미달`, 둘 다면 `품종·품질 신뢰도 미달`. 기준값과 같으면 미달이 아니다. 오류는 `추론 시간 초과`/`추론 오류`.
- 위 버튼 `전체 n` / `재검사 n` / `오류 n`의 수가 목록 행 수와 같고, 누르면 해당 구분만 남는다.
- 안내 문구 `최근 판정 n건 중 · 신뢰도 기준 품종 50% / 품질 60% 미만은 재검사 · 전체 기간은 검사 이력`의 n은 snapshot `history` 길이(서버 최대 200).
- 시각 열은 KST `HH:MM:SS.mmm`, 최신순, 최대 50행. 메인 화면에는 검사 ID 열이 없고, 행에 마우스를 올리면 검사 ID가 보인다(ID는 검사 이력·CSV에 유지).
- 해당 건이 없으면 `최근 판정 n건 중 재검사·오류 없음`.
- 정상 판정은 `검사 이력` 창(QA-WEB-12)에서 확인한다.

#### QA-WEB-04 상단 요약 카드 · P1

- 근거: FR-21·28, FE-05
- 환경: E3 + E2(Simulator 정지)
- 절차: QA-OPS-02의 5건을 보내기 전후 카드 값을 기록한다.
- 기대 결과: `오늘 저장 검사` +5, `통계 제외` +1.
  - `오늘 저장 검사`·`오늘 재검사율`은 큰 카드. `오늘 재검사율`은 `x.x%`와 옆 작은 글씨 `n건`, 값은 snapshot `today.reinspection / today.total`(소수 첫째 자리). 20%를 넘으면 빨간 카드로 바뀐다(PR #115).
  - `평균 추론`은 `inferenceTotalMs / inferenceCount`의 `x.xms`. 서버 관제에서는 라벨에 `· 예시`가 없다.
  - `현재 처리량`은 최근 10초 평균 `x.x건/초`.

#### QA-WEB-05 처리 현황 패널 · P1

- 근거: FR-09·22·29, FE-05
- 절차: `기간` 선택을 1·5·10·30분으로 바꾸고, 같은 시각 snapshot `periodTotals`와 비교한다.
- 기대 결과:
  - 큰 숫자가 선택한 기간의 `periodTotals` 값과 같다
  - 선그래프(Chart.js) `처리량`이 최근 5분(`5분 전`~`현재`) 처리량을 건/초로 그린다. 값은 2초마다 직전 20초 이동평균이고 최근 판정 이력의 시각으로 계산한다. 2초 간격 정상 운영이면 0.5 부근에서 평평하다
  - 회색 점선 `설정 라인 속도`가 `1000 / intervalMs`(2초 간격이면 0.5)에 있다. 처리량 선이 점선 아래로 내려가면 라인 속도를 못 따라가는 상태다
  - 재검사는 주황 원, 오류는 빨간 삼각형으로 x축 위 해당 시각에 찍히고, 개수가 `재검사·오류 사과` 목록 중 최근 5분 안의 건수와 같다
  - 마우스를 올리면 `HH:MM:SS`와 `처리량 0.50건/초` 또는 `재검사 · 품질 신뢰도 미달` 같은 사유가 나온다
  - 이력이 상한(서버 200건)에 닿아 그보다 오래된 구간은 선이 끊긴다(`처리량 수집 전`). 2초 간격이면 약 6분 40초치가 남아 5분 전체가 채워진다
  - `오늘 재검사 n건 · x.x% · 오판 의심 n건`의 비율이 상단 `오늘 재검사율`과 같다
  - `등급`·`품종` 비율 막대와 범례 `특 n건 (x.x%)`의 분모가 `오늘 품종·품질 집계 대상 n건`의 n이다
  - `선별 목적지별 성공 명령`을 펼치면 snapshot `today.bins`와 같은 목록
  - 하단 문구 `서버 저장 결과 기준 · 시간 초과와 추론 오류는 품종·품질 집계에서 제외`

#### QA-WEB-05-1 처리 중 사과 표시 · P2

- 근거: FR-20·41, #53·#83·#88
- 환경: E3(E1 읽기)
- 절차: 2분 동안 `처리 중 사과` 패널을 본다. 개발자 도구로 snapshot `state.jobs`·`recentCompletedJobs`를 함께 본다.
- 기대 결과:
  - 우하단 패널에 12장이 한 줄로 보이고(PR #115), 아래에 `HH:MM:SS 투입`과 처리 상태가 표시된다. 라인 간격 2초면 2초마다 다음 사과로 바뀐다. 사과가 건너뛰어지지 않는다(1분에 약 30개)
  - 처리 중인 검사가 잠깐 없어도 마지막으로 처리한 사과를 다음 사과가 올 때까지 계속 보여준다(패널 높이가 줄었다 늘었다 하지 않는다)
  - 화면을 처음 열었을 때 처리한 사과가 아직 없으면 12칸 빈 자리와 `처리 중인 사과가 없습니다.`가 보인다

#### QA-WEB-06 통계 CSV 버튼 · P2

- 근거: FR-32
- 절차: 관리자 페이지 `기간 통계` 탭에서 최근 구간 5분을 고르고 `통계 CSV`를 누른다.
- 기대 결과: `cqc-statistics.csv`가 내려받아진다. 내용이 QA-OPS-13 c와 같은 형식이고 `last_5_minutes` 섹션이 있다.

#### QA-WEB-07 시스템 상태 패널 · P2

- 근거: FR-35 (KI-4는 #37에서 해결)
- 기대 결과(PR #115 배포 후): 구성요소 4개가 색 칩으로 한 줄에 보인다. `Simulator` `검사 전송 중`, `Inference` `추론 서비스 준비 완료`, `Backend` `관제 API 응답 중`, `MySQL` `검사 이력 조회 성공`. 정상은 초록, 정지·확인 중은 주황, 오류는 빨강 칩이다. 패널 제목 옆 배지는 모두 정상이면 초록 `모두 정상`, 오류가 있으면 빨강 `확인 필요 n`. 수신 시각은 칩에 마우스를 올리면 보인다.

#### QA-WEB-08 설비·연동 오류 목록 · P2

- 근거: FR-35, FE-06
- 절차: QA-INS-08 이후 시스템 상태 패널의 `설비·연동 오류`를 본다.
- 기대 결과(PR #115 배포 후): 최근 3건이 `HH:MM:SS 추론 오류 · 제어 성공 · 저장 완료` 형식으로 보이고, 4~8번째는 `이전 오류 n건 더 보기`를 펼쳐 본다. 검사 ID는 행에 마우스를 올리면 보인다. 오류가 없으면 `설비·연동 오류 없음`. 같은 건이 좌하단 `재검사·오류 사과`에는 사과 기준(`오류` · `추론 오류`)으로 보인다.

#### QA-WEB-09 Simulator 조작 · P1

- 근거: FE-04·06 capability 기반 조작, FR-18·46·49·54
- 환경: E3 + E2 (E1의 Simulator는 공용이라 조작하지 않는다)
- 절차와 기대:
  1. `입력 정지` 버튼과 `시연 설정`의 동시 처리 수·장애 적용 범위·장애 체크박스가 활성이고 `서버가 허용한 설정만 조작할 수 있습니다. 응답 성공 후 적용됩니다.` 문구가 보인다. 동시 처리 선택지는 `순차 1개`·`병렬 2개`·`병렬 4개`
  2. `입력 정지` → 버튼이 `입력 재개`로 바뀌고 상단에 `입력 정지 · 진행 중 n건은 완료 후 종료`. Network에 `PUT /api/quality/simulator` 200
  3. 장애 `추론 시간 초과` 체크, 범위 `다음 1건` → 상단 `장애 시연 중 · 추론 시간 초과 · 다음 1건 (접수 후 해제)`
  4. `입력 재개` → 다음 검사 1건이 `시간 초과`로 기록되고 경고가 자동으로 사라진다
  5. 다른 탭에서 먼저 설정을 바꾼 뒤 이 탭에서 조작 → 오류 경고(revision 충돌)가 뜨고 다음 snapshot에서 최신 설정으로 맞춰진다
- 끝나면 장애 해제, 동시 처리 1, 입력 재개로 되돌린다.

#### QA-WEB-10 DB 중단 표시와 복구 · P1

- 근거: FR-36, FE-08
- 환경: E3 + E2
- 절차: `docker compose stop mysql`, 60초 관찰, `docker compose start mysql`, 30초 관찰
- 기대 결과:
  - 중단 후 약 5초 안에 상단 경고 `… · 마지막 수신 HH:MM:SS · 기존 화면 유지`. 기존 수치와 표가 지워지지 않고 그대로 남는다
  - 예시 데이터로 바뀌지 않는다(배지가 `브라우저 예시`가 되지 않음)
  - MySQL healthy 후 수 초 안에 경고가 사라지고 수치가 다시 갱신된다

#### QA-WEB-11 Backend 중단 표시와 복구 · P1

- 환경: E3 + E2
- 절차: `docker compose stop backend`, 30초 관찰, `docker compose start backend`
- 기대 결과: QA-WEB-10과 같은 경고와 화면 유지. 개발자 도구에서 `/api/quality/snapshot`이 503 `BACKEND_UNAVAILABLE`. Backend healthy 후 자동 복구된다(새로고침 불필요).

#### QA-WEB-12 검사 이력 창 · P1

- 근거: FR-31, FE-03
- 절차와 기대:
  1. `검사 이력`을 연다 → 창 제목 `검사 이력 관리`, 안내 `서버 보관 이력을 조회합니다. 목록 새로고침 전까지 조회 기준 시각을 유지합니다.`
  2. 품종 `부사`, 품질 `특` → 모든 행이 부사·특이고 페이지가 1로 돌아간다
  3. 선별함 목록에 QA-OPS-03 `bins` 값이 있다. `DEMO_BIN_01` 선택 → 해당 행만
  4. 처리 상태 `시스템 오류` → `$RUN-ins08` 행, 상태 칸 `시스템 오류`
  5. 오류 유형 `추론 오류` → 4와 같은 행 포함
  6. 표시 행 수 50·100·200 전환 → `n / m페이지`가 `total`에 맞게 바뀐다
  7. `다음 페이지`·`이전 페이지` → 행이 겹치지 않는다. 첫 페이지에서 `이전`, 마지막에서 `다음` 비활성
  8. 창을 연 채로 새 검사 1건 → 목록에 안 나타난다. `목록 새로고침` → 나타나고 `최신 이력을 불러왔습니다.`
  9. 시작일을 종료일보다 늦게 → `시작일은 종료일보다 늦을 수 없습니다.`, `CSV 내보내기` 비활성
  10. `초기화` → 모든 필터가 `전체`, 날짜 기본값
  11. 행 표시: 가상 °Brix 소수 첫째 자리(`13.9`), 추론/모델 칸에 추론 시간과 모델 버전, 제어 `성공`, 저장 `완료`, 저신뢰 행 상태 `처리 완료 · 검수`
  12. 오판 의심 선택 `기타` → `오판 의심 표시를 저장했습니다.`, 필터 오판 의심 `기타`로 그 행이 조회된다. `오판 의심 없음`으로 되돌리면 필터에서 빠진다(E1에서는 본인 `$RUN` 행만)

#### QA-WEB-13 이력 CSV 내려받기 · P1

- 근거: FR-32
- 절차: QA-WEB-12에서 품종 `부사`로 거른 뒤 `CSV 내보내기`
- 기대 결과: 파일 이름 `cqc-inspections.csv`. 내용이 같은 필터의 `$BE/v1/quality/inspections.csv?variety=부사&...` 결과와 행 수가 같다(현재 페이지가 아닌 필터 전체). Excel에서 한글이 깨지지 않는다.

#### QA-WEB-14 기간 통계 창 · P2

- 근거: FR-09, FE-05
- 절차: `기간 통계`를 열고 오늘~오늘로 조회, `통계 새로고침`, `기간 통계 CSV`
- 기대 결과: 품종·품질·성공한 선별 명령·오판 의심 표의 수량이 QA-OPS-12 응답과 같다. 비율의 분모는 품종·품질은 `normal`, 오판 의심은 `total`. 날짜가 잘못되면 `시작일과 종료일을 올바르게 선택하세요.`와 CSV 비활성. CSV 파일 이름은 `cqc-period-statistics.csv`, 내용은 QA-OPS-13 a 형식.

#### QA-WEB-15 검수 이미지 창 · P1

- 근거: FR-16·42, FE-07
- 절차와 기대:
  1. 상단 버튼 `검수 이미지 N장`의 N이 snapshot `retention.images`와 같다
  2. 창 제목 `검수 이미지 관리`, 안내 `서버에 보관된 검수 이미지입니다. …`, 필터 `구분`(전체·시스템 오류·저신뢰 재검사)·`오판 의심 필터`, 요약 `시스템 오류 n/100 · 저신뢰 n/200`, 표 열 `검사 ID`·`발생 시각`·`구분`·`사유`·`오판 의심`·`이미지`. 저신뢰 행의 사유 아래에 `품질 55.8% < 60.0%`처럼 기준에 못 미친 신뢰도가 보인다
  3. `미리보기` → 원본 사진이 보인다. `미리보기 닫기`로 닫힌다
  4. 한 행 `삭제` → `선택한 이미지 1장을 삭제할까요?` 확인 → `삭제 확인` 후 그 행만 사라지고 N이 1 줄어든다
  5. `전체 이미지 삭제` → 확인 문구가 떠 있는 동안 새 장애 검사 1건을 보낸다 → 확인 후 확인 창을 연 시점의 이미지만 지워지고 새 이미지는 남는다
  6. 삭제한 이미지의 검사는 검사 이력에 그대로 있다
  7. 이미지가 없으면 `보관된 검수 이미지가 없습니다.`
  8. 다른 곳에서 지운 이미지의 미리보기 → `이미지 조회 불가 · 만료 또는 연결 끊김`
- 4·5는 E2에서 하거나 E1에서는 본인 `$RUN` 이미지로만 한다.

#### QA-WEB-16 장애 원본 비노출 · P2

- 근거: FR-42
- 절차: 메인 화면의 모든 패널과 재검사·오류 사과·설비·연동 오류를 확인하고, 개발자 도구 Network에서 `previews` 요청을 찾는다.
- 기대 결과: 검수 이미지 창을 열기 전에는 검수 원본 미리보기(`/api/quality/previews/<32자리>_<번호>`) 요청이 없고 검수 원본 사진이 화면에 없다. 처리 중 사과 패널의 `live_` 미리보기(#53)는 정상 요청이다.

#### QA-WEB-17 전체 무스크롤 반응형 · P1

- 근거: NFR-11·12, FE-02·08
- 절차: 창 크기 1920×1080, 1600×900, 1366×768, 1280×720, 1024×768, 768×1024, 390×844에서 각각 새로고침하고 콘솔에 붙여넣는다.

```js
const d = document.documentElement;
({ viewport: [innerWidth, innerHeight], doc: [d.scrollWidth, d.scrollHeight],
   transform: getComputedStyle(document.querySelector(".qc-console")).transform,
   panelsInside: [...document.querySelectorAll(".qc-console .panel")]
     .every((el) => el.getBoundingClientRect().bottom <= innerHeight + 1) })
```

- 기대 결과: 모든 크기에서 `doc`이 `viewport`와 같다(전체 페이지 스크롤 없음), `transform`이 `none`, 네 패널이 화면 안에 있다. 표·목록은 패널 안에서만 스크롤된다. 관리자 페이지(`/admin`)는 무스크롤 대상이 아니며 페이지 전체가 스크롤된다. 글자 크기를 줄여 맞추지 않는다.
- 기준값: 10-06 서버 3100에서 7개 크기 모두 통과([FE-08](../../FE-08.md)).

#### QA-WEB-18 proxy 제한 · P2

- 근거: FE 관제 proxy 보안
- 환경: E3. `W=http://localhost:3200/api/quality`

| # | 요청 | 기대 |
|---|---|---|
| a | `curl -s $W/unknown` | 404 `NOT_FOUND` |
| b | `curl -s -X POST $W/snapshot` | 405 (Next가 직접 응답하면 본문이 비어 있을 수 있다) |
| c | `curl -s -X DELETE $W/fault-images -H "Origin: http://evil.example" -d '{"ids":[]}'` | 403 `CROSS_ORIGIN_WRITE` |
| d | `DELETE $W/fault-images` 본문 16,385바이트 이상(검수 이미지 300장 ID 약 11.4KB는 통과) | 413 `BODY_TOO_LARGE` |
| e | `curl -s $W/snapshot` (정상) | 200, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` |
| f | `CQC_QUALITY_BACKEND_URL` 없이 실행 후 `curl -s $W/snapshot` | 503 `BACKEND_UNCONFIGURED` |
| g | Backend 정지 중 `curl -s $W/snapshot` | 503 `BACKEND_UNAVAILABLE` |

#### QA-WEB-19 장시간 실행 · P1

- 근거: FE-08 메모리 누수 점검, #73
- 환경: E1 3100(읽기). 입력은 서버 Simulator가 넣는 실제 검사를 쓴다(따로 보내지 않는다)
- 절차:
  1. 1600×900 창으로 3100을 연다. JS heap·DOM 노드·이벤트 리스너·요청 수를 일정 간격으로 기록한다(FE-08 본시험은 30초 간격 자동 기록).
  2. 3시간 이상 실행한다(10-06 결정, 8시간 대신). 중간의 Jenkins 재배포는 그대로 두고 끊긴 구간을 따로 적는다.
  3. 1시간마다 다른 탭을 10분 띄웠다가 돌아온다.
- 기대 결과: 강제 GC 뒤 heap이 증가 추세 없이 유지, DOM 노드 수가 일정, 끊긴 구간 밖에서 연결 배지가 계속 `서버 관제`, `오늘 저장 검사`가 계속 증가, 브라우저 예외 0건. 재배포로 끊기면 경고가 뜨고 복구 뒤 새로고침 없이 경고가 사라진다.
- 탭 전환: 숨김 중에는 조회가 느려져도 되고, 돌아온 뒤 몇 초 안에 최신 수치로 돌아오며 오류가 없다.
- 기준값: 10-06 3시간 25분 결과 — GC 뒤 heap 6.8~8.7MB, DOM 1,115~1,217개(GC 시점), 예외 0, 탭 복귀 1초([FE-08](../../FE-08.md), #73).

### 5.7 Simulator (QA-SIM)

Simulator는 독립 프로세스(포트 8002, 외부 비공개)이고 관제 API `PUT $BE/v1/quality/simulator`로 조작한다. 모든 변경 요청에는 현재 snapshot의 `revision`을 `expectedRevision`으로 넣는다.

```bash
rev() { curl -s $BE/v1/quality/snapshot | python -c "import json,sys;print(json.load(sys.stdin)['revision'])"; }
sim() { curl -s -w " HTTP%{http_code}\n" -X PUT $BE/v1/quality/simulator -H "Content-Type: application/json" -d "$1"; }
# 예: sim "{\"expectedRevision\":$(rev),\"running\":false}"
```

#### QA-SIM-01 기동 시 자동 재생 · P1

- 근거: FR-18·25 (기본 ON, Docker 시작과 함께 실행), MO PR #32
- 환경: E1 (읽기만)
- 절차: Jenkins 배포 또는 `simulator` 재시작 직후 1분 안에 snapshot을 본다.
- 기대 결과: `components.Simulator.status=healthy`, `state.running=true`, `state.concurrency=1`, `state.intervalMs=2000`, `revision=0`. 아무도 켜지 않아도 오늘 검사 수가 늘어난다.

#### QA-SIM-02 입력 간격 2000ms · P1

- 근거: DM-08 운영 경로 처리량, 결정 기록 09-30
- 환경: E1 (읽기만)
- 절차: `curl -s "$BE/v1/quality/inspections?pageSize=200"`의 `timestamp`를 정렬해 이웃 간격을 계산한다(`qa-` 접두사 기록 제외).
- 기대 결과: 간격 중앙값 2.0초(±0.1초), p90 2.2초 이하, 처리량 초당 약 0.5건, 시간 초과 0건(제한시간 = 라인 속도, #87). 10-01 기준값: 중앙값 2.003초·p90 2.111초·0.5건/초·시간 초과 0/152([원본](../../results/server-simulator-throughput-20261001.json)). 10-05 #87 배포 후: 535건 중 시간 초과 0(빌드·배포 2회 포함).
- 주의: Jenkins 배포(이미지 빌드)가 같은 서버에서 도는 동안은 한 건에 5~9초가 걸린다. dev 푸시 직후 10분은 측정하지 않는다. 측정 시작·종료 시각, 표본 수, 중앙값·p90·처리량·시간 초과 수를 모두 기록한다. QA-SIM-13의 정상 100건 결과에 p90이 없으면 QA-SIM-02 전체 통과를 대신하지 않는다.

#### QA-SIM-03 정지와 재개 · P1

- 근거: FR-18·23 (정지 시 새 입력만 막고 진행 중 요청은 완료, 재개 시 이어서)
- 환경: E2
- 절차:
  1. `sim "{\"expectedRevision\":$(rev),\"running\":false}"`
  2. 10초 동안 snapshot 오늘 검사 수를 2초마다 기록
  3. `sim "{\"expectedRevision\":$(rev),\"running\":true}"`
- 기대 결과:
  1. 200, 응답 snapshot `state.running=false`, `components.Simulator.status=stopped`, `revision` 1 증가
  2. 정지 응답 뒤 진행 중이던 최대 1건만 추가되고 이후 늘지 않는다. `simulator` 컨테이너는 unhealthy로 바뀐다(재생 중이 아니므로 정상)
  3. 200, `running=true`, 검사 수가 다시 늘어난다. 재개 후 첫 묶음의 `source_reference`가 정지 전 마지막 묶음의 다음 순번이다(3.2 DB 조회)

#### QA-SIM-04 revision 충돌 · P2

- 근거: 관제 OpenAPI 409
- 환경: E2
- 절차: 현재 revision을 R로 기록 → `sim '{"expectedRevision":R,"concurrency":2}'` → 같은 R로 다시 `sim '{"expectedRevision":R,"concurrency":1}'`
- 기대 결과: 첫 요청 200(`revision` R+1, `concurrency=2`), 두 번째 409 `{"code":"REVISION_CONFLICT"}`이고 설정은 2로 남는다. 끝나면 1로 되돌린다.

#### QA-SIM-05 설정 입력 검증 · P2

- 환경: E2. 모든 행 `expectedRevision`은 현재 값

| # | 본문에 추가 | 기대 |
|---|---|---|
| a | `"concurrency":3` | 422 `INVALID_SETTINGS` |
| b | `"concurrency":"2"` | 422 `INVALID_SETTINGS` |
| c | `"faults":["DB_ERROR","DB_ERROR"]` | 422 `INVALID_SETTINGS` |
| d | `"faults":["UNKNOWN"]` | 422 `INVALID_SETTINGS` |
| e | `"running":null` | 422 `INVALID_SETTINGS` |
| f | `"speed":1` | 422 `INVALID_SETTINGS` |
| g | `expectedRevision` 없음 | 422 `INVALID_SETTINGS` |
| h | `"intervalMs":1500` | 422 `INVALID_SETTINGS` (1000·2000·3000만 허용) |
| i | `"intervalMs":"2000"` | 422 `INVALID_SETTINGS` (정수만) |
| j | `"intervalMs":null` | 422 `INVALID_SETTINGS` |

- 공통: 422 뒤 `revision`이 바뀌지 않는다.

#### QA-SIM-06 장애 6종 · P1

- 근거: FR-46·47, FR-14·44·45
- 환경: E2. 장애마다 `sim '{"expectedRevision":R,"faults":["<장애>"],"scope":"NEXT"}'`로 다음 1건에만 건다.

| 장애 | 다음 검사 기록 (이력 API) | 비고 |
|---|---|---|
| `INFERENCE_TIMEOUT` | `processingStatus=TIMEOUT`, `errorCode=INFERENCE_TIMEOUT`, `status=FAIL`, `bin=TEST_REINSPECTION_BIN` | 장애 이미지 12장 저장 |
| `INFERENCE_ERROR` | `processingStatus=ERROR`, `errorCode=INFERENCE_ERROR`, `status=FAIL` | 장애 이미지 12장 저장 |
| `DB_ERROR` | 이력에 남지 않는다(저장 실패, 유실 허용) | 바로 다음 정상 건은 저장된다 |
| `CONTROL_REJECTED` | `control=FALLBACK`, `status=REVIEW`, `bin=TEST_REINSPECTION_BIN`, `faults`에 `CONTROL_REJECTED` | 정상 bin 거부 → 재검사 bin 1회 대체 |
| `CONTROL_NO_RESPONSE` | `control=NO_RESPONSE`, `status=REVIEW`, `errorCode=CONTROL_NO_RESPONSE` | 재시도 없음, 성공 bin 통계에 안 셈 |
| `CONTROL_FAILED` | `control=FAILED`, `status=REVIEW`, `errorCode=CONTROL_FAILED` | 재시도 없음 |

- 공통: 장애가 걸린 1건 뒤 snapshot `state.faults=[]`, `revision` 1 증가(다음 1건 자동 해제). 그다음 검사는 정상 처리된다.

#### QA-SIM-07 적용 범위 전체 · P2

- 근거: FR-54
- 환경: E2
- 절차: `faults:["CONTROL_REJECTED","INFERENCE_TIMEOUT"]`, `scope:"ALL"` → 10초 관찰 → `faults:[]`
- 기대 결과: 그 사이 모든 검사가 두 장애를 함께 받는다(시간 초과로 기록). 해제할 때까지 `state.faults`가 유지된다. 웹 상단 경고에 `추론 시간 초과 / 명령 거부 · 전체 신규 요청`이 보인다.

#### QA-SIM-08 재시작 후 위치 복구와 장애 초기화 · P1

- 근거: FR-33·48
- 환경: E2
- 절차:
  1. 장애 `CONTROL_FAILED`·범위 `ALL`, 동시 처리 2로 바꾼다
  2. 최근 저장 검사의 `source_reference`(묶음 ID)를 기록한다
  3. `docker compose restart simulator`
  4. 재기동 후 첫 검사 3건의 `source_reference`와 snapshot을 확인한다
- 기대 결과: 첫 검사가 2의 묶음 바로 다음 순번부터 이어진다(미완료였던 1~2건은 다시 보낼 수 있음). snapshot `state.faults=[]`, `concurrency=1`, `intervalMs=2000`(환경변수 기본값), `running=true`, `revision=0`(장애·설정 초기화, 정상 모드).

#### QA-SIM-09 검사 실패 후에도 입력 지속 · P1

- 근거: FR-19·34 (KI-5는 #37에서 해결, KI-1은 PR #52에서 검증)
- 환경: E2
- 절차: `docker compose stop mysql` 20초 → `docker compose start mysql` → 30초 관찰
- 기대 결과: MySQL이 멈춘 동안에도 Simulator가 계속 보내고 검사는 정상 bin으로 판정된다(저장만 실패). MySQL 복구 뒤 Backend·Simulator 재시작 없이 저장이 다시 늘어난다. `components.Simulator.status`가 `error`로 바뀌지 않는다.

#### QA-SIM-10 Simulator 전용 헤더 인증 · P2

- 근거: BE-07 내부 토큰
- 환경: E1 (B-FL 12장, 당도 13.9). `send`의 curl 인자에 헤더를 덧붙여 보낸다.

| # | 추가 헤더 | 기대 |
|---|---|---|
| a | `X-CQC-Simulator-Faults: DB_ERROR` (토큰 없음) | 403 `Simulator 인증에 실패했습니다` |
| b | `X-CQC-Simulator-Token: wrong` | 403 |
| c | 헤더 없음 | 200 정상 판정(일반 검사는 장애를 받지 않는다) |

- a·b는 DB·장애 이미지에 아무것도 남기지 않는다.

#### QA-SIM-11 목록 끝에서 처음으로 · P3

- 근거: FR-24
- 환경: E2, 동시 처리 4로 약 30분(869묶음)
- 기대 결과: 마지막 묶음 뒤 첫 묶음(`index.json`의 첫 `default_playback` 묶음)부터 다시 보낸다. 같은 묶음이 새 `inspection_id`로 기록된다.

#### QA-SIM-12 라인 속도 변경 · P1

- 근거: #37 Simulator `intervalMs`, 관제 화면 라인 속도(#42)
- 환경: E2
- 절차:
  1. `sim "{\"expectedRevision\":$(rev),\"intervalMs\":3000}"`
  2. 1분 동안 저장 검사의 `timestamp` 간격을 계산한다
  3. `sim "{\"expectedRevision\":$(rev),\"intervalMs\":1000}"` → 1분 관찰
  4. `docker compose restart simulator` → snapshot 확인
- 기대 결과:
  1. 200, 응답 snapshot `state.intervalMs=3000`, `revision` 1 증가. 실행을 멈추지 않고 바로 적용된다
  2. 간격 중앙값 3.0초(±0.1초), 초당 약 0.33건
  3. 간격 중앙값은 `max(1초, 한 건 처리 시간)`이다. 서버컴 한 건 처리 약 1.4~2초라 1초보다 길게 나오고, 요청이 쌓이지 않는다(무한 대기열 없음)
  4. 재시작 뒤 `intervalMs`가 환경변수 기본값 2000으로 돌아온다
- 끝나면 2000으로 되돌린다.

#### QA-SIM-13 정상 100건 연속 (ALL-04 수용 기준) · P1

- 근거: ALL-04, FR-01·26, 결정 기록 09-30·10-05. **아래 기준은 제안이며 10-08 회의에서 확정한다(#65).**
- 환경: E1 (읽기만). 라인 속도 2초·순차 1, 장애 토글 모두 해제. 측정 중 dev 푸시·Jenkins 빌드를 하지 않는다
- 절차: 시작 시각을 적고 3분 30초(약 105건) 기다린 뒤 `curl -s "$BE/v1/quality/inspections?pageSize=200"`에서 시작 시각 이후 기록을 시간순으로 100건 고른다.
- 기대 결과(제안):
  1. 100건이 모두 저장되고 이웃 간격 중앙값 2.0초(±0.1초), 최대 4초 미만(처리 공백 없음)
  2. 시간 초과·추론 오류 0건
  3. 재검사는 저신뢰 사유만 있고 비율 20% 이하(10-02~10-05 운영 13~16%)
  4. 처리량 초당 0.5건(±0.05). 초당 2건 목표는 미달로 기록한다(1.2절)
- 기록: 측정 구간 시작·끝 시각, 커밋, 모델 버전, 재검사 비율

### 5.8 자동 시험 (QA-AUTO)

#### QA-AUTO-01 Python 시험 · P1

- 절차: `python -m pytest tests data/sampling/tests -q`
- 기대 결과: 실패 0. 건너뜀은 실제 MySQL·외부 서비스가 필요한 조건부 시험뿐이고, 건너뜀 사유가 환경변수 미지정(`CQC_TEST_DATABASE_URL` 등)이어야 한다. 건너뜀 수는 기록만 한다.
- 비고: Windows에서 검수 이미지 시험 2개가 `WinError 5`로 실패하면 KI-8로 적고 Linux(Jenkins 또는 Docker)에서 다시 돌린 결과로 판정한다(#99).

#### QA-AUTO-02 MySQL 통합 시험 · P2

- 절차: E2 MySQL에 시험용 DB를 만들고 `CQC_TEST_DATABASE_URL=mysql+pymysql://…/cqc_test python -m pytest tests/api -k mysql -q`
- 기대 결과: 건너뜀 없이 통과.

#### QA-AUTO-03 웹 시험·정적 검사·빌드 · P1

- 절차: `cd cqc-logistics-platform/apps/web && npm test && npx tsc --noEmit && npm run lint && npm run build`
- 기대 결과: 시험 실패 0(10-06 기준 51개), `tsc` 오류 0, ESLint 오류 0(경고는 기록만), 빌드 성공.

## 6. 분담과 실행 순서

### 6.1 파트별 분담

케이스 담당은 그 기능을 만든 파트다. 담당 파트가 실행하고 기록표를 채운다. 실패하면 4절 양식으로 담당 파트에 이슈를 올린다.

| 파트 | 담당 | 케이스 | 수 | 실행 환경 |
|---|---|---|---:|---|
| DM | 조현재 | QA-DEP-02·03, QA-INF-01~08, QA-INS-01~06(모델·임계값 판정), QA-SIM-13(수용 기준) | 17 | E1, QA-INS-06만 E2 |
| BE | 홍준희 | QA-INS-07~17, QA-OPS-01~16, QA-IMG-01~06, QA-SIM-03~07·09~12, QA-AUTO-01·02 | 44 | E1 읽기 + E2 장애 주입 |
| FE | 강성민 | QA-WEB-01~19·05-1, QA-AUTO-03 | 21 | E3(E1 3100 읽기, 조작·장애는 E2 연결) |
| MO | 홍유나 | QA-DEP-01·04~07, QA-IMG-07, QA-SIM-01·02·08 | 9 | 서버 컨테이너·볼륨·재시작, E2 |

- 합계 91개. 4개 파트가 공통으로 쓰는 E2(로컬 Compose)·모델 폴더 준비는 MO와 DM이 돕는다(2절).
- MO-09(#71)는 이 목록에서 반복 실행할 케이스를 골라 자동화한다. 우선 대상: QA-DEP-01~05, QA-INF-01·06, QA-INS-01·07, QA-OPS-01·08·10, QA-SIM-01·02.
- 결과는 ALL-04(#65) 기록표로 모은다. 진행 상황은 ALL-03에만 적는다.

### 6.2 BE-10과 겹치는 케이스

BE-10(#66) 3·4단계는 같은 내용을 격리 환경에서 시험한다. BE-10 결과에 같은 기대값이 증거와 함께 있으면 해당 QA 케이스는 그 결과를 링크해 갈음하고, E1에서 하는 확인만 따로 한다.

| QA 케이스 | BE-10 시험 | 비고 |
|---|---|---|
| QA-INS-07 | BND-01~04, DUP-01·02 (2단계 통과) | E1에서 l~o만 다시 확인 |
| QA-INS-08~12 | INS-07~09, TIM-01~07 (2단계 통과) | E1 가능한 QA-INS-08만 다시 확인 |
| QA-INS-13, QA-OPS-14, QA-SIM-09 | DB-01·02 | |
| QA-INS-14·15 | INS-10~12 (2단계 통과) | |
| QA-OPS-02·12 | OPS-02 | |
| QA-OPS-03~09 | OPS-01 | |
| QA-OPS-10·11 | OPS-03 | |
| QA-IMG-01~06 | IMG-01~05 | |
| QA-SIM-06 | TIM-09 (2단계), E2E-05 | |
| QA-SIM-08 | SIM-01 | |
| QA-SIM-13 | E2E-01 | 기준은 10-08 확정 |
| QA-DEP-06 | E2E-04 | |

### 6.3 실행 순서

학원 서버를 오염시키지 않도록 E1 읽기 케이스를 먼저, 장애 주입은 E2에서 나중에 한다. 측정 중에는 dev에 푸시하지 않는다(Jenkins 재배포).

1. 전원: QA-AUTO-01~03 (BE·FE)
2. E1: QA-DEP-02 → QA-INF 전체 → QA-INS-01~05·07·08 → QA-OPS-01·03~13·15 → QA-IMG-01~05 (DM → BE)
3. E1: QA-OPS-16(본인 `$RUN` 행만), QA-SIM-01·02·10·13 (BE·MO·DM)
4. E3(E1 3100): QA-WEB-01~03·05·05-1·06~08·12~19 (FE)
5. E2: QA-DEP-01·03~07 → QA-INS-06·10~17 → QA-OPS-02·14 → QA-IMG-06·07 → QA-SIM-03~09·11·12 → QA-WEB-04·09~11 → QA-AUTO-02 (MO·DM·BE·FE)

### 6.4 기록표

2026-10-06 BE-10 증거 인계: 6.2의 동일 기대값 재사용 규칙에 따라 아래 행에 기존 실행 결과를 연결했다. 새 시험은 실행하지 않았다. 실행자 `BE-10 기록`은 원 실행 기록의 인계 표기이며 담당자·담당 파트를 변경하지 않는다. 일시는 원 실행일, 커밋·모델은 링크한 실행 절의 기준선이다. `차단(부분 증거)`는 해당 기대값은 검증됐지만 케이스 전체의 입력·환경·E1 확인이나 다른 기대값은 미확인이라는 뜻이다. ALL-04 전체 완료를 뜻하지 않으며 #66 완료와 후속 수용 경계는 6.4.1을 따른다.

| 케이스 | 담당 | 결과 (통과/실패/차단) | 실행자 | 일시 | 커밋·모델 | 비고·결함 번호 |
|---|---|---|---|---|---|---|
| QA-DEP-01 | MO | 통과 | MO-09 재검증 | 2026-10-07 09:51 KST | `328baaaf702f` (#115 이미지 digest 대조) | E1 7개 서비스 healthy·재시작 정책 확인. [자동 점검 결과](../../results/qa-mo-20261007-evidence/live-results.json). |
| QA-DEP-02 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | health 필드 전부 일치, 온도 0.3908/0.3840, decode_workers 8 |
| QA-DEP-03 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | models/selected model.pt·model.json·서버 health SHA 일치(b254206e…) |
| QA-DEP-04 | MO | 통과 | MO-09 재검증 | 2026-10-07 09:51 KST | `328baaaf702f` (#115 이미지 digest 대조) / `cqc-apple-separate12-focal-v2-cal-20260930` | Backend health·임계값·Inference URL·이미지 경로 일치. [자동 점검 결과](../../results/qa-mo-20261007-evidence/live-results.json). |
| QA-DEP-05 | MO | 통과 | MO QA | 2026-10-07 11:50:32 KST | `328baaaf702f` (#115 이미지 ID 고정·대조) | 격리 `cqc-mo09-e2-final-20261007`: `20260929_02 (head)`, 13개 bin 조합·재검사·활성 상태 일치. 시험 컨테이너·전용 볼륨 정리. [원자료](../../results/qa-mo-20261007-evidence/e2-final-restart-evidence.json). |
| QA-DEP-06 | MO | 통과 | MO QA | 2026-10-07 11:50:55 KST | `328baaaf702f` (#115 이미지 ID 고정·대조) | 격리 E2 재시작 전후 이력 17→17·검사 ID 동일·전체 이미지 ID 100개 동일·미리보기 SHA-256 동일, 새 정상 검사 제어·저장 `SUCCEEDED`. [원자료](../../results/qa-mo-20261007-evidence/e2-final-restart-evidence.json). |
| QA-DEP-07 | MO | 통과 | MO-09 재검증 | 2026-10-07 10:22 KST | 작업 HEAD `0ebee874`; 배포 SHA 무관 | 추적 `.env` 없음, `.env.example` MySQL 비밀번호는 `change_me`. 정규식 일치 1건은 동적 시험 비밀번호 설정 코드로 확인. [검토 기록](../../results/qa-mo-20261007.md#history). |
| QA-INF-01 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 키 13개 정확, 부사·특 1.000/0.990(0.9897) |
| QA-INF-02 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 확률 합 1.000, 최댓값=신뢰도=예측 라벨 |
| QA-INF-03 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | FL·LQ·MIS 각 3회 확률 차 0, 표 대비 ±0.005 안(LQ 0.466, MIS 0.513) |
| QA-INF-04 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | decode 98·model 137·total 235ms, inference_time_ms=model |
| QA-INF-05 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 1·4·8·11장 모두 200, used_frame_count 일치 |
| QA-INF-06 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | a~m 13행 상태·문구 일치, 각 오류 뒤 정상 200 |
| QA-INF-07 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 동시 예측 3건 중 /health 71ms |
| QA-INF-08 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 36건 200, total 평균 300·p95 401·최대 473ms(라인 간격 안). p95가 기준 308.8의 1.30배 경계 → DM 기록 |
| QA-INS-01 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 12건 COMPLETED·NORMAL, DEMO_BIN_01~12 기대값 일치 |
| QA-INS-02 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 9·18·14 → 200(BIN_01·02·02), 8.9·18.1·abc·nan·inf → 422 |
| QA-INS-03 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | VIRTUAL_BRIX_MISSING·재검사 bin·통계 포함 |
| QA-INS-04 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | LQ 0.466·LQ2 0.581·MIS 0.512 모두 LOW_QUALITY_CONFIDENCE, sweet |
| QA-INS-05 | DM | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | EDGE 0.629→BIN_01, EDGE2 0.647→BIN_05 |
| QA-INS-06 | DM | 통과(BE-10 갈음) | 조현재(에이전트) | 2026-10-07 10:40~11:20 | dev da6872f 웹 / E1 조회 + QA 중계 | 노트북에 Docker가 없어 E2 미실행. BE-10 INS-02(품종 저신뢰)·INS-04(둘 다 저신뢰) PASS로 갈음 |
| QA-INS-07 | BE | 통과 | BE(#103 보고) | 2026-10-07 | E1 `24e49e1` | 잘못된 ID 422·점 포함 200·중복 409, 중복 전후 공개 history·이미지 불변. DB 직접 비교 없이 공개 응답·데이터 근거로 통과(10-07 DM·FE 합의). [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-INS-08 | BE | 통과 | BE(#103 보고) | 2026-10-08 | E1 `45c33f5` | 손상 PNG 1장 → 200·`REINSPECTION_REQUIRED`·`INFERENCE_HTTP_ERROR`·`TEST_REINSPECTION_BIN`, 제어·저장 성공, 검수 이미지 1장. 시스템 오류 100장 유지·가장 오래된 1장 순환 삭제(허용된 보존 정책). [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-INS-09 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-05 | 2/4 §9 기준선 | [INS-09](../../BE-10-results.md): ID/frames/null/JSON/필수 field 오류 정책 PASS; 지정 케이스 전체 조합은 담당 대조 필요 |
| QA-INS-10 | BE | 통과 | BE(#103 보고) | 2026-10-08 | E2 `45c33f5` | 닫힌 포트 연결 실패 → 200·843.8ms, `INFERENCE_CONNECTION_ERROR`, 재검사·통계 제외, 오류 이미지 12장, 제어·저장 성공. [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-INS-11 | BE | 통과 | BE(#103 보고) | 2026-10-08 | E2 `45c33f5` | Inference 중단 → 200·1096.4ms 연결 오류·재검사, 복구 뒤 다음 검사 정상·Backend 재시작 없음. [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-INS-12 | BE | 통과 | BE(#103 보고) | 2026-10-08 | E2 `45c33f5` | 업무 기한 50ms → 200·797.3ms `INFERENCE_DEADLINE_EXCEEDED`, 예측 null·이미지 12장·통계 제외, late 결과가 판정·제어를 덮어쓰지 않음. [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-INS-13 | BE | 실패 | BE·MO(#117) | 2026-10-08 | E2 `45c33f5` | DB 장애 중 정상 판정·LKG bin·제어 성공, 저장 FAILED 분리, 복구 뒤 재시작 없이 저장 재개는 통과. **HTTP 응답 4.307초로 2초 기준 초과**(이전 MO 회차 4.938초). 원인은 Docker 이름 조회 지연(약 3.3초). **최종까지 보류 확정, 수용 판정에서 응답시간 조건만 예외(KI-10, [#117](https://github.com/yuudong123/CQC/issues/117))** |
| QA-INS-14 | BE | | | | |  |
| QA-INS-15 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-05 | 2/4 §9 기준선 | [INS-10~12](../../BE-10-results.md): 거부 시 대체1회·무응답 추가호출 없음·실패 상태 PASS; QA 케이스 전체 조건은 담당 대조 필요 |
| QA-INS-16 | BE | | | | |  |
| QA-INS-17 | BE | | | | |  |
| QA-OPS-01 | BE | 통과 | BE(#103 보고) | 2026-10-07 | E1 `24e49e1` | snapshot 전체 필드 기대값 충족. [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-OPS-02 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | Linux MySQL8.4, 3/4 §11 | [OPS-02](../../BE-10-results.md): 20건 total20/normal16/excluded4/reinspection8 SQL/API 일치. 이 케이스의 지정5건 분포를 실행한 기록과 구분 |
| QA-OPS-03 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | 3/4 §11 및 #112/35ac952 | [OPS-01·§13.4](../../BE-10-results.md): 실제 DB 이력 변환/정상100 PASS; 전체 지정 행 기대값 대조는 후속 |
| QA-OPS-04 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-05~06 | 2/4 §9·3/4 §11 | [INS-02~09·OPS-02](../../BE-10-results.md): 정상/저신뢰/오류/timeout 상태·통계 정책 PASS; QA 지정 입력 전체는 별도 대조 |
| QA-OPS-05 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | Linux MySQL8.4, 3/4 §11 | [OPS-01](../../BE-10-results.md): 현행 API 필터·SQL ID 대조 PASS; QA 필터 조합별 전체 확인은 후속. model 필터는 #68 |
| QA-OPS-06 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | Linux MySQL8.4, 3/4 §11 | [OPS-01](../../BE-10-results.md): 최신순225건·200+25 pagination PASS; 50/100 및 invalid 쿼리 전체 매트릭스 확인은 별도 |
| QA-OPS-07 | BE | 통과(기존 증거 재사용) | BE-10 기록 | 2026-10-06 | Linux MySQL8.4, 3/4 §11 | [OPS-01·03](../../BE-10-results.md): 조회 snapshotAt 고정 후 신규 검사 제외, 현재 조회와 구분 PASS |
| QA-OPS-08 | BE | | | | |  |
| QA-OPS-09 | BE | 통과(기존 증거 재사용) | BE-10 기록 | 2026-10-06 | Linux MySQL8.4, 3/4 §11 | [OPS-01·03](../../BE-10-results.md): KST 자정 경계·기간 필터·00:00:00.123 대조 PASS |
| QA-OPS-10 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | 3/4 §11 및 #112/35ac952 | [OPS-03·§13.2/13.4](../../BE-10-results.md): 전체 필터 CSV/BOM/KST ms·FE40392행 bytes 일치·정상100 ID 대조 PASS. Excel 수동 표시 등 전체 기대값은 별도 |
| QA-OPS-11 | BE | | | | |  |
| QA-OPS-12 | BE | 통과(기존 증거 재사용) | BE-10 기록 | 2026-10-06 | Linux MySQL8.4, 3/4 §11 | [OPS-02](../../BE-10-results.md): DB/API/snapshot의 total·normal·excluded·품종/품질/bin·inferenceCount 일치. §13.4 정상100 전후 증가량도 일치 |
| QA-OPS-13 | BE | | | | |  |
| QA-OPS-14 | BE | 통과(기존 증거 재사용) | BE-10 기록 | 2026-10-06 | Linux MySQL8.4, 3/4 §11 | [DB-01~02·LOG-01](../../BE-10-results.md): 실제 MySQL 중단 중 조회5 API503, Backend 재시작 없이 복구200·DB 오류 로그 연결 PASS |
| QA-OPS-15 | BE | 통과 | BE(#103 보고) | 2026-10-08 09:20 | E1 `45c33f5` | KI-6. 10건 저장 10/10·시간 초과 0, `periodTotals["1"]` 39 = 직전 60초 history 39, points 합 23 = history 23. 10-07 회차(시간 초과 5건)는 dev 푸시 부하와 겹쳐 판정 제외. [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-IMG-01 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | Linux MySQL8.4, 3/4 §11 | [IMG-01·§13.4](../../BE-10-results.md): 정상/당도누락 이미지0, 저신뢰3종/시스템오류4종 보관·sidecar 정책 PASS. QA 지정 입력/장수 전체와 구분 |
| QA-IMG-02 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | Linux 저장소, 3/4 §11 | [IMG-01~03](../../BE-10-results.md): category/inspectionId 목록·sidecar confidence/threshold/error 정책 PASS; 전체 QA 응답 필드 대조는 후속 |
| QA-IMG-03 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | 3/4 §11 및 #112/35ac952 | [IMG-03~05·§13.3](../../BE-10-results.md): preview·삭제 후410 PASS; PNG hash/모든 잘못된 경로 조합 확인은 별도 |
| QA-IMG-04 | BE | 차단(부분 증거) | BE-10 기록 | 2026-10-06 | 3/4 §11 및 #112/35ac952 | [IMG-05·§13.3](../../BE-10-results.md): 선택 삭제·잔존 목록·preview410 PASS; 전체 지정 선택 조합은 담당 대조 필요 |
| QA-IMG-05 | BE | | | | |  |
| QA-IMG-06 | BE | 통과(기존 증거 재사용) | BE-10 기록 | 2026-10-06 | Linux 저장소, 3/4 §11 | [IMG-02](../../BE-10-results.md): 시스템101→100/저신뢰201→200, 독립 oldest 삭제·최신 유지 PASS; Windows #99와 구분 |
| QA-IMG-07 | MO | 통과 | MO QA | 2026-10-07 11:50:55 KST | `328baaaf702f` (#115 이미지 ID 고정·대조) | QA-IMG-06 조건의 시스템 오류 이미지 100장 생성 후 Backend 재시작. 전체 100개 ID 동일·미리보기 HTTP 200 및 SHA-256 동일. [원자료](../../results/qa-mo-20261007-evidence/e2-final-restart-evidence.json). |
| QA-WEB-01 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 제목·부제·배지 서버 관제 |
| QA-WEB-02 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 30초 snapshot 30회, 간격 중앙 1.007초, 동시 요청 최대 0(중첩 없음) |
| QA-WEB-03 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 품질 신뢰도 미달 사유 표시, 안내문 최근 판정 200건 |
| QA-WEB-04 | FE | 통과 | 조현재(에이전트) | 2026-10-07 | dev 328baaa | 카드 5개가 snapshot today를 그대로 표시(오늘 2,004건·재검사율 11.0%=221/2,004·평균 추론 151.1ms·통계 제외 6·라벨 '예시' 없음). 증가량은 화면이 받은 집계를 그대로 표시하는 코드와 시연·FE-08 연속 관제 중 계속 증가한 관찰로 갈음 |
| QA-WEB-05 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 1·5·10·30분 화면=API(30·166/165·311·902), 설정 라인 속도 0.50 점선, 하단 문구 |
| QA-WEB-05-1 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 12초 동안 12장 유지·사진 5회 교체, 빈 상태 문구 없음 |
| QA-WEB-06 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | cqc-statistics.csv, BOM, last_5_minutes 300행 · **10-08 관리자 페이지(`/admin`) 재확인 통과**(dev `e960d1f`, 로컬 웹 + QA 중계: 조회는 E1, 설정·삭제는 중계 안에서만): 기간 통계 탭 최근 구간 5분 → `cqc-statistics.csv` 325줄·`last_5_minutes` 포함 |
| QA-WEB-07 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 4개 구성요소 문구·수신 시각 표시 |
| QA-WEB-08 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 설비·연동 오류 목록 표시(추론 오류 행). INS-08 본인 기록 대조는 BE 실행 뒤 |
| QA-WEB-09 | FE | 통과(중계) | 조현재(에이전트) | 2026-10-07 10:40~11:20 | dev da6872f 웹 / E1 조회 + QA 중계 | E2 대신 로컬 웹(3202)+QA 중계: 조회는 E1, 장애·설정은 중계 안에서만. 안내문·순차1/병렬2/병렬4·정지/재개 버튼·정지 경고·장애 경고(다음 1건)·revision 충돌 경고와 최신 설정 동기화 확인. 다음 1건 시간 초과 기록·자동 해제는 MO-09 E2 장애 6종으로 갈음 · **10-08 관리자 페이지(`/admin`) 재확인 통과**(dev `e960d1f`, 로컬 웹 + QA 중계: 조회는 E1, 설정·삭제는 중계 안에서만): 안내문·순차 1개/병렬 2개/병렬 4개·입력 정지 → `PUT /api/quality/simulator`·버튼 `입력 재개`·장애 표시(추론 시간 초과·다음 1건)·revision 충돌 경고. 4번(다음 검사 시간 초과)은 중계라 10-07 결과 유지 |
| QA-WEB-10 | FE | 통과(중계) | 조현재(에이전트) | 2026-10-07 10:40~11:20 | dev da6872f 웹 / E1 조회 + QA 중계 | E2 대신 로컬 웹(3202)+QA 중계: 조회는 E1, 장애·설정은 중계 안에서만. DB_UNAVAILABLE 0.5초 뒤 "마지막 수신·기존 화면 유지" 경고, 수치 유지·예시 모드 전환 없음, 복구 2.1초 뒤 경고 해제 |
| QA-WEB-11 | FE | 통과(중계) | 조현재(에이전트) | 2026-10-07 10:40~11:20 | dev da6872f 웹 / E1 조회 + QA 중계 | E2 대신 로컬 웹(3202)+QA 중계: 조회는 E1, 장애·설정은 중계 안에서만. 연결 끊김 1.5초 뒤 경고, proxy 503 BACKEND_UNAVAILABLE, 복구 2.1초 뒤 새로고침 없이 해제 |
| QA-WEB-12 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 제목·부사/특 필터·100행·페이지 이동·이전 비활성·새로고침 문구·날짜 역전 경고·CSV 비활성. 오판 지정(12번)은 #110 BE-10 PASS로 갈음 · **10-08 관리자 페이지(`/admin`) 재확인 통과**(dev `e960d1f`, 로컬 웹 + QA 중계: 조회는 E1, 설정·삭제는 중계 안에서만): 안내 문구·부사/특 필터 50행 전부 일치·100행 1/120페이지·다음 페이지 행 겹침 없음·첫 페이지 이전 비활성·날짜 역전 경고와 CSV 비활성·초기화 |
| QA-WEB-13 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 부사 필터 CSV 28,340행·BOM·25초 다운로드(#111 이후). Backend 대조는 BE-10 §13.2 / 이전: [§13.2](../../BE-10-results.md): #109 FE200 실제 다운로드40392행·Backend bytes/필드/BOM 일치 PASS. 지정 FE 필터 조작 전체 수용은 FE 담당 후속 · **10-08 관리자 페이지(`/admin`) 재확인 통과**(dev `e960d1f`, 로컬 웹 + QA 중계: 조회는 E1, 설정·삭제는 중계 안에서만): 부사 필터 CSV `cqc-inspections.csv` 37,943줄 = 같은 조건 Backend 직접 37,943줄 |
| QA-WEB-14 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 기간 통계 창 표시(전체 1,460·재검사 10.8%·평균 추론 143ms) · **10-08 관리자 페이지(`/admin`) 재확인 통과**(dev `e960d1f`, 로컬 웹 + QA 중계: 조회는 E1, 설정·삭제는 중계 안에서만): 기간 통계 탭 표시(오늘 API total 5,045)·`cqc-period-statistics.csv` |
| QA-WEB-15 | FE | 통과 | 조현재(에이전트) | 2026-10-07 | E1 `24e49e1`(PR #115 포함) | 1~4·6~8 통과(E1, 본인 qa 이미지 1장 삭제 12→11). 5번 전체 삭제는 300장 ID 본문 11,409바이트가 프록시 한도 8,192바이트를 넘어 413이었음(원인 확인). 한도를 16,384바이트로 올리고 300장 삭제 시험을 추가해 수정(0c679cd). 확인 시점 300장만 보내고 새 이미지는 제외하는 로직은 정상. 배포 뒤 서버에서 한 번 더 확인 **서버 재확인(10-07, 수정 배포 뒤): 존재하지 않는 ID 300개(본문 약 11.7KB)로 전체 삭제 요청 → 200, 공용 이미지 300장은 그대로 유지.** · **10-08 관리자 페이지(`/admin`) 재확인 통과**(dev `e960d1f`, 로컬 웹 + QA 중계: 조회는 E1, 설정·삭제는 중계 안에서만): 탭 `검수 이미지 300장` = `retention.images`·안내·요약(n/100·n/200)·열 6개·미리보기(1000px)·닫기·삭제 확인 문구와 요청 ID(한 장은 해당 ID 1개, 전체는 확인 창을 연 시점 300개). 실제 삭제 반영은 같은 코드의 10-07 E1 결과 유지 |
| QA-WEB-16 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 메인 화면 20초: 처리 중 사과 live_ 미리보기 120건, 검수 원본 미리보기 0건(기대값을 live_ 제외로 정정) |
| QA-WEB-17 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 10-06 FE-08 결과 갈음: 서버 3100 7개 크기 · **10-08 관리자 페이지(`/admin`) 재확인**(dev `e960d1f`, 로컬 웹 + QA 중계: 조회는 E1, 설정·삭제는 중계 안에서만): 관제 화면은 상단 버튼이 링크 2개로 줄었을 뿐 패널 배치가 같아 10-06 결과 유지, 관리자 페이지는 무스크롤 대상 아님 |
| QA-WEB-18 | FE | 통과 | 조현재(에이전트) | 2026-10-07 | dev da6872f 웹 / E1 조회 + QA 중계 | a~e는 E1 3100(a 404·b 405·c 403·d 413·e 헤더). f: Backend 주소 빈 값으로 실행 → 503 BACKEND_UNCONFIGURED. g: 중계 끊김 → 503 BACKEND_UNAVAILABLE |
| QA-WEB-19 | FE | 통과 | 조현재(에이전트) | 2026-10-07 09:27~09:40 | dev da6872f / cal-20260930 | 10-06 FE-08 결과 갈음: 3시간 25분 누수 없음(#73) |
| QA-OPS-16 | BE | 통과 | BE(#103 보고) | 2026-10-07 | E1 `24e49e1` | OTHER 지정·판정 불변·통계 0→1, NONE 복구 1→0, 잘못된 값 422·없는 ID 404. [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-SIM-01 | MO | 통과 | MO QA | 2026-10-07 11:50:30 KST | `328baaaf702f` (#115 이미지 ID 고정·대조) | 격리 E2 기동 12.892초 후 `healthy`, running=true, concurrency=1, intervalMs=2000, revision=0. 오늘 검사 4→5 증가. E1 기동 관찰 대체 여부 공동 확인 필요. [원자료](../../results/qa-mo-20261007-evidence/e2-final-restart-evidence.json). |
| QA-SIM-02 | MO | 통과 | MO-09 재검증 | 2026-10-07 09:51~09:54 KST | `328baaaf702f` (#115 이미지 digest 대조) / `cqc-apple-separate12-focal-v2-cal-20260930` | 새 100건: 중앙값 2.002초·p90 2.163초·최대 2.398초·0.501건/초·시간 초과 0. [원자료](../../results/qa-mo-20261007-evidence/live-normal-100.json). 10-06 p90 2.233초 실패 이력·원인 미확정은 유지. |
| QA-SIM-03 | BE | | | | |  |
| QA-SIM-04 | BE | | | | |  |
| QA-SIM-05 | BE | | | | |  |
| QA-SIM-06 | BE | | | | |  |
| QA-SIM-07 | BE | | | | |  |
| QA-SIM-08 | MO | 통과 | MO QA | 2026-10-07 11:51:55~11:52:13 KST | `328baaaf702f` (#115 이미지 ID 고정·대조) | `CONTROL_FAILED`/ALL·동시2 설정 후 재시작. 이전 묶음 index 20, 재기동 후 21·22·23 순서. faults=[]·동시1·간격2000·running=true·revision=0. [원자료](../../results/qa-mo-20261007-evidence/e2-final-restart-evidence.json). |
| QA-SIM-09 | BE | | | | | #45 |
| QA-SIM-10 | BE | 통과 | BE(#103 보고) | 2026-10-07 | E1 `24e49e1` | 토큰 없음·잘못된 토큰 403, 공개 history·이미지 부작용 없음, 일반 요청 200. 공개 데이터 근거로 통과(10-07 DM·FE 합의). [#103 BE 결과](https://github.com/yuudong123/CQC/issues/103) |
| QA-SIM-11 | BE | | | | |  |
| QA-SIM-12 | BE | | | | |  |
| QA-SIM-13 | DM | 통과 | 조현재(에이전트)·MO-09·BE-10 | 2026-10-06~07 | dev 328baaa / cal-20260930 | 제안 기준(간격 중앙 2.0±0.1초·최대 4초 미만·시간 초과/오류 0·재검사 20% 이하·0.5±0.05건/초)으로 판정. 다른 시험과 겹치지 않은 회차: 10-06 14:23(중앙 1.996·최대 2.500·0.500건/초·오류 0, MO-09), 10-07 09:23(중앙 1.997·p90 2.182·최대 3.013·재검사 10%·오류 0). 다른 시험과 겹친 10-06 11:04·10-07 09:27 회차는 판정에서 제외. 저장·통계·CSV 100건 일치는 BE-10 E2E-01 |
| QA-AUTO-01 | BE | | | | |  |
| QA-AUTO-02 | BE | | | | |  |
| QA-AUTO-03 | FE | 통과 | 조현재(에이전트) | 2026-10-07 11:40 | dev 328baaa | 웹 시험 52/52, tsc 0, ESLint 오류 0·경고 5(기존 시험 파일 미사용 변수), next build 성공 |

### 6.4.1 BE-10 완료 증거와 ALL-04 후속 경계

[BE-10 결과 §14](../../BE-10-results.md)의 #66 원래 완료 조건은 충족했고 기록 인계를 완료했다. 정상100은 직접 HTTP 기능 검증으로 충족했으며 인증 Simulator 전체 수용을 대신하지 않는다. 장애·저신뢰3종·실제 socket late-result·MySQL 중단/복구는 2/4·3/4의 같은 정책 기대값을 재사용한다. 지정 입력·조합 또는 E1 확인이 다른 QA 행은 부분 증거로 유지하며 불필요하게 같은 기능을 재시험하지 않는다.

원 실행 기준선과 raw 증거는 BE-10 결과 §9·§11·§13에 있다. 3/4는 Linux/MySQL8.4·migration `20260929_02`·Backend `2c859dd`, 실제 배포 재시험은 Jenkins112·SHA `35ac95250a39fd659ef46a8e4d064733bcc9e57c`·모델 `cqc-apple-separate12-focal-v2-cal-20260930`이다. 서로 다른 환경의 증거를 최신 배포 runtime 직접 증거로 대체하지 않는다.

ALL-04 전체 수용·Simulator 경로·목표환경 CPU/성능은 #65/#103, 자연 timeout 정량 기준은 #65, container/image/pending/runtime·migration 운영 증거는 #96, model 필터 계약은 #68에 남긴다. 최신 정상100 직접 SQL 추가 감사는 권장사항이며 #66 Close blocker가 아니다. BE-10은 완료, 현재 미해결 제품 FAIL0이며 #66 Close 가능하다. ALL-04 전체는 완료로 표시하지 않는다. Issue 댓글/상태 변경 없이 문서에 인계 범위만 연결했다.

### 6.5 MO 담당 검토와 기존 예비 증거 (2026-10-06)

이 절은 #103의 파트별 검토용이다. 6.4에는 BE-10 기존 증거를 인계했으며 나머지 최종 기록은 기준·분담 합의와 담당 검토 후 채운다. MO-09가 다른 파트의 케이스를 자동 실행해도 6.1 담당은 바뀌지 않는다. MO-09 출력은 6.4와 같은 7열이고 담당을 이 문서에서 가져온다. 부분 검증·자동 회귀·제안 기준은 관찰 통과와 전체 수용 결과를 구분해 기록표에 차단으로 남긴다.

| MO 담당 케이스 | 확인된 증거 | 남은 확인 |
|---|---|---|
| QA-DEP-01 | 10-06 09:54 KST, `cqc-cicd` 7개 서비스 healthy·재시작 정책 자동 확인 | 배포 SHA를 식별해 최종 회차 기록 |
| QA-DEP-04 | 최신 재검증 11:04 KST: Backend health 필드·임계값 2개·Inference URL·이미지 경로 통과 | 최종 회차의 환경·증거 기록 |
| QA-DEP-05 | 격리 MySQL 회귀 시험 전 migration 실행 | `alembic current`와 13개 seed 조합·활성 상태 직접 대조 |
| QA-DEP-06 | 이번 예비 회차의 서비스 재시작·보존 증거 없음 | E2에서 위 절차 실행 또는 6.2 BE-10 E2E-04의 동일 기대값 증거 검토 |
| QA-DEP-07 | 이번 예비 회차의 저장소 비밀값 검사 증거 없음 | 추적 파일 검사 실행·결과 기록 |
| QA-IMG-07 | 이번 예비 회차의 재시작·미리보기 보존 증거 없음 | E2에서 동일 이미지 ID·HTTP 200 확인 |
| QA-SIM-01 | 09:54 현재 상태 healthy·자동 재생 설정·revision 0 확인 | 기동 직후 1분 관찰 및 검사 증가 기록 |
| QA-SIM-02 | 최신 100건 중앙값 1.998초·p90 2.277초·처리량 0.494건/초·시간 초과 0. p90 기준 초과로 실패 | 간격 증가 원인 확인·담당 검토 |
| QA-SIM-08 | 이번 예비 회차의 Simulator 재시작 증거 없음 | 묶음 순서·위치 복구·설정 초기화 확인 또는 BE-10 SIM-01 증거 검토 |

기존 결과 원문은 [MO-09 예비 증거](../../results/mo09-qa-preliminary-20261006.json)에 보존했다. 원 실행자는 `MO-09 automation`이며 문서의 기준 커밋과 실행 코드·배포 이미지의 커밋은 별도로 기록한다.

| 예비 실행 범위 | 실제 관찰 | 수용시험에서의 사용 범위 |
|---|---|---|
| QA-SIM-13 정상 100건 | 10-06 10:02 KST, 저장 100·간격 중앙값 2.014초·최대 2.972초·0.494건/초·재검사 10·시간 초과/추론 오류 0 | 제안 기준의 예비 결과. DM·팀이 10-08 기준을 확정한 뒤 재사용 여부 결정 |
| QA-SIM-06 E2 장애 6종 | 10:35~10:36 KST, 별도 `cqc-mo09-e2-20261006`의 실제 서비스에 NEXT 주입. 장애 행의 상태·자동 해제 revision·후속 정상 저장 확인 | BE 검토용 부분 증거. 추론 장애 이미지 12장, 제어 재시도 횟수·성공 bin 통계는 이 실행에서 직접 확인하지 않아 전체 케이스 통과로 옮기지 않음 |
| DB_ERROR 주입 | NEXT 설정 자동 해제·DB_ERROR 이력 행 부재·후속 정상 저장 | 오류 검사 ID 자체와 실제 MySQL 중단·복구는 미확인. QA-INS-13·QA-SIM-09를 대신하지 않음 |
| 격리 자동 회귀 8항목 | 시간 초과·DB LKG·제어 거부·장애 6종·이미지 순환·CSV·이력 순환 알고리즘 통과 | 개별 회귀 증거. QA-AUTO-01 전체 실행이나 E2 중단·재시작 수용시험을 대신하지 않음. 이력은 5/2 시험 한도 |

- 정상 100건·E2 실제 서비스의 모델 버전은 `cqc-apple-separate12-focal-v2-cal-20260930`. 배포 이미지 Git SHA는 미확인이다. 격리 회귀의 작업 HEAD는 `f1521360011c`이며 미커밋 변경이 있었다. 문서 기준 `2c859dd`에서 전체 시험을 실행했다는 뜻이 아니다.
- E2 시험 컨테이너·전용 볼륨은 종료 후 제거했고, 운영 `cqc-cicd` 7개 서비스 healthy를 다시 확인했다.
- 회의에서 남은 결정: QA-SIM-13 기준, 6.1 분담, E2 주입·중단·복구 진행 방식과 기존 증거 재사용 범위. 합의·최종 결과를 #65에 기록한다.

### 6.6 최신 dev 자동화 재검증 (2026-10-06)

실행 코드 HEAD는 `3504195` + MO-09 미커밋 수정이다. 원본 스크립트는 배포 이미지 SHA와 실행 코드 HEAD를 구분한다. 최신 결과와 세부 절차는 [MO-09](../../MO-09.md)에 기록한다.

- 11:04~11:07 KST 정상 100건 관찰: 저장 100·간격 중앙값 1.998초·p90 2.277초·최대 4.141초·0.494건/초·재검사 12·시간 초과/추론 오류 0. QA-SIM-02 p90 기준 및 QA-SIM-13 최대 공백 제안 기준을 넘겨 실패했다. 앞선 예비 회차 통과로 이 실패를 덮지 않는다.
- Backend 상태·임계값·주소·이미지 경로와 모델 상태·체크섬, 컨테이너 구성은 자동 관찰 통과. Simulator 기동 직후 관찰 및 CSV의 남은 수동 확인은 부분 검증으로 기록표 차단을 유지한다.
- 임시 DB의 최초 재검증은 준비 단계 차단이며, 초기화용 서버 대신 최종 TCP 서버를 확인하도록 수정했다. 원문은 [MO-09 예비 증거](../../results/mo09-qa-preliminary-20261006.json)에 회차별로 보존한다.
- 격리 자동 회귀 최신 회차(`outputs/mo09-latest-isolated-final-20261006/`)는 7개 항목 통과. QA-IMG-06은 Windows `WinError 5` 원문을 보존하고 Linux 컨테이너에서 1 passed로 재확인했다.
- E2 상세 장애 회차(`outputs/mo09-e2-detailed-20261006/`)는 장애 6종의 상태·NEXT 해제·후속 정상 저장, 추론 장애 이미지 12장, 제어 시도 횟수를 확인했다. 전체 통계·중단 복구는 남았다.
- 14:07 시작한 첫 재측정은 14:12경 Compose 컨테이너 교체로 차단됐다. 배포 후 10분 안정 시간을 기다린 14:23~14:25 새 100건은 중앙값 1.996초·p90 2.233초·최대 2.500초·처리량 0.500건/초·재검사 12·오류 0이다. QA-SIM-13 제안 기준은 관찰상 충족했으나 기준 합의 전 기록표는 차단, QA-SIM-02는 p90 2.2초 기준을 0.033초 초과해 실패다. 원문은 `outputs/mo09-live-repeat-stable-20261006-1413/`에 보존했다.

### 6.7 MO 재검증·출처 보완 (2026-10-07)

- MO 담당 9건의 최신 실행 기대값 충족. 6.4에 E1 관찰·저장소 검토·격리 E2 결과를 환경별로 기록.
- QA-SIM-02 새 100건 p90 2.163초 통과. 10-06 두 회차 실패 및 원인 미확정 유지.
- 현재 배포는 Jenkins #115 / `328baaaf702f` 이미지 digest 4/4 대조. 최종 E2 서비스 이미지도 같은 빌드 ID로 고정·3/3 대조.
- QA-SIM-13 제안 기준 승인은 미정. SIM-01의 E2 기동 증거를 E1 신규 배포 관찰로 대체할지, BE-10 증거 재사용 범위는 공동 확인 필요.
- [보존본·최종 E2 결과](../../results/qa-mo-20261007.md#summary), [회의 검토안](../../results/qa-mo-20261007.md#meeting), [이슈 초안](../../results/qa-mo-20261007.md#drafts) 준비. #65 전체 수용 완료 판정은 미실행.

## 7. 갱신 규칙

- 1.2의 제외 항목이 dev에 병합되면 해당 영역 케이스를 추가하고 제외 표에서 지운다.
- 임계값·모델 버전·bin seed가 바뀌면 3.3·3.4 표와 QA-DEP-02·04, QA-INS-01·04~06 기대값을 함께 고친다.
- 알려진 결함이 고쳐지면 1.3에서 지우고 해당 케이스 비고를 비운다.
