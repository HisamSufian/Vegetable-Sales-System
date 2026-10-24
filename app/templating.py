from datetime import timedelta, timezone
from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

DUBAI = timezone(timedelta(hours=4))   # UAE has no daylight saving


def dubai_time(value) -> str:
    """Shows a stored timestamp in Dubai time, e.g. 24 Oct 2026, 19:40."""
    return value.astimezone(DUBAI).strftime("%d %b %Y, %H:%M") if value else ""


templates.env.filters["dubai"] = dubai_time
