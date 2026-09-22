"""동기 SQLAlchemy Engine과 Session factory 생성 함수."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import Settings, get_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    """Settings의 DATABASE_URL로 MySQL 동기 Engine을 생성한다."""

    runtime_settings = settings or get_settings()
    if not runtime_settings.database_url:
        raise RuntimeError("DATABASE_URL 설정이 필요합니다.")

    database_url = make_url(runtime_settings.database_url)
    if database_url.drivername != "mysql+pymysql":
        raise ValueError("DATABASE_URL은 mysql+pymysql 형식이어야 합니다.")

    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """요청이나 논리 DB 작업마다 사용할 동기 Session factory를 만든다."""

    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )
