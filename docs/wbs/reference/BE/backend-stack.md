# CQC Backend 기술 스택 및 개발 기준

- 담당자: 홍준희
- 기준일: 2026-09-21
- 상태: Backend 구현 기준과 Backend→Inference 논리 계약 확정. 물리 DB 계약·세부 오류 계약·성능시험 대기 항목은 별도 표시

## 1. 목적과 원칙

이 문서는 CQC Backend의 기술 선택, 코드 배치, 동기·비동기 경계, 개발 명령과 테스트 기준을 정의한다. 물리 DB 스키마나 아직 합의되지 않은 API 값을 대신 확정하지 않는다.

약 3주 안에 구현·통합해야 하는 MVP이므로 FastAPI + MySQL 기반의 단순한 구조, Windows와 Linux·Docker에서 재현 가능한 구성, Mock Inference로 검증 가능한 책임 분리를 우선한다. Java/Spring 구조를 그대로 복제하거나 필요가 확인되지 않은 분산 시스템과 추상화를 추가하지 않는다.

## 2. 현재 프로젝트 구조와 보호 영역

```text
CQC/
├─ configs/
├─ docs/
├─ models/
├─ notebooks/
├─ outputs/
├─ scripts/
├─ src/
│  ├─ api/
│  ├─ data/
│  ├─ inference/
│  ├─ models/
│  ├─ training/
│  ├─ web/
│  └─ __init__.py
└─ tests/
```

현재 Backend 구현은 시작 전이며 `src/api/`에는 placeholder만 있다. 데이터·모델·Inference 구현과 관련 테스트는 이미 존재하므로 Backend는 확정된 서비스 경계와 계약을 기준으로 연동한다.

- `src/api/`: README에서 Backend 영역으로 정의되어 있으므로 Backend 코드의 기준 위치로 사용한다.
- `src/inference/`: 데이터·모델 담당자의 HTTP 추론 서비스 영역이다. Backend HTTP Client를 넣지 않는다.
- `src/models/`: 시스템 모델 구조·코드 영역이다. SQLAlchemy DB Model을 넣지 않는다.
- 루트 `models/`: 로컬 모델 파일·체크포인트 등 Git 제외 산출물 영역이다.
- `src/data/`, `src/training/`, `src/web/`: 기존 담당 영역을 유지한다.

Backend 작업을 이유로 위 폴더를 이동·병합·변경하지 않는다.

## 3. 확정 기술 스택

| 영역 | 선택 | 목적과 선택 이유 |
|---|---|---|
| 언어 | Python | 데이터·모델 생태계와 일치하며 FastAPI 지원이 안정적이다. |
| API | FastAPI | HTTP API, OpenAPI, dependency와 애플리케이션 진입점을 단순하게 구성한다. |
| Schema | Pydantic 2 | 요청·응답·Inference 응답의 타입·형식·직렬화 계약을 관리한다. |
| 설정 | pydantic-settings 2 | 환경변수와 비밀값·timeout·threshold를 타입 검증한다. |
| ORM·SQL | SQLAlchemy 2.0, sync Session | MySQL 저장·조회·트랜잭션을 단순하게 관리하고 Core SQL도 병행할 수 있다. |
| MySQL Driver | PyMySQL | 순수 Python이라 Windows 설치가 쉽고 native build 의존성이 적다. |
| Migration | Alembic | Schema 변경 이력과 빈 MySQL 재현을 관리한다. |
| Inference Client | httpx AsyncClient | multipart, async 외부 대기, transport timeout, 연결 풀과 test transport를 지원한다. |
| ASGI Server | Uvicorn | FastAPI를 로컬과 컨테이너에서 같은 방식으로 실행한다. |
| Multipart | python-multipart | FastAPI의 `multipart/form-data` 요청 파싱에 필요하다. |
| Test | pytest | 단위·API·DB·통합 테스트와 FastAPI 테스트 도구를 함께 사용한다. |
| Lint·Format | Ruff | Black·isort·flake8을 따로 구성하지 않고 공통 규칙을 적용한다. |

