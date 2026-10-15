# SIM-07 로컬 ALL 증거 선별 보존 및 최종 검수

공식 Backend 37/44 PASS 유지. SIM-07은 로컬 Backend 동시 ALL 기능 충족이나 FE 실제 경고·E2 환경 대체 인정 대기로 공식 PASS 보류다.
실행 소스 f8a2002, 검수 HEAD 5493e8c4288d945efeec8c764e13697cc548ddfb이며 관련 Backend·Simulator 코드는 동일하다. 모델 SHA b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a. 환경은 D CQC-AUTO01 WSL 프로세스 전용 환경이며 E2 Docker가 아니다. 독립 network·mount namespace, 외부 경로 없음, 전용 cqc_sim_qa·position·저장소와 데이터셋·모델 읽기 전용 근거를 보존한다.

## 서로 다른 회차

- independent/: CONTROL_REJECTED 1회(대상5·제어9·오류5), INFERENCE_TIMEOUT 1회(10초 창5+해제 경계1·제어6·오류6). 전 건 저장·HTTP200, 해제 후 정상 처리. 제어 거부4건 대체 성공, 저신뢰1건 재검사 bin 거부1회.
- combined/: faults=[CONTROL_REJECTED,INFERENCE_TIMEOUT], scope=ALL 단일 회차. 정확한 10초 창5건 모두 두 장애 헤더 확인, 해제 경계1건 별도 관리로 전체 대상6건. 공개 TIMEOUT·INFERENCE_TIMEOUT, DB REINSPECTION_REQUIRED·INFERENCE_DEADLINE_EXCEEDED, 제어 REJECTED·재검사 bin1회. 오류 DB timeout6·제어거부6, 저장6건 성공. 후속 무장애3건 저장(정상2·저신뢰1).
- 해제 요청은 관찰 시작 뒤 각각10.223초·10.278초·동시10.300초다. 정확한 [t,t+10.0) 관찰 창과 API 적용·해제 경계를 구분한다. 검사 ID·source_reference·요청 시각·결과는 joined.json과 CSV에 있다.
- 동시 회차 result.json의 TEST_INTERRUPTED·window_unapplied는 후처리에 남은 단일 장애 비교 조건 오류다. 원본 중단 기록을 보존하고 combined/review.json의 원자료 재검수 결과를 최종 근거로 사용한다. 실제 시험을 반복하지 않았다.
- 동시 회차 최종 정상 launcher 복원 뒤 stopped/revision1/concurrency1/2000ms/faults[]/jobs0/position1025, 누적 검사1025·제어시도1029·오류23이었다. 기동 자동 입력은 시험 구간에서 제외했다. 이 값은 당시 종료 증거이며 이번에는 서비스·API·DB에 접속하지 않았다.
- 주입 timeout은 실제 Inference 호출을 우회한다. 실제 transport timeout 또는 모델 추론 성공 증거로 확대하지 않는다.
- 실제 웹 경고 “추론 시간 초과 / 명령 거부 · 전체 신규 요청”은 미검증이다. 선택 snapshot·공개 이력은 FE 재검수용 Backend 응답이며 화면 캡처가 아니다.

## 원본과 선택 보존

원본 D:/CQC-SIM-QA/evidence/sim07-20261013/run1/ 및 combined/는 그대로 보존한다. source-manifest는 복사하지 않은 파일도 포함한 원본 전체 목록으로, Git 보존본을 검증하는 루트 manifest와 다르다.
원본 전체94파일을 일괄 복사하지 않고 핵심 요청·응답, 검사별 DB/제어/오류 연결, 관찰 시계열, 종료 상태와 Backend 오류 로그를 선별했다. 반복 누적 history·전체 DB·자원 로그·계측 스크립트·대용량 이미지는 제외했다. provenance.json에서 원본 해시와 복사/가공본 해시를 구분한다.
review-checks.json은 D 원본과 기존 SIM-11·12 보존본의 해시·원본 출처·재계산 결과를 기록한다. 인증정보·인증 헤더·개인 연락처를 검사했다. 이번 작업에서 신규 시험·제품/공식 테스트 수정·서비스/DB 조작을 하지 않았다.
자료는 로컬 미커밋 상태로 GitHub 공개 링크가 없다. Commit·Push 후 증거와 통합 검수 문서 링크를 #103에 연결해야 한다.