from datetime import UTC, datetime, timedelta

from app.core.clock import utc_now


def test_utc_now_returns_aware_utc_datetime() -> None:
    before = datetime.now(UTC)
    now = utc_now()
    after = datetime.now(UTC)

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    assert before <= now <= after


def test_utc_now_does_not_depend_on_local_timezone() -> None:
    now = utc_now()

    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)