Pydantic Schema와 SQLAlchemy DB Model은 분리한다. validator에서 DB·HTTP를 호출하거나 비즈니스 정책을 실행하지 않는다. CSV는 우선 표준 라이브러리를 사용한다. Kafka, Redis, Celery, RQ, CQRS와 Event Sourcing은 MVP에 도입하지 않는다.

## 4. 버전 정책

Python은 `>=3.13,<3.14`를 기준으로 한다. 기준일 현재 3.13은 bugfix 지원 중이고 Windows·Linux와 선택 라이브러리 지원 범위를 만족한다. 최신 3.14를 즉시 채택하지 않아 데이터·모델 도구와 팀 환경의 호환 위험을 줄인다.

| 항목 | 초기 허용 범위 |
|---|---|
| Python | `>=3.13,<3.14` |
| FastAPI | `>=0.141,<0.142` |
| Pydantic | `>=2.13,<2.14` |
| pydantic-settings | `>=2.15,<2.16` |
| SQLAlchemy | `>=2.0,<2.1` |
| Alembic | `>=1.20,<1.21` |
| httpx | `>=0.28,<0.29` |
| PyMySQL | `>=1.2,<1.3` |
| pytest | `>=9.1,<9.2` |
| Ruff | `>=0.16,<0.17` |
| Uvicorn | `>=0.53,<0.54` |
| python-multipart | `>=0.0.32,<0.0.33` |

0.x 라이브러리는 호환 변화 가능성이 있어 minor 범위를 고정한다. SQLAlchemy 2.1과 httpx 1.0의 prerelease는 사용하지 않는다. 정확한 patch는 dependency lock 또는 constraints 파일에 기록하고 CI가 같은 해석 결과를 설치하게 한다. 새 minor·major는 Windows와 Linux에서 API·DB·Inference·migration 테스트 후 함께 올리며 팀원이 각자 `latest`를 설치하지 않는다.

## 5. Backend 코드 배치

기존 `src/api/` 의미를 유지하는 다음 구조를 권장한다. 이번 문서 작업에서는 디렉터리를 만들지 않는다.

```text
src/
├─ api/
│  ├─ main.py                 # FastAPI app factory·lifespan
│  ├─ routers/                # HTTP 입출력과 Service 호출
│  ├─ schemas/                # Pydantic 계약
│  ├─ services/               # orchestration과 정책
│  ├─ repositories/           # MySQL 저장·조회·집계
│  ├─ db/                     # SQLAlchemy Model·Session·metadata
│  ├─ clients/                # Backend용 Inference HTTP Client
│  ├─ control/                # 내부 Virtual Control
│  └─ core/                   # 설정·공통 예외·Enum
└─ simulator/                 # 별도 실행 단위인 Simulator 후보
```

새로 필요할 수 있는 디렉터리는 위 `src/api/` 하위 폴더와 `src/simulator/`다. README가 `src/api/`를 Backend 영역으로 이미 지정했으므로 별도 `src/backend/`는 만들지 않는다. migration과 dependency 파일 위치는 Backend 골격 및 MLOps 실행 방식과 함께 확정한다.

## 6. 책임과 의존성

```text
Router
  → Service
      ├─ Repository → MySQL
      ├─ Inference Client → Inference API
      └─ Virtual Control
```

- Router: HTTP 요청·응답, Schema 처리, dependency 주입과 Service 호출
- Service: 검사 흐름, confidence·timeout·오류·bin 정책과 기능 간 조정
- Repository: MySQL 저장·조회·수정·삭제와 통계·집계
- Inference Client: multipart 호출, transport 처리와 응답 검증
- Virtual Control: bin 명령과 성공·실패·거부·무응답 처리
- Simulator: 시연 전용 `data/processed/realtime-apple-arrival-demo/index.json` 기본 12장 묶음 순회, `request.json` 순서·metadata 전송, 500ms 간격, 시작·정지·반복과 position 복구. 묶음 안에서 대표 이미지를 다시 고르지 않음

