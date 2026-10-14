**[MO] 결과 — SIM-06·09 원자료 조사 및 E1 제어 증거 보완 (10-14)**

## 한 일

- BE 요청에 따라 기존 Git·로컬 원자료의 보존 위치와 부족 조건 조사
- 추가 조사 10회 및 기존 E1 DB 읽기 전용 대조
- 원본 TSV·SQL·검사/제어/오류 행·출처·체크섬 보존
- 커밋·푸시 완료: feat/mlops

## 결과 (수치)

- **신규 실제 제어 원자료 13행 확보**
  - 무응답 검사 11건: 검사·제어·오류 각 11행, 명령 ID·bin·요청/응답 시각 확인
  - 검사별 저장 제어 행 1개, attempt_no=1·NO_RESPONSE
  - 기존 E1 추론 오류·시간 초과 검사 2건: 재검사 bin 제어 각 1행·SUCCEEDED
- 무응답 11건의 ID·bin·모델·UTC→KST 완료 시각이 기존 Git CSV와 **11/11 일치**, 각 12프레임·저장 성공
- 기존 BE SIM-07 Git 자료에서 제어 거부 9행·추론 시간 초과 6행의 위치 확인
- 조회 전후 E1 7개 서비스의 ID·이미지·StartedAt·RestartCount·health 동일, 모두 healthy
- 원자료 묶음 85개 파일·SHA-256 목록 84항목 보존

## 다른 파트 영향

- **BE:** 신규 E1 무응답·추론 제어 상세 및 기존 WSL 자료 검수 요청
- **BE·DM:** E1/WSL 자료의 SIM-06 Docker NEXT 대체 인정 범위 확인 요청
- 서로 다른 회차를 하나의 시험으로 합치지 않았으며, 신규 검사·장애 주입·서비스 변경은 하지 않음

## 남은 일

- [ ] E1/WSL 제어·이미지 증거의 대체 인정 범위 확정
- [ ] SIM-06: 실제 FAILED 명령 상세, 성공 bin 통계 전후 제외, DB_ERROR 대상 ID·저장 실패 로그 연결 보완
- [ ] SIM-09: 동일 회차의 중단 20초·복구 후 30초 자동 저장 증가·검사 ID·무재시작·공개 상태 원자료 확보
- [ ] 인정 후에도 부족한 필수 조건만 확정하고, 필요한 경우 최소 추가 격리 시험 협의

이번 자료는 별도 E1 회차의 보존 행이며 원래 10/06 E2 행의 복원이나 전체 NEXT 절차 통과가 아닙니다.
SIM-09 기존 복구 성공은 직접 probe이며 자동 저장 재개와 구분합니다. 동일 컨테이너 ID만으로 과거 무재시작을 확정하지 않습니다.
**BE 공식 37/44·INS-13 FAIL/수정 보류·#65 FAIL을 유지합니다.**

## 관련 PR / 문서

- [전체 조사 보고서](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim06-sim09-inventory-20261014/README.md)
- [추가 조사 10회 및 신규 원자료](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim06-sim09-inventory-20261014/ten-pass/README.md)
- [무응답 검사·제어·오류 11건](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim06-sim09-inventory-20261014/ten-pass/10-e1-exact-ids-records.json)
- [추론 오류·시간 초과 제어 2건](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim06-sim09-inventory-20261014/ten-pass/10-e1-failed-inference-records.json)
- [조건별 미완료 대조](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim06-sim09-inventory-20261014/second-pass/remaining-conditions.json)
