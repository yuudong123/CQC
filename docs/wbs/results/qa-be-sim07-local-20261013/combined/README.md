# SIM-07 두 장애 동시 ALL 단일 회차 검수

공식 QA 37/44 유지. SIM-07 공식 PASS는 변경하지 않았다.
동시 요청 faults=["CONTROL_REJECTED","INFERENCE_TIMEOUT"], scope="ALL"을 공개 설정 API에 적용했다. 정확한 10초 관찰 창의 모든 5검사에 두 장애 헤더가 존재하고 제어·검사·오류 DB와 공개 이력이 일치한다. 해제 처리 경계 1검사는 별도 기록해 전체 장애 대상은 6건이다.
최종 DB: REINSPECTION_REQUIRED, error_code=INFERENCE_DEADLINE_EXCEEDED, control_status=REJECTED, target_bin_code=TEST_REINSPECTION_BIN, persistence_status=SUCCEEDED. 공개 처리 상태 TIMEOUT, errorCode INFERENCE_TIMEOUT, faults 두 종류, control REJECTED이다.
검사당 제어 요청은 재검사 bin으로 1회 거부, 대체·재시도 없음. 오류 DB에는 검사당 INFERENCE_DEADLINE_EXCEEDED와 CONTROL_REJECTED 각 1행이다. timeout 판정 이후 제어 분기도 적용되는 현재 정책과 일치한다. 주입 timeout은 실제 Inference 호출을 우회한다.
ALL 설정은 관찰 중 유지되며 설정·시작·해제·정지 요청 모두 HTTP200, revision 1→2→3→4→5이다.
정확한 창은 COMBINED-timeseries.json의 window_start_monotonic 기준 [t,t+10.0)이다. 해제 요청은 10.299573503초 뒤 발생했으며 지연을 숨기지 않는다. 창 밖 해제 경계 검사는 review-targets.csv에서 별도 표시했다.
해제 후 faults=[] 요청 3건: 저신뢰 재검사 1건은 제어·저장 성공, 정상 COMPLETED 2건은 제어·저장 성공이다.
원래 result.json의 TEST_INTERRUPTED와 window_unapplied는 동시 검사를 단일 장애와 비교한 보조 스크립트 후처리 오류다. 실제 요청·응답·DB와 별도 review.json으로 재검수했고 원본은 수정하지 않았다. 장애 시험은 1회뿐이다.
계측 준비와 정상 실행 복원의 자동 입력은 시험 구간에서 제외한다. 최종 상세 상태·집계는 review.json 및 review-final-stable.json을 따른다. Simulator만 정상 launcher로 복원했고 Supervisor·MySQL·Inference·Backend는 재시작하지 않았다.
환경은 외부 경로 없는 격리 network·mount namespace의 로컬 WSL 프로세스 환경이다. 전용 DB·position·저장소와 읽기 전용 데이터셋·모델을 사용한다. 실행 소스 f8a2002, 검수 HEAD 5493e8c4288d945efeec8c764e13697cc548ddfb이며 관련 제품 코드가 동일하다.
기존 독립 회차 review-manifest와 이전 AUTO·SIM 증거/DB 파일 fingerprint를 확인했다. 기존 증거 파일과 QA 문서는 변경하지 않았다. 인증정보는 메모리로만 재사용했다.
미검증: 실제 Frontend 상단 '추론 시간 초과 / 명령 거부 · 전체 신규 요청' 경고, 로컬 환경의 E2 대체 인정. 전용 FE 미연결 상태로 공유 FE나 외부 포트를 변경하지 않았다. review-public-history.json과 COMBINED-applied.json은 UI 재검수에 필요한 Backend 응답 자료다.
원자료 manifest.sha256와 추가 검수 review-manifest.sha256를 구분한다. 전체 대상 ID·source_reference·시각·제어·오류 상세는 review-targets.csv 및 COMBINED-joined.json에 있다.