Router의 직접 SQL/httpx 호출, Repository의 Inference 호출, Inference Client의 bin 결정, Simulator의 DB 수정을 금지한다. Service·Repository·Client처럼 의존성·상태가 있는 곳에는 클래스를 사용할 수 있고 단순 계산·변환·CSV formatting은 함수로 작성할 수 있다.

Generic Repository, 구현체 하나뿐인 Interface·Factory, 복잡한 Unit of Work, Base Class 남용과 깊은 상속은 도입하지 않는다.

## 7. Sync·Async 정책

### Inference HTTP

검사 orchestration과 Inference Client는 `async def`와 lifespan에서 재사용하는 `httpx.AsyncClient`를 사용한다.

- 외부 대기 중 다른 검사 요청을 처리한다.
- 요청마다 Client를 만들지 않고 연결 풀을 재사용한다.
- Client 생성·종료는 FastAPI lifespan에서 관리한다.
- multipart 전송부터 응답 전체 수신까지 측정한다.
- Simulator가 보낸 이미지와 metadata의 `view_index` 대응 순서를 유지하며 Backend에서 대표 프레임을 다시 선택하거나 metadata를 변경하지 않는다.

### MySQL

MySQL은 SQLAlchemy sync Session과 PyMySQL을 사용한다.

- 요청 또는 논리 DB 작업마다 Session을 생성·종료한다.
- Session을 요청·스레드·task 사이에 공유하지 않는다.
- Inference 대기 중 DB transaction을 열어두지 않는다.
- 검사 `async def` 흐름의 동기 DB 작업은 명시적 threadpool 경계에서 짧게 실행한다.
- 이력·통계처럼 동기 I/O 중심 endpoint는 일반 `def`로 작성할 수 있다.

FastAPI가 직접 호출하는 일반 `def` endpoint·dependency는 threadpool에서 실행되지만 `async def` 안에서 직접 부른 일반 함수는 자동 전환되지 않는다. AsyncSession과 async MySQL driver는 실제 DB 병목이 측정되기 전에는 도입하지 않는다.

## 8. DB와 Migration

SQLAlchemy URL은 `mysql+pymysql://...` 형식을 사용하고 실제 접속 정보는 `DATABASE_URL`로 주입한다.

- 초기 Schema부터 Alembic revision으로 관리한다.
- `autogenerate` 결과의 타입·nullable·index·constraint와 downgrade를 검토한다.
- 앱 시작 시 `metadata.create_all()`로 migration을 대신하지 않는다.
- migration history는 단일 선형 흐름을 유지한다.
- Backend는 revision과 명령을 제공하고 MLOps와 적용 시점·실패 처리를 협의한다.
- 통계·순환 삭제가 ORM으로 불명확하면 SQLAlchemy Core 또는 명시적 SQL을 제한적으로 사용한다.

물리 테이블·관계·키·인덱스는 별도 DB 설계 문서에서 확정한다.

## 9. Inference HTTP와 late result

Backend는 모델을 로드하거나 전처리를 중복 구현하지 않는다. Mock과 실제 Inference는 같은 논리 계약을 사용한다.

전체 처리 흐름은 다음으로 확정한다.

```text
Simulator가 시연 전용 목록의 사전 구성 12장 묶음을 로드
  → Backend가 이미지와 metadata를 변경 없이 중계
  → Inference가 최대 12장으로 추론
```

기본 시연의 대표 이미지 선택은 데이터 묶음 생성 단계에서 완료된다. Simulator는 `request.json`의 이미지 순서와 metadata를 유지하고 Backend는 이를 재정렬·교체·축소하지 않는다. Backend는 이미지 수와 metadata 대응 관계 등 계약 유효성만 검사한 뒤 Inference에 전달한다. Backend↔Inference 입력 인터페이스는 1장 이상 최대 12장과 multipart 전체 24MiB로 고정한다.

### Backend → Inference 요청

Endpoint는 `POST /v1/predict`, Content-Type은 `multipart/form-data`다.

