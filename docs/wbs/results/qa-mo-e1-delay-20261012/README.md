# ALL-04 지연 분석 — E1 검사·제어 DB 기록 및 서비스 로그

2026-10-12 BE 요청에 따른 E1 읽기 전용 수집 완료. 검사 **9/9건**, 관련 제어 시도 **9건** 확보. 기존 정상 100건 증거의 완료 시각과 DB 완료 시각 **9/9 일치**. 기존 QA-SIM-02·13 FAIL 유지.

[BE 자료 요청 댓글](https://github.com/yuudong123/CQC/issues/65#issuecomment-6116341359) · [DM 판정·분석 요청](https://github.com/yuudong123/CQC/issues/65#issuecomment-6115958487)

## 수집 대상과 선정 근거

BE 댓글은 9개 검사 ID를 직접 열거하지 않으므로, 기존 100건 원자료의 지연 구간 전후를 재구성해 **0-based index 5·6·7·8 및 91·92·93·94·95** 선정. BE가 별도로 정리한 ID 목록과 일치한다고 확정하지 않음. 모든 선정 ID·시각·원자료 SHA-256을 [selected-inspections.json](selected-inspections.json)에 보존.

- 09:46:26.685~09:46:36.230 KST의 4건: 4.740초 간격 전후
- 09:49:24.393~09:49:38.498 KST의 5건: 3.931초·5.755초 간격 전후
- DB 조회 시각 **2026-10-12 11:02 KST**, MySQL **8.4.11**
- 공용 E1 `cqc-cicd-mysql-1`에서 `START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY`로 조회 후 `ROLLBACK`
- 운영 서비스 재시작·설정 변경·검사 POST·데이터 삭제·재측정 미실행

## 검사 생성·완료 시각 간격 분해

아래 값은 DB `created_at`·`completed_at`의 차이. `완료 간격 = 생성 시각 간격 + 두 검사 내부 경과시간의 차이`로 대조.

| 완료 구간(KST) | 완료 간격 | created_at 간격 | 이전 검사 created→completed | 다음 검사 created→completed | 경과시간 변화 |
|---|---:|---:|---:|---:|---:|
| 09:46:28.761→33.501 | 4.740초 | 4.683초 | 0.719초 | 0.776초 | +0.057초 |
| 09:49:26.208→30.139 | 3.931초 | 3.196초 | 0.780초 | 1.515초 | +0.735초 |
| 09:49:30.139→35.894 | 5.755초 | 6.501초 | 1.515초 | 0.769초 | −0.746초 |

- 4.740초·5.755초 완료 공백에는 검사 생성 시각 사이 간격 증가가 크게 기여. 이 관찰만으로 Simulator·업로드·Backend·DB 중 원인을 특정하지 않음.
- 모든 선정 검사 `inspection_status=COMPLETED`, `control_status=SUCCEEDED`, `persistence_status=SUCCEEDED` 확인. 물리 DB의 `error_code`는 9건 모두 NULL, 기존 공개 API 원자료에서는 `errorCode=NONE`으로 표시되어 두 표현 구분.
- 제어 시도는 각 검사 1건, 모두 `attempt_no=1`·`ROUTE_TO_BIN`·`SUCCEEDED`, 최대 `response_time_ms=0.188ms` 확인.
- 모델 내부 추론 시간은 151.771ms·482.420ms·165.413ms로 각 지연 구간의 다음 검사에 대응.

[9개 검사 시각 CSV](inspection-timing.csv) · [검사별 시각·제어 기록](timing-by-inspection.json) · [간격 분해 JSON](gap-decomposition.json)

## 서비스 로그

Backend·Simulator·Inference의 Docker timestamp 포함 로그를 아래 범위로 수집. 최초 차단과 지연 전후 정상 검사도 포함하도록 요청 시각보다 범위를 조금 넓혀 수집.

| 로그 묶음 | KST 범위 | UTC 범위 |
|---|---|---|
| initial-snapshot | 09:43:55~09:45:00 | 00:43:55~00:45:00 |
| gap-0946 | 09:46:24~09:46:40 | 00:46:24~00:46:40 |
| gap-0949 | 09:49:22~09:49:42 | 00:49:22~00:49:42 |

[로그 9개](logs/) · [로그 범위·줄 수 목록](log-inventory.json)

Backend access 로그에서 관찰한 **응답 완료 기록**:

| 범위 | 완료 응답 전체 | 웹 경로 미리보기 | 웹 경로 snapshot | 웹 경로 fault-images | CSV 완료 응답 | 4xx/5xx 완료 응답 |
|---|---:|---:|---:|---:|---:|---:|
| 09:43:55~09:45:00 | 36 | 0 | 0 | 0 | 0 | 0 |
| 09:46:24~09:46:40 | 56 | 36 | 4 | 5 | 0 | 0 |
| 09:49:22~09:49:42 | 124 | 84 | 13 | 13 | 0 | 0 |

- 웹 경로 peer `172.20.0.8`은 수집 시 `logistics-web` IP와 일치. 생성 시각·컨테이너 ID는 [네트워크 요약](current-network-summary.json)에 보존. 이를 개별 사용자나 브라우저 세션의 식별로 확대하지 않음.
- 관찰용 `pageSize=200` 이력 GET은 지연 로그 범위에서 각각 3회 관찰.
- 요청량이 함께 관찰되지만 그것이 지연을 일으켰다는 인과관계는 미확정.
- 완료 응답 로그에 CSV가 없다는 사실은 해당 시각에 미완료·중단 요청이 전혀 없었다는 증명이 아님.
- 서비스 access 로그에 검사 ID와 HTTP 요청 시작 시각이 없어, 개별 검사↔로그의 직접 식별 및 업로드·SQL 구간별 시간 계측은 불가. Docker 시각·DB 완료 시각을 바탕으로 BE에서 추가 대조 필요.

[Backend 응답 이벤트](backend-http-events.json) · [경로별 집계](backend-http-summary.json)

## DB 원자료와 시각 해석

- [query.sql](query.sql): 실제 읽기 전용 조회 SQL. 비밀번호·Token 없음.
- [mysql-result.jsonl](mysql-result.jsonl): MySQL JSON 출력 원문.
- [inspections.json](inspections.json): `created_at`, `completed_at`, `updated_at`와 판정·저장 상태.
- [control-attempts.json](control-attempts.json): `requested_at`, `responded_at`, 제어 응답시간·상태.
- [database-info.json](database-info.json): 조회 시각·MySQL 버전·UTC session 시각.
- [deployed-timestamp-source.txt](deployed-timestamp-source.txt): 배포된 Backend 코드의 UTC 변환 및 생성·완료 시각 할당 발췌.
- DB DATETIME(3)는 UTC naive, 파생 KST는 UTC+09:00. UTC 원문도 함께 보존.
- `created_at`은 애플리케이션의 검사 생성 시각이며 네트워크 요청 진입 시각과 동일하지 않음.
- `completed_at`은 최종 저장 값 구성 시 할당되어 commit 완료 시각을 직접 나타내지 않음. 이 값만으로 특정 SQL·DB lock 대기시간을 분리하거나 DB 대기가 없었다고 확정하지 않음.

## 확인 한계와 후속

당시 CPU·메모리·디스크 I/O 시계열은 이번 실행에서 수집하지 않았고 로컬 증거 검색에서도 찾지 못함. 현재 자원 수치를 과거 값으로 대체하지 않음. 순환 삭제·재측정은 이번 자료 수집 범위에 포함하지 않음.

BE에서 생성·완료·제어 기록과 서비스 로그를 대조하여 Backend 수정·추가 계측 필요 여부 판단. 기존 실패 기록과 기준값 유지.

## 재현·무결성

원본 수집 폴더: `outputs/qa-mo-e1-delay-20261012-110224/`. [수집 스크립트](collect_e1_delay_evidence_20261012.py)는 데이터 변경 없이 위 SQL·Docker 로그 조회를 수행.

```powershell
python docs/wbs/results/qa-mo-e1-delay-20261012/collect_e1_delay_evidence_20261012.py --output outputs/qa-mo-e1-delay-<새 회차>
```

[collection.json](collection.json)에 수집 시각·서비스 이미지·행 수·한계 보존. [manifest.sha256](manifest.sha256)에 공유 파일별 SHA-256 보존.
