# QA-AUTO-02 격리 MySQL 통합 시험 — 2026-10-12

최종 판정: **PASS**. 이미 완료한 공식 시험 1회의 로그와 DB 전후 상태를 QA 원문과 최종 대조한 기록이다. 이 문서 정리 단계에서 pytest 수집·재실행이나 DB 초기화를 하지 않았다.

## 실행 환경 및 결과

- 소스 SHA: `0094807a159e4bedadd2700fd689b3c848ee803f`
- WSL2 `CQC-AUTO01`, Debian 13, Python 3.13.5
- 소스 `/opt/cqc-auto02/source-0094807`, venv `/opt/cqc-auto02/venv`
- Oracle MySQL Community Server **8.4.11**, 격리 주소 `127.0.0.1:13324`
- 전용 바이너리 `/opt/cqc-auto02/mysql/usr/sbin/mysqld`, 데이터 `/opt/cqc-auto02/mysql-data`
- MySQL과 시험은 같은 독립 network namespace, 외부 경로 없음, 시험 사용자 UID 1000
- 공식 명령: `python -m pytest tests/api -k mysql -q -rs -p no:cacheprovider`
- 전체 수집 항목 **510건**은 최종 선택 13＋deselected 497의 합계다. 별도 수집 명령을 실행한 결과가 아니다.
- **13 passed / 0 failed / 0 errors / 0 skipped**, **497 deselected**, 경고 1건, **12.62초**, **종료 코드 0**

497건은 `-k mysql`의 범위 밖이어서 선택되지 않은 시험이며 skip이 아니다. 실제 MySQL 시험을 skip 없이 통과해야 한다는 QA 원문의 합격 조건을 충족한다. 이번 대상은 새 D 기반 독립 인스턴스이며 기존 E1·공유 E2 DB를 사용한 결과로 기록하지 않는다.

## 선택 ID 목록과 전체 PASS의 구분

`auto02-after-test.json`의 `selected_tests`는 코드 AST로 정적으로 확인한 명령 대응 목록이다. 일반 MySQL 통합 7건(중복 요청 2건 포함), 순환 삭제 1건, BE-10 운영 통합 2건, 연결 설정 단위시험 3건의 합계 13건과 실제 로그의 선택 13건을 대조했다.

`-q` 로그에는 개별 node ID별 실행 결과가 출력되지 않았다. 이 묶음은 개별 실행 상태나 JUnit 결과를 생성하지 않으며 **정적 ID 목록**과 **실제 로그의 전체 13 PASS**를 구분한다. `individual_status_basis`도 이 한계를 명시한다.

## DB 전후 상태

| 전용 DB | 시험 전 검사/제어/오류 | 시험 후 검사/제어/오류 | migration / 활성 mapping |
|---|---|---|---|
| cqc_test | 0/0/0 | 0/0/0 | 20260929_02 / 정상 12＋재검사 1 |
| cqc_auto02_retention | 0/0/0 | 0/0/0 | 동일 |
| be10_3 | 0/0/0 | 5/5/1 | 동일 |

`be10_3`의 잔여 오류 검사 ID는 `03bcfbdb-d52a-4f2a-ba8c-29dccdad968d`이며 원시 코드 `INFERENCE_HTTP_ERROR`, 제어·저장 모두 SUCCEEDED다. `tests/api/test_be10_operations_integration.py`의 Simulator 위치 복구 시험은 첫 회차 재개 시 `faults=[INFERENCE_ERROR]`, `scope=NEXT`를 지정한다. Backend `src/api/services/inspections.py`는 해당 주입을 INFERENCE_HTTP_ERROR로 처리한다. 사후 오류 1건은 이 의도된 시험 조건과 일치하며 pytest 실패를 의미하지 않는다.

일반·순환 삭제 시험의 자체 정리 및 BE-10 fixture의 전용 DB 전체 검사 삭제는 기존 코드의 동작이다. 조회한 사후 상태는 예상 범위와 일치한다. 시험 종료 후 추가 DB 초기화·삭제를 수행하지 않고 잔여 기록을 보존했다.

## 경고 및 별도 운영 주의사항

경고 1건은 Starlette TestClient의 httpx 사용 관련 폐기 예정 안내다. 현재 MySQL 기동 이후 ERROR 없음, Simulator 로그 ERROR 없음·프로세스 종료 완료를 `auto02-log-review.json`에서 확인한다. 설치 단계의 과거 초기화 오류와 이번 시험 로그를 혼동하지 않는다.

시험 시작 C 여유 **5.319GiB → 증거 보존 시 4.311GiB**로 약 1GiB 감소했다. **원인은 미확정**이며 시험 PASS와 별개인 환경 운영상 주의사항이다. D 여유는 약 448.405GiB로 거의 같았다. 원인을 WSL·Docker·페이지 파일 문제로 단정하지 않으며 추가 시험·다운로드·설치·기존 데이터 삭제·압축·이동을 하지 않았다.

## 증거 및 출처

- [auto02-pytest.log](auto02-pytest.log): 원본 pytest 출력
- [summary.json](summary.json): 실행 1회, 종료 코드·건수·공간 변화
- [auto02-before-test.json](auto02-before-test.json): 실행 직전 실제 서버·namespace·DB·seed·빈 데이터·소스 검증
- [auto02-after-test.json](auto02-after-test.json): 사후 DB 기록·서버 대상, 전체 결과, 정적 ID 목록
- [auto02-log-review.json](auto02-log-review.json): 서버·Python 로그 검토 및 소스 불변
- [manifest.sha256](manifest.sha256): 위 원본 복사 파일 5개의 해시

다섯 파일은 `D:\CQC-AUTO02\evidence\run-20261012-1\`의 동일 이름 파일을 바이트 그대로 복사하고 SHA-256 일치를 확인했다. 로그 해시는 `b6cd139c8a0fd09c872733465a0ee5588adc66448a81f5170e663cd8f1489a9b`다. README와 해시 목록만 이번에 작성한 설명 자료이며, 기존 요약·사후 JSON은 당시 분석 자료의 원본 복사다. JSON의 `qa_documents_updated=false`, `github_updated=false`는 시험 증거 보존 당시 상태로서 이번 공식 기록 갱신 이전 값이다.

파일은 비밀번호·인증 토큰·운영 URL·개인 식별 정보 없이 기술 경로·시험용 무작위 ID·결과만 포함한다. 원본 생성 시 DB 비밀번호 미포함 확인과 이번 내용 검토를 수행했다. D 원본·전용 환경·잔여 DB 기록은 보존했다. `.gitattributes`로 로그·JSON의 바이트를 보존한다. 저장소 자료는 로컬 미커밋 상태이므로 Commit·Push 전에는 GitHub에서 열람할 수 없다.

공식 Backend QA는 **33/44 → 34/44 PASS, 잔여 10개**다. INS-13 승인 보류, OPS-13 실환경 검증 대기, Simulator 잔여 항목 및 #65 공식 성능 FAIL 등 다른 판정은 유지한다.

공식 결과 공유: [#103 AUTO-02 최종 PASS 댓글](https://github.com/yuudong123/CQC/issues/103#issuecomment-6118956883).
