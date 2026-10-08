# BE 담당 QA 대행 결과 (2026-10-08, #103)

- 요청·수락: [#103 대행 제안](https://github.com/yuudong123/CQC/issues/103#issuecomment-6052305336) → BE 수락(10-08 14:22 KST). 케이스 담당은 BE, 실행자는 조현재(에이전트). **최종 PASS 판단은 BE 검토 뒤.**
- E1: 학원 서버 `192.168.133.106:8000`, 실행 15:27~15:33 KST, 본인 실행 ID `qa-be-10081526`. 실행 중 dev 푸시 없음(그때 dev 최신 커밋 `1e6ff23`).
- 본인 데이터만 사용: 검사 6건(`qa-be-10081526-ins01-FL-13.9`, `-ins01-YS-15.0`, `-ins03`, `-ins04-LQ`, `-ins08`, `-qa-be-10081526-ops11`)을 만들었고, 삭제는 본인 저신뢰 이미지 2장(`b2089a3e…_10`, `_11`)뿐이다. 공용 설정 변경·장애 주입·다른 사람 데이터 변경 없음.
  - 보존 정책 영향: 본인 저신뢰 검사 12장과 손상 사진 1장이 들어가 가장 오래된 저신뢰 12장·시스템 오류 1장이 순환 삭제됐다(10-08 #103에서 허용한 보존 동작).
- 원자료: [e1-results.json](e1-results.json)(케이스별 기대·실제·판정·비고), 실행 스크립트 [qa_be_proxy.py](qa_be_proxy.py).
- 첫 실행(15:27)은 응답 헤더 이름을 대소문자 그대로 비교해 OPS-08·10이 잘못 실패로 잡혔고 OPS-13 저장 중 멈췄다. 스크립트만 고쳐 같은 본인 검사를 재사용해 다시 확인했다(15:32). 새 검사는 만들지 않았다.

## 결과

| 케이스 | 판정 | 확인한 기대값 | 실제 | 남은 범위 |
|---|---|---|---|---|
| QA-OPS-03 | 통과 | B-FL 13.9 행 필드·시각·내림차순·bins | 부사/특/DEMO_BIN_01/PASS, confidence 98.97·cultivar 99.998, brix 13.9 비실측, 모델 v2-cal, 제어·저장 성공, date·time·timestamp 일치, 200건 내림차순, bins에 DEMO_BIN_01 | — |
| QA-OPS-04 | 통과(부분) | INS-01·03·04·08 행 상태 변환 | 정상 PASS/COMPLETED, 저신뢰·당도 누락 REVIEW/재검사함, 오류 FAIL/ERROR/INFERENCE_ERROR·variety null·excluded true·faults 첫 값 일치·예측 필드 null | INS-10·12 행(E2 전용) |
| QA-OPS-05 | 통과(부분) | a~n 필터, total·items 일치 | 모든 필터가 조건 행만 반환하고 본인 행 포함. h INFERENCING 0건, m 2026-01-01 0건, f·j 오류 21건에 본인 ins08 포함 | g·k의 `$RUN-ins12`(E2), l OTHER는 오늘 지정 행 0건이라 필터 형식만 |
| QA-OPS-06 | 통과 | 페이지·행 수·422 | 50+50 중복 0, 100·200, pageSize=20·page=0 → 422 INVALID_QUERY, 마지막+1 빈 목록 | — |
| QA-OPS-08 | 통과 | 4개 엔드포인트 × a~e, f | 모두 422와 지정 code, 본문 code 하나, no-store. statistics?minutes=1 → UNKNOWN_QUERY_FIELD | — |
| QA-OPS-10 | 통과 | CSV 헤더·형식·열·행 수 | text/csv utf-8·attachment cqc-inspections.csv·no-store, BOM·CRLF·전 칸 따옴표, 17열 순서 일치, 9,834행 ≈ total 9,836(요청 사이 Simulator 입력), brix 모두 false, 오류 행 error_codes, 이미지 열 없음 | Excel 미설치 → UTF-8 BOM·한글 디코딩으로 대신 확인 |
| QA-OPS-11 | 통과 | 하이픈 시작 ID의 CSV 첫 칸 | `"'-qa-be-10081526-ops11"` (작은따옴표로 수식 무력화) | Excel 직접 열기 미실행(미설치) |
| QA-OPS-13 | 통과 | 통계 CSV 두 형식·구간 행 수·422 | 기간 형식 헤더·total 그룹 비율=reinspection/total, 오늘 형식 섹션, 1·5·10·30분 = 60·300·600·1,800행, minutes=2 → 422, mode BACKEND | — |
| QA-IMG-01 | 통과 | 저신뢰만 사진 12장 저장 | 본인 저신뢰 12장(LOW_CONFIDENCE·errorCode null·LOW_QUALITY_CONFIDENCE), 정상·당도 누락 0장 | 200장 한도라 검사 ID 기준으로 판정 |
| QA-IMG-02 | 통과(부분) | 목록 형식·정렬·필터·ins08 항목 | 300장, 최신순, 키 12개, id·previewUrl 형식, category·inspectionId 필터, 본인 ins08 imageIndex 0·INFERENCE_HTTP_ERROR | 시간 초과 항목 표시(E2) |
| QA-IMG-03 | 통과 | 미리보기·잘못된 id | 200 image/png no-store, 보낸 손상 사진과 SHA-256 같음. `0000`·없는 id 410 IMAGE_EXPIRED, `..%2F..%2Fetc` 404 | — |
| QA-IMG-04 | 통과 | 선택 삭제 | 200 deletedIds 2개(중복·없는 id 무시), 본인 12→10장, 미리보기 410, 이력·CSV 유지 | 보존 수 300은 Simulator가 곧바로 다시 채워 본인 검사 기준으로 판정 |
| QA-IMG-05 | 통과 | 삭제 입력 검증 | `[]` → 200 빈 목록, `../x`·301개·추가 필드·본문 없음 → 422 INVALID_IDS, 본인 이미지 12장 그대로 | — |
| QA-INS-09 | 통과 | 지정 자동 시험 | `tests/api/test_inspection_service.py::test_service_rejects_mismatched_inference_response` 2 passed(노트북, Python 3.11, 저장소 `1e6ff23`) | — |
| QA-AUTO-01 | 통과(KI-8) | `pytest tests data/sampling/tests` | 노트북 Windows: 563 통과·91 건너뜀·2 실패. 실패 2개는 모두 `WinError 5` 폴더 이름 변경(KI-8): `test_review_images.py::test_independent_100_200_retention_and_bulk_api`, `test_simulator_faults.py::test_fault_injection_is_request_local_and_retains_only_inference_images[INFERENCE_ERROR…]`. 두 시험은 Linux [PR #119 python 검사](https://github.com/yuudong123/CQC/actions/runs/37730404036/job/113157984172)에서 통과. 건너뜀 91개는 모두 `CQC_TEST_DATABASE_URL`·`CQC_BE10_*_DATABASE_URL` 미지정 | — |
| QA-AUTO-02 | 미실행 | 실제 MySQL 통합 시험 건너뜀 없이 통과 | 노트북에 Docker·MySQL이 없어 실행하지 못함 | **BE·MO E2 MySQL로 반환** |

## 보완 (2026-10-08 16:27~16:36, #103 BE 검수 요청)

BE 검수 댓글의 누락 증거·원문 조건만 다시 확인했다. 원자료는 [supplement/](supplement/)에 있다([supplement.json](supplement/supplement.json)).

**실행 시각 바로잡기**: 위 E1 15:27~15:33, #103 댓글의 15:27~15:50은 잘못 적은 범위다. 실제는 E1 첫 실행 15:26(실행 ID `qa-be-10081526`, 스크립트 오류로 중단) → 재실행 15:27:27~15:28:07(`e1-results.json`), 로컬 시험 15:28~15:33이다.

| 요청 | 보완 결과 | 파일 |
|---|---|---|
| OPS-06 같은 total | 1쪽 응답의 `snapshotAt`으로 2쪽·마지막+1쪽 고정 → total 78,277 세 번 같음, 중복 0, 빈 목록 | supplement.json |
| OPS-08 f no-store | `/statistics?minutes=1` → 422 UNKNOWN_QUERY_FIELD, `Cache-Control: no-store` | supplement.json |
| OPS-10 행 수 정확 일치·원본 | 같은 `snapshotAt`으로 history total 11,449 = CSV 11,449행. 원본 CSV·응답 헤더 첨부. Excel 직접 열기는 미실행(Excel 없음) | ops10-inspections.csv, ops10-headers.json |
| OPS-13 suspicions 섹션 | 오판 의심 0건이면 `suspicions` 행이 없고, 본인 행을 OTHER로 지정하면 생긴다(지정 → CSV → NONE 복구). 빈 집계 표현을 원문 기준으로 어떻게 볼지 BE 판단 필요 | ops13-statistics-today-with-other.csv, -after-restore.csv |
| OPS-05 g·k·l | g·k: E1 시간 초과 행으로 필터 정합 확인, 본인 실행 ID의 시간 초과 행 포함. l: 본인 행 OTHER 지정 → OTHER 필터 포함·NONE 필터 제외 → NONE 복구 | supplement.json |
| IMG-01 정상 12건 | 원문대로 정상 12건(선별함 01~12) 전송 → 각 검사 ID 저장 사진 0장(`qa-be-10081636t-*`). 16:27 1차 회차는 16:24 dev 푸시의 Jenkins 빌드와 겹쳐 1건이 시간 초과라 판정 제외 | supplement.json |
| IMG-02 전체 필드 | 300개 항목 키·타입·범위 모두 정상. `INFERENCE_TIMEOUT` 항목도 E1 목록에서 확인. 참고: `createdAt`·`snapshotAt`이 정수값인데 `…361.0`처럼 소수 표기로 온다 | img02-fault-images.json |
| IMG-04 삭제 전후 ID | 본인 이미지 2장 삭제 전후 전체 ID 집합 차이 = 그 2개뿐(사이 신규 0) | img04-ids-before.json, img04-ids-after.json |
| AUTO-01 원문 로그 | Windows 전체 범위 562 통과·91 건너뜀·3 실패(WinError 5), Windows CI 범위 463·91·5(WinError 5 2 + 시간 민감 3). 실패 시험이 회차마다 달라 Windows로는 확정 불가 → **부분 유지**, Linux 전체 범위는 BE·MO 환경 필요 | auto01-windows-*.log, *.xml |
| E1 배포 SHA 연결 | Backend가 빌드·커밋 정보를 내보내지 않아 DM·FE 쪽에서는 연결 불가. 대행 당시 코드에 영향 있는 마지막 병합은 PR #118(`e960d1f`). 배포 기준선 확인은 MO 도구 필요 | — |

- 우연 증거: 16:27 회차에서 생긴 본인 시간 초과 행 `qa-be-10081626s-ins01-FS-15.0`이 OPS-04 시간 초과 행(FAIL/TIMEOUT/INFERENCE_TIMEOUT/예측 null/재검사함)과 IMG-02 `INFERENCE_TIMEOUT` 이미지 12장을 E1에서 직접 보여준다.
- 본인 데이터만 사용: 보완 회차 검사 25건(정상 12건 × 2회, 저신뢰 1건. 1차 정상 12건 중 1건은 시간 초과), 오판 의심 지정은 본인 행 1건을 OTHER → NONE으로 복구, 삭제는 본인 이미지 2장.
