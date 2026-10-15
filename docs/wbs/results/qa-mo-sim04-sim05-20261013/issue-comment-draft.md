**[MO] 결과 — SIM-04·05 전용 실환경 시험 완료 (10-13)**

BE 요청에 따라 준비된 전용 환경을 현재 배포 이미지로 갱신해 실제 HTTP 시험을 진행했습니다.

- 실행자 홍유나(Codex), 시험 **2026-10-13 12:36:31~12:40:10 KST**
- Jenkins #147 SUCCESS / `91e0cd0b191935d0a3359b08285421b9dfe847c1`. Backend·Inference·Simulator 이미지 digest 3/3 일치.
- `cqc-mo103-sim0405-20261013-122650` 전용 DB·position·이미지·로그·internal network 사용, 데이터셋만 읽기 전용 공유.
- 초기 입력 후 Simulator 정지, jobs 0·검사 수 11 안정 확인 후 실행.
- **SIM-04 기대값 충족:** R=1/concurrency=2 → 200/R=2, 이전 R=1/concurrency=1 → 409 REVISION_CONFLICT 및 설정 유지, R=2로 1 복원 → 200/R=3.
- **SIM-05 10/10 기대값 충족:** 모두 422 INVALID_SETTINGS, 전후 Backend·Simulator 설정/revision 불변, 검사 수 11 유지·jobs 0.
- 요청·응답·전후 상태·snapshot·DB·로그·모델 체크섬 보존. Windows 루프백 연결 제한으로 전용 Backend 컨테이너 안에서 실제 HTTP 호출했습니다.
- 전용 컨테이너 4개는 중지하고 증거·볼륨 보존. E1 7개 서비스 ID·이미지·StartedAt·health 전후 동일 및 healthy 확인.
- 정리 단계에서 Backend는 종료 유예 25초 뒤 exit 137, OOMKilled=false였습니다. 종료 지연 원인은 미확정이며 시험 결과와 구분해 기록했습니다.
- 준비 단계 중단 두 회차는 시험 요청 전 기록이며 원자료에 보존했습니다.

**공유 증거 (`feat/mlops`)**

- [결과 보고서](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim04-sim05-20261013/README.md)
- [요청·응답·상태·snapshot·DB·로그 원자료](https://github.com/yuudong123/CQC/tree/feat/mlops/docs/wbs/results/qa-mo-sim04-sim05-20261013)
- [SIM-04 조건 대조](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim04-sim05-20261013/sim04-checks.json) · [SIM-05 10종 대조](https://github.com/yuudong123/CQC/blob/feat/mlops/docs/wbs/results/qa-mo-sim04-sim05-20261013/sim05-checks.json)

게시 시 푸시된 커밋 SHA를 함께 기재하고, 위 브랜치 링크를 해당 커밋의 고정 링크로 바꿉니다. 이 파일은 댓글 초안이며 자동 게시하지 않습니다.

공식 QA 판정과 기록표 반영은 BE 검수를 부탁드립니다. #65 공식 FAIL·INS-13 보류 및 다른 QA 판정은 유지합니다.
