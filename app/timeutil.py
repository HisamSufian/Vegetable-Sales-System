"""Dubai date and time. The server (Render) runs on UTC, which gives the wrong
date between midnight and 4 AM Dubai time, so we never use the server's date."""
from datetime import date, datetime, timedelta, timezone

DUBAI = timezone(timedelta(hours=4))   # UAE has no daylight saving


def dubai_today() -> date:
    return datetime.now(DUBAI).date()
