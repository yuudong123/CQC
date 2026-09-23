"""CQC Backend Alembic 실행 환경."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from src.api.core.config import get_settings
from src.api.db import models  # noqa: F401  # ORM 모델을 metadata에 등록한다.
from src.api.db.base import Base
from src.api.db.session import create_db_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Settings에서 Alembic이 사용할 MySQL 연결 문자열을 가져온다."""

    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("Alembic 실행에는 DATABASE_URL 설정이 필요합니다.")
    return database_url


def run_migrations_offline() -> None:
    """DB 연결 없이 SQL 스크립트 형태로 migration을 구성한다."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Settings 기반 Engine으로 실제 DB에 migration을 적용한다."""

    engine = create_db_engine()
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
