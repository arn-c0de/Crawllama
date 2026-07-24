"""Timezone-aware datetime helpers.

Centralizes the project's time handling so security-relevant timestamps
(API-key expiry, audit events, role assignments) are consistently stored and
compared in UTC. Historically these modules used naive ``datetime.now()``,
which is DST/timezone-fragile and makes expiry comparisons ambiguous across
hosts.

Use :func:`utcnow` for every new timestamp. Use :func:`ensure_aware` whenever
you parse a stored timestamp before comparing it, so legacy naive values (from
data written before this change) are treated as UTC instead of raising
``TypeError: can't compare offset-naive and offset-aware datetimes``.
"""
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def ensure_aware(dt: datetime | None) -> datetime | None:
    """Coerce a possibly-naive datetime to UTC-aware.

    Naive datetimes (e.g. parsed from timestamps stored before UTC-awareness
    was introduced) are assumed to already be in UTC. ``None`` passes through.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
