"""Helper utilities for analytics date window normalization, bucket interpolation, and streak tracking."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.analytics.schemas import (
    AnalyticsDateRangeQueryDto,
    AnalyticsGroupBy,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RANGE_DAYS: int = 30
MAX_RANGE_DAYS: int = 366
DAY_SECONDS: int = 86_400

T = TypeVar("T")
R = TypeVar("R")


def get_analytics_timezone() -> ZoneInfo:
    """Returns the application-configured ZoneInfo timezone with UTC+7 fallback.

    Returns:
        ZoneInfo: Active timezone representation.

    Example:
        >>> tz = get_analytics_timezone()
    """
    try:
        return ZoneInfo(settings.ANALYTICS_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


@dataclass
class ResolvedAnalyticsDateRange:
    """Normalized, validated [from_date, to_date) window for analytics queries.

    Attributes:
        from_date (datetime): Inclusive start instant.
        to_date (datetime): Exclusive end instant.
    """

    from_date: datetime
    to_date: datetime


def parse_iso_datetime(value: str) -> datetime:
    """Parses an ISO 8601 string into an aware datetime object.

    Args:
        value (str): ISO timestamp string.

    Returns:
        datetime: Aware UTC datetime.

    Raises:
        HTTPException: 400 if parsing fails.

    Example:
        >>> dt = parse_iso_datetime("2026-09-15T00:00:00Z")
    """
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ISO datetime string: {value}",
        ) from None


def resolve_analytics_date_range(
    query: AnalyticsDateRangeQueryDto,
    now: datetime | None = None,
) -> ResolvedAnalyticsDateRange:
    """Resolves and validates raw query parameters into concrete date boundaries.

    Args:
        query (AnalyticsDateRangeQueryDto): Range query input.
        now (datetime | None, optional): Evaluation instant. Defaults to UTC now.

    Returns:
        ResolvedAnalyticsDateRange: Validated start and end instants.

    Raises:
        HTTPException: 400 if from >= to or interval exceeds 366 days.

    Example:
        >>> q = AnalyticsDateRangeQueryDto()
        >>> r = resolve_analytics_date_range(q)
        >>> r.from_date < r.to_date
        True
    """
    eval_now = now or datetime.now(UTC)
    if eval_now.tzinfo is None:
        eval_now = eval_now.replace(tzinfo=UTC)

    to_date = parse_iso_datetime(query.to_time) if query.to_time else eval_now
    from_date = (
        parse_iso_datetime(query.from_time) if query.from_time else (to_date - timedelta(days=DEFAULT_RANGE_DAYS))
    )

    if from_date >= to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be before to",
        )

    delta_days = (to_date - from_date).total_seconds() / DAY_SECONDS
    if delta_days > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analytics date range cannot exceed {MAX_RANGE_DAYS} days",
        )

    return ResolvedAnalyticsDateRange(from_date=from_date, to_date=to_date)


def resolve_analytics_group_by(
    range_: ResolvedAnalyticsDateRange,
    requested: AnalyticsGroupBy | None = None,
) -> AnalyticsGroupBy:
    """Determines aggregation granularity based on query window length.

    Rules:
    - If explicitly requested, honor it.
    - Span <= 31 days -> DAY
    - Span <= 180 days -> WEEK
    - Span > 180 days -> MONTH

    Args:
        range_ (ResolvedAnalyticsDateRange): Date window.
        requested (AnalyticsGroupBy | None, optional): User-selected option. Defaults to None.

    Returns:
        AnalyticsGroupBy: Resolved bucket granularity.

    Example:
        >>> r = ResolvedAnalyticsDateRange(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 15, tzinfo=UTC))
        >>> resolve_analytics_group_by(r) == AnalyticsGroupBy.DAY
        True
    """
    if requested:
        return requested

    span_days = (range_.to_date - range_.from_date).total_seconds() / DAY_SECONDS
    if span_days <= 31:
        return AnalyticsGroupBy.DAY
    if span_days <= 180:
        return AnalyticsGroupBy.WEEK
    return AnalyticsGroupBy.MONTH


def round_ratio(numerator: int | float, denominator: int | float) -> float:
    """Computes a decimal ratio rounded to 4 decimal places with zero-division protection.

    Args:
        numerator (int | float): Dividend.
        denominator (int | float): Divisor.

    Returns:
        float: Rounded ratio in [0, 1].

    Example:
        >>> round_ratio(3, 4)
        0.75
        >>> round_ratio(1, 0)
        0.0
    """
    if denominator <= 0:
        return 0.0
    ratio = numerator / denominator
    return min(1.0, max(0.0, round(ratio, 4)))


def normalize_bucket_date(d: date, group_by: AnalyticsGroupBy) -> date:
    """Normalizes a local calendar date to the start of its aggregation bucket.

    - DAY: Unchanged.
    - WEEK: Preceding Monday.
    - MONTH: 1st of month.

    Args:
        d (date): Local calendar date.
        group_by (AnalyticsGroupBy): Aggregation level.

    Returns:
        date: Normalized start date of bucket.

    Example:
        >>> from datetime import date
        >>> from app.modules.analytics.schemas import AnalyticsGroupBy
        >>> normalize_bucket_date(date(2026, 9, 15), AnalyticsGroupBy.MONTH)
        datetime.date(2026, 9, 1)
    """
    match group_by:
        case AnalyticsGroupBy.MONTH:
            return date(d.year, d.month, 1)
        case AnalyticsGroupBy.WEEK:
            days_from_monday = d.weekday()  # Monday is 0
            return d - timedelta(days=days_from_monday)
        case AnalyticsGroupBy.DAY:
            return d


def increment_bucket(d: date, group_by: AnalyticsGroupBy) -> date:
    """Advances a bucket date forward by one unit of the specified granularity.

    Args:
        d (date): Current bucket start date.
        group_by (AnalyticsGroupBy): Granularity level.

    Returns:
        date: Next bucket start date.

    Example:
        >>> from datetime import date
        >>> from app.modules.analytics.schemas import AnalyticsGroupBy
        >>> increment_bucket(date(2026, 9, 1), AnalyticsGroupBy.DAY)
        datetime.date(2026, 9, 2)
    """
    match group_by:
        case AnalyticsGroupBy.MONTH:
            month = d.month + 1
            year = d.year
            if month > 12:
                month = 1
                year += 1
            return date(year, month, 1)
        case AnalyticsGroupBy.WEEK:
            return d + timedelta(days=7)
        case AnalyticsGroupBy.DAY:
            return d + timedelta(days=1)


def fill_missing_buckets(
    rows: list[dict[str, Any]],
    from_date: datetime,
    to_date: datetime,
    group_by: AnalyticsGroupBy,
    map_fn: Callable[[dict[str, Any]], R],
    empty_fn: Callable[[str], R],
) -> list[R]:
    """Interpolates missing time series buckets across the half-open interval.

    Args:
        rows (list[dict[str, Any]]): Database records containing 'bucket' key.
        from_date (datetime): Start datetime.
        to_date (datetime): End datetime.
        group_by (AnalyticsGroupBy): Bucket granularity.
        map_fn (Callable): Transformation for existing row.
        empty_fn (Callable): Factory for empty bucket row.

    Returns:
        list[R]: Continuous list of mapped time series buckets.

    Example:
        >>> rows = [{"bucket": "2026-08-01", "count": 5}]
        >>> start = datetime(2026, 8, 1, tzinfo=UTC)
        >>> end = datetime(2026, 8, 3, tzinfo=UTC)
        >>> res = fill_missing_buckets(rows, start, end, AnalyticsGroupBy.DAY, lambda r: r, lambda b: {"bucket": b, "count": 0})
        >>> len(res)
        2
    """
    tz = get_analytics_timezone()
    by_bucket = {r["bucket"]: r for r in rows if "bucket" in r}

    local_start = from_date.astimezone(tz).date()
    local_end = (to_date - timedelta(microseconds=1)).astimezone(tz).date()

    start_bucket = normalize_bucket_date(local_start, group_by)
    end_bucket = normalize_bucket_date(local_end, group_by)

    results: list[R] = []
    current = start_bucket
    while current <= end_bucket:
        bucket_label = current.strftime("%Y-%m-%d")
        if bucket_label in by_bucket:
            results.append(map_fn(by_bucket[bucket_label]))
        else:
            results.append(empty_fn(bucket_label))
        current = increment_bucket(current, group_by)

    return results


def format_date_to_study_date(dt: datetime, tz: ZoneInfo) -> str:
    """Formats an instant into a YYYY-MM-DD calendar date string in the target timezone.

    Args:
        dt (datetime): Target timestamp.
        tz (ZoneInfo): Application timezone.

    Returns:
        str: Date string formatted as YYYY-MM-DD.

    Example:
        >>> from datetime import datetime, timezone
        >>> from zoneinfo import ZoneInfo
        >>> format_date_to_study_date(datetime(2026, 9, 15, tzinfo=timezone.utc), ZoneInfo("UTC"))
        '2026-09-15'
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz).strftime("%Y-%m-%d")


