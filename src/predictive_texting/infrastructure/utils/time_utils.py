from datetime import UTC, datetime


def now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


def now_utc_str() -> str:
    """Return current UTC datetime as ISO 8601 string."""
    return now_utc().isoformat()


def to_utc_str(dt: datetime) -> str:
    """Convert datetime to UTC ISO 8601 string."""
    return dt.astimezone(UTC).isoformat()


def from_utc_str(value: str) -> datetime:
    """Parse ISO 8601 string into UTC datetime."""
    dt = datetime.fromisoformat(value)
    return dt.astimezone(UTC)
