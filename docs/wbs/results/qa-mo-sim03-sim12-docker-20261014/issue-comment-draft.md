**[MO] 결과 — SIM-03·12 Docker 보완 검증 완료 (10-14)**

## 한 일
- BE 요청에 따라 새 전용 Docker 환경에서 SIM-03 unhealthy 및 SIM-12 재시작 기본값 복원 확인
- 요청·응답·snapshot·DB·Docker health·로그·소스 대조 자료 보존
- WSL 증거 인정 범위와 SIM-12 처리시간 정의에 대한 MO 검토 의견 정리

## 결과 (수치)
- Jenkins #155 SUCCESS / 소스 `9723907`, Backend·Inference·Simulator 이미지 digest 3/3 일치
- 실행 중 관련 Python 소스 68개가 빌드 및 BE 기준 `f8a2002`와 일치
- **SIM-03 보완 조건 12/12 충족:** 정지 200/R1 → 실제 Docker unhealthy, 검사 4건·jobs 0이 15.857초 동안 불변 → 재개 200/R2 → 검사 증가·Docker healthy 복귀
- **SIM-12 재시작 보완 조건 12/12 충족:** 실행 중 1000ms 적용 200/R3 → Compose restart → 동일 컨테이너 StartedAt 변경 → 실제/Backend 2000ms·revision 0·running=true·기본 설정 복원 및 Docker healthy
- 전용 컨테이너 4개 중지, E1 7개 서비스 ID·이미지·StartedAt·health 전후 동일 및 모두 healthy
- 정리 단계 Backend exit 137·OOMKilled=false 재관찰, 원인 미확정으로 별도 기록
- 시험 요청 전 준비 중단 2회는 원본 보존. 1분 정량 시험은 반복하지 않음

## 다른 파트 영향
- BE: 두 Docker 보완 증거 검수 및 공식 QA 반영 범위 확인 요청
- BE·DM: 소스·격리·출처가 확인된 WSL 자료는 해당 환경의 기능 증거로 사용하고 Docker 조건은 이번 별도 증거를 연결하는 안 제안. E2 대체 인정은 공동 확인 필요
- 팀: SIM-12의 '한 건 처리시간' 구간과 1000ms 정량 기준 확인 요청. 코드상 worker는 HTTP 응답 뒤 position 저장까지 포함하고 이미지 준비는 worker 생성 전임
- FE: SIM-07 실제 웹 경고 확인은 기존 요청대로 남아 있음

## 남은 일
- [ ] BE 증거 검수 및 SIM-03·12 공식 판정 범위 확인
- [ ] WSL 증거의 E2 대체 인정 범위와 SIM-12 처리시간 정의·정량 기준 합의
- [ ] Backend 종료 지연 원인 후속 검토

전체 SIM-03·12 PASS로 확대하지 않으며 BE 공식 37/44·SIM-04/05 PASS·#65 FAIL·INS-13 보류를 유지합니다. 기존 1000ms 간격 1.1110초와 명목 기대값 불일치도 그대로 기록합니다. BE의 미Push 원자료는 이번에 직접 재검수하지 않았으며 소스 일치는 환경·모델·성능 전체 동등성을 뜻하지 않습니다.

## 관련 PR / 문서
- [결과 보고서](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim03-sim12-docker-20261014/README.md)
- [전체 원자료](https://github.com/yuudong123/CQC/tree/feat/mlops/docs/wbs/results/qa-mo-sim03-sim12-docker-20261014)
- [BE 협조 요청](https://github.com/yuudong123/CQC/issues/103#issuecomment-6141661792)

외부 게시용 초안입니다. 게시 시 보고서·원자료 링크는 증거 커밋의 고정 SHA 링크로 바꿉니다.
