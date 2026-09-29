# 원격 Windows 실행 보조 스크립트

`src/training`에 있던 PS1 네 개를 모았다. 스크립트 내용과 로그 저장 위치는 유지했다.

| 파일 | 용도 |
| --- | --- |
| `run_all.ps1` | 기본 모델·뷰 수 비교 학습 |
| `run_improvement_v2.ps1` | v2 개선 학습 |
| `run_final_fit.ps1` | 최종 재학습 |
| `run_i7_4790_acceptance.ps1` | 목표 CPU 수용시험 |

평소 데이터 작업은 `notebooks/`에서 진행한다. 이 스크립트들은 실제 학습·성능 검사를 시작한다. 외부 예약 작업에 이전 `src/training/*.ps1` 경로가 등록돼 있다면 `scripts/remote/*.ps1`로 수정해야 한다. 이번 정리에서는 원격 예약 작업·Jenkins 설정을 변경하지 않았다.
