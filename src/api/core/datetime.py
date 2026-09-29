"""DB 저장 경계에서 사용하는 UTC 시각 변환 함수."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """밀리초로 절삭한 timezone-aware UTC 현재 시각을 반환한다."""

    now = datetime.now(timezone.utc)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def to_utc_naive(value: datetime) -> datetime:
    """aware datetime을 MySQL DATETIME(3)에 저장할 UTC naive 값으로 바꾼다."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("DB 시각 변환에는 timezone-aware datetime이 필요합니다")
    utc_value = value.astimezone(timezone.utc)
    return utc_value.replace(
        tzinfo=None,
        microsecond=(utc_value.microsecond // 1000) * 1000,
    )