| 필드 | 의미 | 규칙 |
|---|---|---|
| `inspection_id` | 전체 처리 흐름의 공통 검사 식별자 | Simulator에서 받은 값을 변경하지 않고 전달 |
| `images` | 대표 이미지 반복 파일 필드 | 1장 이상 최대 12장, PNG·JPEG |
| `view_index` | 이미지별 뷰 순번 | 각 `images` 항목과 같은 순서로 대응 |
| `angle_direction` | 이미지별 촬영 방향 | 각 `images` 항목과 같은 순서로 대응 |
| `verticality_angle` | 이미지별 수직각 | 각 `images` 항목과 같은 순서로 대응 |
| `horizontality_angle` | 이미지별 수평각 | 각 `images` 항목과 같은 순서로 대응 |

이미지와 네 metadata 목록은 `view_index` 순서로 일대일 대응한다. Backend는 이미지 수와 각 metadata 항목 수가 같은지, `view_index` 대응 관계가 유효한지 검사하되 값이나 순서를 변경하지 않는다. `group_no`와 정답 품종·품질은 Inference에 전달하지 않는다.

### Inference → Backend 응답

| 필드 | 의미 |
|---|---|
| `inspection_id` | 요청과 동일한 검사 식별자 |
| `predicted_cultivar` | 품종 예측값 |
| `cultivar_probabilities` | `fuji`·`yanggwang`을 key로 가진 확률 객체 |
| `cultivar_confidence` | 선택된 품종의 confidence |
| `predicted_grade` | 품질 예측값 |
| `quality_probabilities` | `L`·`M`·`S`를 key로 가진 확률 객체 |
| `quality_confidence` | 선택된 품질의 confidence |
| `inference_time_ms` | 모델 추론 시간 |
| `model_name` | 모델명 |
| `model_version` | 모델 버전 |
| `preprocessing_version` | 전처리 버전 |
| `used_frame_count` | 패딩을 제외하고 실제 추론에 사용한 이미지 수 |

Backend는 응답의 `inspection_id`가 요청과 같은지 검증하고, 확률 객체의 class index나 순서를 추측하지 않는다. 정상 응답의 `used_frame_count`는 `1..12` 범위이며 padding을 제외한 요청 이미지 수와 같아야 한다.

최신 모델 설정은 `separate` 구조, 대표 12장, 품종·품질 confidence threshold 각각 0.50, 기능 통합용 모델 버전 `cqc-apple-separate12-v1.0.0`이다. 다만 최종 Test 품질 Macro F1이 승인 기준에 미달했으므로 이 패키지를 승인·운영 배포 모델로 표현하지 않는다.

현재 `src/inference/api.py`는 `images`만 받고 `src/inference/schemas.py` 응답에는 `inspection_id`와 `used_frame_count`가 없다. 따라서 Backend 통합 전에 실제 Inference 구현과 생성 OpenAPI를 위 확정 계약에 맞추고 계약 테스트를 통과해야 한다.

500ms business deadline은 Backend가 요청을 전송한 시점부터 응답 전체를 받은 시점까지다. connect·read·write·pool transport timeout은 네트워크 자원 제한이므로 별도로 설정한다.

```text
500ms 안에 완료 → 응답 검증과 판정 정책 적용
500ms 초과      → 즉시 재검사 bin 확정
                  필요한 범위에서 HTTP 작업 유지
                  늦은 결과는 진단용으로만 저장
```

- late result는 확정된 bin과 정상 품종·품질 통계를 변경하지 않는다.
- late result 저장에는 요청의 DB Session을 재사용하지 않는다.
- DB 장애와 Backend 재시작에 따른 유실을 허용한다.
- 무제한 background task와 Kafka·Redis·Celery·RQ·별도 broker를 사용하지 않는다.

프로세스 내부 bounded background task가 최소 후보지만 최대 개수, registry, 종료·정리와 transport 최대 대기시간은 Backend 설계·성능시험에서 확정한다.

## 10. 환경변수 초안

