"""동기 SQLAlchemy Engine과 Session factory 생성 함수."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import Settings, get_settings

_MYSQL_CONNECTION_ERROR_CODES = frozenset({2002, 2003, 2006, 2013, 2055})


def is_database_unavailable_error(exc: Exception) -> bool:
    """초기 저장 실패 중 실제 MySQL 연결 단절만 구분한다."""

    if not isinstance(exc, DBAPIError):
        return False
    if exc.connection_invalidated:
        return True
    args = getattr(exc.orig, "args", ())
    return (
        bool(args)
        and isinstance(args[0], int)
        and args[0] in _MYSQL_CONNECTION_ERROR_CODES
    )


def create_db_engine(settings: Settings | None = None) -> Engine:
    """Settings의 DATABASE_URL로 MySQL 동기 Engine을 생성한다."""

    runtime_settings = settings or get_settings()
    if not runtime_settings.database_url:
        raise RuntimeError("DATABASE_URL 설정이 필요합니다.")

    database_url = make_url(runtime_settings.database_url)
    if database_url.drivername != "mysql+pymysql":
        raise ValueError("DATABASE_URL은 mysql+pymysql 형식이어야 합니다.")

    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": runtime_settings.db_connect_timeout_seconds},
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """요청이나 논리 DB 작업마다 사용할 동기 Session factory를 만든다."""

    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )
