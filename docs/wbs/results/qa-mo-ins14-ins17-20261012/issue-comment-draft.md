**[MO] 결과 — QA-INS-14·17 기존 DB 증거 보완 (2026-10-12)**

## 한 일

- [BE 잔여 DB 증거 요청](https://github.com/yuudong123/CQC/issues/103#issuecomment-6117222988)의 지정 ID·확인 항목 대조
- E1 `cqc-cicd-mysql-1` / `cqc` DB의 기존 검사·오류·제어 기록 읽기 전용 조회
- 기존 E2 JSONL·공유 CSV·로컬 보존 자료 확인 및 전달 묶음 작성
- INS-14 원래 E2 회차와 별도 E1 대안 회차 구분 보존

## 결과 (수치)

### INS-17

- 조회 기준: **2026-10-12 12:35:52.411 KST**
- 지정 검사 `qa-e1-20261008-091125-45628a-ins08`의 검사 **1행**, `inspection_errors` **1행** 보존 확인
- 오류 행: `id=979`, `component=inference`, 원시 `error_code=INFERENCE_HTTP_ERROR` 확인
- 오류 발생: **2026-10-08 09:11:29.856 KST**, 검사 완료: **09:11:29.860 KST** 확인
- 기존 공유 CSV 헤더 포함 **11095행**의 동일 ID·완료 시각·공개 `error_codes=INFERENCE_ERROR` 대조
- 현재 배포 Backend의 `INFERENCE_HTTP_ERROR → INFERENCE_ERROR` 공개 계약 변환 규칙 확인, DB 원시 코드 원문 보존

### INS-14 원래 E2 회차

- `be10-2-63f2ca4e` 지정 12건의 기존 API·검사 DB 기록 및 정상 bin **12/12 일치** 재확인
- 확인한 로컬 보존 자료에서 해당 12건의 개별 `control_attempts`·응답시간 추가 확보 미완료
- 이 환경에서 E2 MySQL 컨테이너 확인 불가, 원래 E2 DB의 보존·삭제 여부 **미확정**
- E1 DB에서 해당 E2 ID의 검사·제어 조회 각 0행 확인, E2 원본 소실 판정 근거로 사용하지 않음

### INS-14 E1 대안 회차 — 재사용 검토용

- BE가 대안으로 언급한 `qa-be-10081636t-ins01-*` 기존 검사 **12행**, 제어 **12행** 보존 확인
- 검사별 제어 정확히 **1행**, 전 건 `attempt_no=1`·`ROUTE_TO_BIN`·`SUCCEEDED` 확인
- `DEMO_BIN_01`~`DEMO_BIN_12` **12개 bin** 확인
- `requested_bin_code`와 **검사 DB**의 `target_bin_code` **12/12 일치** 확인
- `response_time_ms` 전체 최대 **0.090ms**, 기준 **100ms 미만** 대조 완료
- 원래 E2 회차와 다른 증거로 분리, 기존 E1 API 응답 대조·재사용 범위는 BE 검토 필요

## 다른 파트 영향

- BE: INS-17 실DB 오류 행과 기존 API·이력·CSV·이미지 증거 최종 대조 가능
- BE: INS-14 기존 E1 대안 12건의 제어 상세·응답시간 검토 가능
- DM: INS-14·17 PASS 여부 및 Backend **30/44 PASS** 집계 변경은 BE 최종 판정 후 반영 필요

## 남은 일

- [ ] BE 보유 INS-17 API·이력·이미지 원자료와 실DB 행 최종 대조
- [ ] 원래 E2 DB·다른 환경의 기존 export 보존 여부 추가 확인
- [ ] 기존 E1 12건 API 응답 대조 및 INS-14 재사용 범위 판단
- [ ] BE 최종 판정 후 QA 기록표·집계 반영

## 관련 PR / 문서

- [BE 요청 댓글](https://github.com/yuudong123/CQC/issues/103#issuecomment-6117222988)
- [기존 E2 API·검사 DB 증거](https://github.com/yuudong123/CQC/blob/0a4521ecd862a1626f7301ac2920e15bee467a07/docs/wbs/BE-10-2-local-evidence.jsonl)
- [기존 공유 CSV](https://github.com/yuudong123/CQC/blob/dev/docs/wbs/results/qa-be-proxy-20261008/supplement/ops10-inspections.csv)
- [전달자료 폴더](https://github.com/yuudong123/CQC/tree/feat/mlops/docs/wbs/results/qa-mo-ins14-ins17-20261012)
- [결과 보고서](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-ins14-ins17-20261012/README.md)
- [INS-17 실DB 오류 행](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-ins14-ins17-20261012/ins17-db-check.json)
- [INS-14 E1 대안 제어 대조](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-ins14-ins17-20261012/e1-fallback-control-review.json)
- [SQL·DB 원자료](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-ins14-ins17-20261012/mysql-result.jsonl)
- 전달 ZIP: `qa-mo-ins14-ins17-20261012.zip` — 필요 시 별도 첨부
- 핵심 파일: `README.md`, `query.sql`, `mysql-result.jsonl`, `ins17-db-check.json`, `e1-fallback-control-review.json`, `e1-fallback-control-table.csv`, `manifest.sha256`
