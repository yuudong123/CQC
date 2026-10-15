# QA-AUTO-01 Linux 전체 시험 — 2026-10-12

판정: **PASS**. 기존 실행 결과를 원문과 최종 대조한 기록이며, 이 자료 정리 단계에서는 시험을 재실행하지 않았다.

- 실행 환경: WSL2 `CQC-AUTO01`, Debian 13, Python 3.13.5, pytest 9.1.1
- 소스 SHA: `6f32cddd24fa19d577e2d53d1d2a2f7a35f4f0cc`
- 실행 경로: `/opt/cqc-auto01/source`, 가상환경 `/opt/cqc-auto01/venv`
- 실제 저장소: `D:\CQC-AUTO01\wsl\ext4.vhdx`의 Linux ext4
- 명령: `python -m pytest tests data/sampling/tests -q -rs -p no:cacheprovider`
- 전체 항목 662건(최종 passed+skipped 합계), 571 passed, 91 skipped, 실패·수집 오류 0건
- subtest 20건 통과(662건에 별도 합산하지 않음), 경고 1건, 73.38초, 종료 코드 0
- 제외·재시험·제품 또는 테스트 코드 수정 없이 전체 공식 범위 실행
- 별도 네트워크 namespace에서 loopback만 활성화, `env -i`로 시험 환경을 구성하여 외부 DB·서비스 설정 미전달
- `.env` 없음, CPU PyTorch 사용, 시험 전후 소스 664개 파일의 HEAD 아카이브 일치 확인

## Skip 최종 판정

| 사유 | 건수 | 원문 허용 여부 |
|---|---:|---|
| CQC_BE10_DATABASE_URL 미설정 | 70 | 실제 격리 MySQL 통합 시험, 허용 |
| CQC_BE10_3_DATABASE_URL 미설정 | 12 | 실제 격리 MySQL·운영 통합 시험, 허용 |
| CQC_TEST_DATABASE_URL 미설정 | 7 | MySQL 중복 2건·일반 통합 5건, 허용 |
| CQC_RETENTION_TEST_DATABASE_URL 미설정 | 1 | 실제 MySQL 순환 삭제 통합 시험, 허용 |
| 완료된 격리 BE-10 증거 실행 설정 미완료 | 1 | 실제 MySQL URL을 포함한 필수 환경 미설정, 아래 근거로 허용 |

마지막 1건은 `tests/api/test_be10_evidence_audit.py:25~29`의 `test_completed_run_api_db_control_statistics_and_csv_agree`다. `CQC_BE10_DATABASE_URL`, `CQC_BE10_AUDIT_RUN`, `CQC_BE10_EVIDENCE`를 읽고 `if not all((url, run, evidence))`이면 skip한다. 그 이후 증거 회차를 읽고 해당 URL로 SQLAlchemy engine·Session을 생성해 실제 검사·제어 DB 행과 API·CSV·통계를 대조한다. 이번 실행기는 `env -i`를 사용하고 위 세 변수를 전달하지 않았다. 따라서 실제 MySQL URL 미설정 자체가 skip 조건을 충족하며, 단순히 로컬 증거 파일이 없다는 이유를 새 허용 조건으로 추가한 판정이 아니다.

91건 모두 원문의 MySQL·외부 서비스 필수 환경변수 미설정에 따른 조건부 skip에 해당한다. 이 결과는 AUTO-02의 실제 MySQL 시험 통과를 뜻하지 않는다.

## 경고 및 증거

경고 1건은 Starlette TestClient의 httpx 사용 관련 폐기 예정 안내다. 실패·수집 오류가 아니며 이번 작업에서 httpx2 설치나 의존성 변경은 하지 않았다.

- [전체 원본 로그](auto01-pytest.log): SHA-256 `398e8088d393a8a385b642f082567982ef0a445fae77da65fb92ee436d43a139`
- [결과 요약](auto01-summary.json): 건수·실행시간·skip 사유·소스 불변 확인
- [환경 확인](environment-verification.json): Python·주요 패키지 버전·설치 경로·DB 변수 미설정·시험 디렉터리·CPU 사용 확인

세 파일은 기존 `D:\CQC-AUTO01\evidence\`의 동일 이름 파일을 바이트 그대로 복사했다. 인증정보나 운영 연결 문자열은 없으며 `.gitattributes`로 로그·JSON의 바이트를 보존한다. 원본 D드라이브 환경과 로그는 변경하지 않았다. 현재 저장소 파일은 로컬 미커밋 상태이며 Commit·Push 후에야 다른 팀원이 저장소에서 열람할 수 있다.

기존 Windows WinError 5 및 Linux 일부 CI 결과는 과거 이력으로 유지한다. 이번 전체 Linux 실행으로 AUTO-01의 잔여 조건을 충족했다. 공식 Backend QA는 **32/44 → 33/44 PASS, 잔여 11개**이며 다른 QA 판정은 변경하지 않는다.

공식 결과 공유: [#103 AUTO-01 최종 PASS 댓글](https://github.com/yuudong123/CQC/issues/103#issuecomment-6118190464).
