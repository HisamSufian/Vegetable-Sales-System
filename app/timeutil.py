"""Dubai date and time. The server (Render) runs on UTC, which gives the wrong
date between midnight and 4 AM Dubai time, so we never use the server's date."""
from datetime import date, datetime, timedelta, timezone

DUBAI = timezone(timedelta(hours=4))   # UAE has no daylight saving


def dubai_today() -> date:
    return datetime.now(DUBAI).date()


def month_start(day: date) -> date:
    return day.replace(day=1)


def month_end(day: date) -> date:
    """Last day of the month (handles 28/29/30/31-day months)."""
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def previous_month(day: date) -> date:
    """First day of the month before this one."""
    return (day.replace(day=1) - timedelta(days=1)).replace(day=1)
