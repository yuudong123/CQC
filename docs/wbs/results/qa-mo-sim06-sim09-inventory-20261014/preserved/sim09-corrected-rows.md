| 케이스 | 담당 | 결과 (통과/실패/차단) | 실행자 | 일시 | 커밋·모델 | 비고·결함 번호 |
|---|---|---|---|---|---|---|
| QA-INS-11 | BE | 차단 | 홍유나 (MO-09 자동화) | 2026-10-06 14:55:57 KST | E2 image SHA unverified; script HEAD 1f521804e458 | [E2] 관찰=통과; 범위=부분: 이력 errorCode·processingStatus·excluded 미확인; Inference 정지 중 재검사·저장, 복구 후 정상 저장 확인; 이력 필드 미확인 |
| QA-INS-13 | BE | 실패 | 홍유나 (MO-09 자동화) | 2026-10-06 14:57:08 KST | E2 image SHA unverified; script HEAD 1f521804e458 | [E2] 관찰=실패; 범위=전체; MySQL 정지 중 정상 bin·저장 실패, 복구 후 저장 확인; 응답 4.938초로 2초 라인 간격 초과 |
| QA-SIM-09 | BE | 차단 | 홍유나 (MO-09 자동화) | 2026-10-06 14:57:08 KST | E2 image SHA unverified; script HEAD 1f521804e458 | [E2] 관찰=통과; 범위=부분: 자동 저장 건수·Simulator 구성요소 상태 미확인; MySQL 정지 중 lastSeenAt 증가, 복구 후 직접 요청 저장 확인; 자동 저장 건수·구성요소 상태 미확인 |