def add_days_to_date_str(date_str: str, days: int) -> str:
    """Offsets a YYYY-MM-DD date string by a specified number of days.

    Args:
        date_str (str): Base date string.
        days (int): Relative offset in days.

    Returns:
        str: Offset date string formatted as YYYY-MM-DD.

    Example:
        >>> add_days_to_date_str("2026-09-15", 1)
        '2026-09-16'
    """
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (d + timedelta(days=days)).strftime("%Y-%m-%d")


def calculate_streak(
    completed_dates: set[str],
    today_str: str,
) -> tuple[int, int, bool, list[dict[str, Any]]]:
    """Computes daily study streaks and trailing 7-day checklist.

    Args:
        completed_dates (set[str]): Set of YYYY-MM-DD strings where study was completed.
        today_str (str): Current local study date string.

    Returns:
        tuple[int, int, bool, list[dict[str, Any]]]:
            - current_streak (int)
            - longest_streak (int)
            - is_today_completed (bool)
            - recent_days (list[dict])

    Example:
        >>> calculate_streak({"2026-09-15"}, "2026-09-15")[0]
        1
    """
    is_today_completed = today_str in completed_dates

    # 1. Current streak calculation
    current_streak = 0
    if is_today_completed:
        current_streak = 1
        check_date = add_days_to_date_str(today_str, -1)
        while check_date in completed_dates:
            current_streak += 1
            check_date = add_days_to_date_str(check_date, -1)
    else:
        yesterday_str = add_days_to_date_str(today_str, -1)
        if yesterday_str in completed_dates:
            current_streak = 1
            check_date = add_days_to_date_str(yesterday_str, -1)
            while check_date in completed_dates:
                current_streak += 1
                check_date = add_days_to_date_str(check_date, -1)

    # 2. Longest streak calculation
    sorted_dates = sorted(completed_dates)
    longest_streak = 0
    if sorted_dates:
        max_streak = 1
        cur = 1
        for i in range(1, len(sorted_dates)):
            expected_prev = add_days_to_date_str(sorted_dates[i], -1)
            if expected_prev == sorted_dates[i - 1]:
                cur += 1
                if cur > max_streak:
                    max_streak = cur
            elif sorted_dates[i] != sorted_dates[i - 1]:
                cur = 1
        longest_streak = max(max_streak, current_streak)

    # 3. 7-day checklist
    recent_days = []
    for i in range(6, -1, -1):
        d_str = add_days_to_date_str(today_str, -i)
        recent_days.append(
            {
                "date": d_str,
                "isCompleted": d_str in completed_dates,
                "isToday": (i == 0),
            }
        )

    return current_streak, longest_streak, is_today_completed, recent_days
