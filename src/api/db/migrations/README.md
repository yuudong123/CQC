# Alembic migration

이 디렉터리는 CQC Backend의 MySQL 물리 스키마 변경 이력을 관리한다.

애플리케이션 실행 시 `Base.metadata.create_all()`을 호출하지 않으며, 스키마 생성과 변경은 Alembic revision으로만 수행한다. 실제 연결 정보는 `DATABASE_URL` 환경변수로 주입한다.
