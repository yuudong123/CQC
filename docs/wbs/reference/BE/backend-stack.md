# 백엔드·DB 기술 스택

- 담당자: 홍준희
- 작성 기한: 2026-09-17
- 상태: 기초 합의 반영, 상세 기술 선정 대기

## 확정된 기술 방향

- Backend는 Python과 FastAPI를 사용한다.
- Database는 MySQL을 사용한다.
- Backend는 Inference HTTP API를 호출하며 모델을 직접 로드하거나 전처리하지 않는다.
- Kafka는 MVP에서 사용하지 않는다.
- 실행 단위는 `simulator`, `inference`, `backend`, `frontend`, `mysql`이다.
- Backend는 API·MySQL·검사 정책·Virtual Control·이력·통계·CSV와 Simulator 애플리케이션 로직을 담당한다.
- MLOps는 Docker·Compose·Volume·healthcheck·재시작 정책·CI/CD·배포·로그 운영 환경을 담당한다.

## 상세 작성 시 확정할 내용

- 백엔드 언어·프레임워크와 버전
- multipart 검사·inference·이력·통계·CSV API
- 검사 상태와 오류 코드
- MySQL 테이블·관계·키·인덱스
- bin 코드와 품종·품질 매핑
- 86,400건/8,640건 순환 삭제 방식
- 장애 이미지 100개 순환 보존
- 가상 제어 내부 모듈과 장애 토글
- 마이그레이션·테스트·실행 명령
- 선택 근거와 미결정 사항

Python, FastAPI, ORM, 마이그레이션 도구, MySQL driver, HTTP client와 테스트 도구의 구체적인 제품·버전은 다음 기술 선정 작업에서 확정한다.

DB 구조는 이 문서를 단일 기준으로 삼고 다른 문서에는 물리 스키마를 중복 작성하지 않는다.