| 변수 | 목적 | 상태 |
|---|---|---|
| `APP_ENV` | local·test·production 구분 | 초안 |
| `APP_HOST` | Backend bind host | 초안, MLOps 협의 |
| `APP_PORT` | Backend port | 초안, MLOps 협의 |
| `DATABASE_URL` | MySQL 연결 정보 | 필수, 비밀값 포함 가능 |
| `INFERENCE_BASE_URL` | Inference 주소 | 필수 |
| `INFERENCE_DEADLINE_MS` | business deadline | 확정값 500 |
| `HTTP_CONNECT_TIMEOUT` | 연결 수립 제한 | 값 미정 |
| `HTTP_READ_TIMEOUT` | 응답 chunk 대기 제한 | 값 미정, late 정책과 연계 |
| `HTTP_WRITE_TIMEOUT` | multipart 전송 chunk 제한 | 값 미정 |
| `HTTP_POOL_TIMEOUT` | 연결 풀 획득 제한 | 값 미정 |
| `INFERENCE_MAX_FILES` | Inference 요청 최대 이미지 수 | 확정값 12 |
| `INFERENCE_MAX_REQUEST_BYTES` | multipart 전체 이미지 최대 크기 | 확정값 25,165,824 bytes(24MiB) |
| `CULTIVAR_CONFIDENCE_THRESHOLD` | 품종 저신뢰 기준 | 확정값 0.50 |
| `QUALITY_CONFIDENCE_THRESHOLD` | 품질 저신뢰 기준 | 확정값 0.50 |
| `INSPECTION_HISTORY_LIMIT` | 이력 상한 | 확정값 86,400 |
| `INSPECTION_HISTORY_DELETE_BATCH` | 상한 도달 시 삭제량 | 확정값 8,640 |
| `FAILURE_IMAGE_PATH` | 장애 이미지 경로 | 경로·Volume 미정 |
| `FAILURE_IMAGE_LIMIT` | 장애 이미지 상한 | 확정값 100 |
| `SIMULATOR_INTERVAL_MS` | 그룹 전송 간격 | 확정값 500 |
| `SIMULATOR_MAX_IMAGES` | 각도 기준 대표 이미지 선택 상한 | 확정값 12 |
| `SIMULATOR_POSITION_PATH` | 마지막 입력 위치 파일 | 경로·Volume 미정 |

확정값도 코드 상수로 흩어놓지 않고 설정에서 검증하며 검사 이력에는 실제 적용한 두 confidence threshold를 기록한다. bin mapping 저장 위치와 late task 제한값은 미정이므로 변수 이름까지 확정하지 않는다. 실제 `.env`는 커밋하지 않는다.

## 11. 테스트 정책

pytest를 기본 runner로 사용한다. 기존 `unittest.TestCase`는 pytest가 수집하므로 즉시 재작성하지 않는다.

1. Pydantic Schema와 Enum
2. confidence·bin 정책
3. 최대 12장 이미지와 metadata의 `view_index` 순서·개수 대응 및 변경 없는 중계
4. 응답 `inspection_id` 일치와 `used_frame_count` 범위·요청 이미지 수 이하 검증
5. 정상 Inference와 두 threshold 0.50 기준의 저신뢰
6. 500ms timeout, 연결 오류와 잘못된 응답
7. DB 저장과 DB 실패 시 선별 유지
8. Virtual Control 성공·거부·무응답과 대체 명령
9. late result가 bin·정상 통계를 바꾸지 않는지 검증
10. FastAPI 검사 수직 흐름
11. 이력·통계·CSV와 순환 삭제
12. 실제 MySQL Repository integration

기본 도구는 pytest, FastAPI TestClient, AnyIO async test, HTTPX MockTransport, `unittest.mock`과 pytest `monkeypatch`다. Mock은 내부 호출 횟수보다 외부 계약과 결과 상태를 검증한다. SQLite로 MySQL integration test를 대체하지 않으며 test DB 실행·초기화는 MLOps와 협의한다.

## 12. 코드 품질

Ruff는 Backend, Simulator와 관련 테스트에만 적용한다. 데이터·모델 담당자의 기존 Python 코드를 일괄 변경하지 않는다.

- `E`: pycodestyle 계열의 들여쓰기·공백·기본 코드 형식 오류
- `F`: Pyflakes 계열의 미사용 import, 정의되지 않은 이름과 명백한 코드 오류
- `I`: 표준 라이브러리 → 외부 라이브러리 → 프로젝트 모듈 순서의 import 정렬

