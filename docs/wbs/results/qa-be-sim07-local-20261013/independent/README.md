# SIM-07 로컬 ALL 장애별 독립 회차 검증

공식 QA 37/44 유지. 공식 SIM-07 PASS를 변경하지 않는다.
QA 원문은 CONTROL_REJECTED와 INFERENCE_TIMEOUT의 동시 ALL 조합이다. 사용자 지시에 따라 이번에는 장애별 독립 회차만 수행했다. 동시 조합과 웹 경고, E2 대체 인정은 미검증이다.

실행 소스 f8a2002, 검수 HEAD 5493e8c4288d945efeec8c764e13697cc548ddfb이며 관련 Backend·Simulator 제품 코드가 동일하다. 모델 SHA b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a.
독립 network·mount namespace, 외부 IPv4/IPv6 경로 없음, loopback 전용 서비스, 전용 cqc_sim_qa DB·position·이미지 저장소, 데이터셋·모델 읽기 전용 mount를 확인했다. 전용 Frontend 리스너는 없으며 포트를 열지 않았다.

## 회차 결과

|장애|정확한 10초 창 대상|전체 장애 대상|검사/제어 시도/오류 DB|결과|
|---|---:|---:|---|---|
|CONTROL_REJECTED|5|5|5/9/5|4건 정상 bin 거부 뒤 재검사 bin 대체 성공, 1건 저신뢰 재검사 bin 거부 1회|
|INFERENCE_TIMEOUT|5|6|6/6/6|전 건 재검사·공개 TIMEOUT, 제어 및 저장 성공; 해제 경계 1건 별도|

측정 창은 시작 HTTP 응답 및 실제 state 확인 직후 monotonic 기준 [t,t+10.0)이다. 해제 요청 전 관찰 종료는 각각 10.223076689초·10.277624506초로, 상태 조회 소요 때문에 10초에서 소폭 초과했다. 실제 요청 전문에 따른 HTTP 시작부터 해제 응답까지의 전체 설정 유지 시간은 이 관찰 창과 구분한다. target-inspections.csv와 review.json에 10초 창·전체 장애 대상·해제 경계를 구분했다.
CONTROL_REJECTED 해제 HTTP 응답 경계에서 정상 26a92337-bce4-4cac-8144-f5d5f48bfdab가 시작했다. 헤더 faults=[]와 DB 정상 저장으로 확인했다.
INFERENCE_TIMEOUT 해제 요청 처리 경계의 38e572dd-8df9-444d-afd5-a64865e42936은 기존 장애 헤더를 받았다. 해제 응답 후 정상 0f11eb33-5bcb-4091-a729-67ee126b2936 및 d22774e0-c090-498b-908d-82f35b2d7fac가 저장됐다.

Timeout 주입은 실제 Inference 호출을 우회한다. 실제 Inference transport timeout 증거가 아니며 used_frame_count·model_version null을 모델 추론 성공으로 해석하지 않는다. Backend 오류 로그의 검사 ID별 images_saved=12를 통해 장애 이미지 저장을 확인했다. 대용량 이미지 사본은 증거에 포함하지 않았다.
제어 거부 회차에서는 실제 Inference 응답과 model_version·used_frame_count=12가 존재한다. DB control_status=SUCCEEDED인 대체 성공은 공개 이력 control=FALLBACK과 구분했다. 저신뢰 1건의 DB 주 오류는 LOW_QUALITY_CONFIDENCE지만 inspection_errors에는 CONTROL_REJECTED가 별도로 저장되어 장애 누락이 아니다.

## 최종 상태와 보존

기준선 998/998/0 → 최종 1014/1018/11. 신규 16검사 = 장애 11 + 해제 이후 정상 3 + 계측 준비/정상 실행 복원 자동 입력 2. 이번 장애 회차와 자동 입력을 섞지 않는다.
공개 설정 요청 8개 모두 HTTP 200, 계측 회차 revision 1→2→3→4→5→6→7→8→9. 정상 Simulator launcher 복원 재시작 후 revision은 0에서 정지 요청으로 1이 됐다. 과거 revision을 강제로 되돌리지 않았다.
최종 running=false/status=stopped/revision1/concurrency1/intervalMs2000/faults[]/jobs0/position1014, Backend snapshot 일치, MySQL·Inference·Backend 정상. 최종 3초 관찰 및 별도 읽기 검증에서 검사 수와 position 불변. Simulator health503은 정지 상태의 정상 계약이다.

상위 폴더의 첫 중단 기록은 snapshot 필드 참조 오류이며 장애 적용·Simulator 교체 이전에 발생했다. 보존한 뒤 보조 스크립트만 고쳤다. 장애 시험은 각 1회이며 반복하지 않았다.
기존 AUTO-01·02 증거와 AUTO-02 DB 파일 크기/mtime, SIM-03·11·12 및 이전 SIM-12 보완 증거의 전후 fingerprint가 일치했다. 기존 환경은 조작하지 않았다.
인증정보를 메모리로만 재사용하고 증거 파일에서 실제 토큰·DB 비밀번호 부재를 확인했다. 전체 요청·응답 원자료 manifest와 검수 후 추가 자료 review-manifest를 구분한다.

남은 공식 조건: 원문의 두 장애 동시 적용, 웹 상단 '추론 시간 초과 / 명령 거부 · 전체 신규 요청' 실제 표시, 로컬 WSL 환경의 E2 대체 인정. FE 검증은 격리 서비스에 연결된 전용 FE가 준비된 뒤 별도 수행하며 공유 FE나 외부 포트를 임의로 변경하지 않는다.
