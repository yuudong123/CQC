# SIM-03 로컬 기능 검증 — BE 최종 검수 (2026-10-13)

**로컬 기능 조건 충족 / Docker unhealthy 미검증 / 공식 PASS 보류.** QA 집계에 포함하지 않는다. E2 Docker 대신 D의 CQC-AUTO01·WSL 프로세스 전용 환경에서 실행했으며 환경 대체 인정 범위는 미확정이다. 로컬 /health 503은 Docker unhealthy의 대체 증거가 아니다.

- 원본: `D:\CQC-SIM-QA\evidence\sim03-20261013-143622\`
- 실행 소스: `f8a200221d7aa4cb3f44877e4114d464208366d7`
- 실행 당시 저장소 HEAD 및 이번 검수 HEAD: `8e47f6d7f5b3d7525263fa8537367de4392cf093`
- 두 커밋의 src/api·src/simulator 변경 없음 재확인. MO SIM-04·05는 다른 회차·소스 `91e0cd0`이며 합치지 않는다.
- 기존 3건과 이번 신규 3건을 ID 집합으로 구분했다. 신규 전 건 COMPLETED·제어/저장 SUCCEEDED·12프레임·오류 없음.

| 요청 | HTTP | revision |
|---|---|---|
| 시작 | 200 | 1→2 |
| 정지 | 200 | 2→3 |
| 재개 | 200 | 3→4 |
| 최종 정지 | 200 | 4→5 |

정지 전후 검사 수 5→5(추가 0), position 5 유지. 정지 완료 후 10.0719초 시계열은 5·5·5·5·5·5, snapshot과 실제 /state 일치, /health 503이었다. 요청 시작·응답 완료 시각은 각 HTTP 원본에서 구분한다. 이번 회차는 정지 전에 요청 2건이 완료돼 진행 중 요청이 남지 않은 경우이며, 진행 중인 요청을 의도적으로 만들어 별도 시험한 것은 아니다.

재개 예상 index 5(0부터 시작), `demo-601142012000-002`와 실제 첫 검사 `9e5c6480-8489-4786-9861-e0b1920da47c` 일치. 순번은 position % 869로 대조했다. 최종 검사/제어/오류 6/6/0, position 6, revision 5·running=false·status=stopped·concurrency 1·intervalMs 2000·faults=[]를 확인했다.

원본 요청·응답, 단계별 snapshot·Simulator 상태·검사/제어 DB 기록과 6개 관찰 파일만 바이트 그대로 보존했다. 실행 도구·전체 로그·AUTO inventory는 복사하지 않으며 원본 위치에서 유지한다. 원본 manifest 전체 검증은 불일치 0이다. `source-manifest.sha256`는 원본 목록(여기에 복사하지 않은 파일도 포함), `copy-provenance.json`는 선택 파일의 원본/복사본 해시, `manifest.sha256`는 이 저장소 보존본과 새 설명 파일의 해시다. 별도 가공한 README·해시/출처 목록을 원본 시험 산출물로 표현하지 않는다.

허용한 선택 파일에서 인증 헤더·토큰·비밀번호·개인정보를 검토했다. 기술용 inspection_id·command_id·로컬 증거 경로만 유지한다. 기존 AUTO 증거 해시·DB 파일 메타데이터 전후 일치 결과는 result.json에서 연결한다. 이번 검수에서 시험·API·DB 접속이나 환경 변경은 하지 않았다.

공식 PASS에는 Docker unhealthy 직접 증거와 로컬 기능 증거의 대체 인정 확인이 남는다. MO 종료 컨테이너의 unhealthy를 이 로컬 회차에 붙이지 않는다. 자료는 현재 로컬 미커밋 상태이며 Commit·Push 후 공유 링크를 연결한다.