Formatter는 `ruff format`을 사용한다. 모든 rule, 과도한 complexity rule, 대량 ignore와 별도 Black·isort·flake8은 도입하지 않는다.

public 함수와 주요 메서드에는 type hint를 사용한다. 주요 클래스·핵심 함수에는 짧은 docstring을 두고 timeout·상태 전이·장애 정책에는 무엇을 왜 하는지 설명하는 주석을 둔다. 코드 자체를 반복 설명하는 주석은 작성하지 않는다.

## 13. 기본 개발 명령

가상환경:

```bash
python -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

```bash
source .venv/bin/activate
```

dependency 파일은 아직 없다. 역할별 충돌을 줄이기 위해 `requirements/backend.txt`, `requirements/backend-dev.txt`를 후보로 MLOps와 확정한다.

```bash
python -m pip install -r requirements/backend-dev.txt
```

실제 파일 생성 전에는 위 설치 명령이 동작한다고 가정하지 않는다.

FastAPI 실행 예정 명령:

```bash
uvicorn <backend_app_module>:app --reload
```

권장 구조에서는 `src.api.main`이 module 후보지만 app factory를 구현할 때 확정한다. `--reload`는 로컬에서만 사용한다.

```bash
pytest
ruff check src/api src/simulator tests
ruff format src/api src/simulator tests
alembic revision --autogenerate -m "change description"
alembic upgrade head
```

`src/simulator/`가 생기기 전에는 해당 Ruff 인자를 제외한다. CI에서는 `ruff format --check`를 사용한다. Alembic 설정 위치와 working directory가 정해지면 실제 명령에 반영한다.

## 14. 역할 경계

Backend는 FastAPI, API 계약, Inference Client, timeout·confidence·bin 정책, MySQL·migration·조회·통계·CSV, Virtual Control과 Simulator 애플리케이션 로직을 담당한다. Simulator 애플리케이션 로직에는 각도 기준 대표 이미지 최대 12장 선택이 포함된다.

데이터·모델 담당은 모델 학습·평가, 시연용 12장 묶음 생성·검증, 모델 로딩·전처리·masking과 Inference HTTP API를 담당한다. Inference는 Simulator가 전달한 최대 12장을 입력으로 받고 부족한 입력의 padding을 처리한다. MLOps는 Docker·Compose·Volume·healthcheck·재시작, CI/CD·배포·로그 운영 환경을 담당한다.

Backend는 실행 명령, 환경변수, health endpoint, migration과 Volume 요구사항을 제공한다. Frontend·Simulator·Inference와 공유하는 endpoint·Schema·Enum·Error를 계약 확인 없이 변경하지 않는다.

## 15. 미정 사항

API·DB 계약 단계:

- Simulator→Backend 검사 endpoint와 multipart 세부 wire schema
- 이미지별 metadata 반복 필드의 직렬화 방식과 계약 위반 시 HTTP 상태·오류 코드
- 이미지 파일별 최대 크기
- 상태 Enum·전이, 오류 코드와 세부 OpenAPI Schema
- bin code와 mapping 저장 방식
- MySQL 물리 테이블·컬럼·관계·인덱스

Backend 설계·성능시험 단계:

- late result 최종 구현, 동시 최대 개수와 lifecycle
- HTTP transport timeout 구체값
- i7-4790 CPU 최종 평균·최대·p95와 500ms 충족 여부
- dependency·lock 파일 형식
- Alembic 디렉터리와 설정 위치

Backend 구현 시작 전에는 실제 Inference가 `inspection_id`, 이미지별 metadata와 `used_frame_count`를 지원하는지, 생성 OpenAPI가 이 문서와 일치하는지 확인한다. 또한 기능 통합용 모델은 품질 승인 실패 상태이므로 개선 모델의 버전·체크섬과 운영 승인 여부를 별도로 확인한다.

미정 값을 코드·문서 예시로 임의 확정하지 않는다.
