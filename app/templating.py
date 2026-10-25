from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.timeutil import DUBAI

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def dubai_time(value) -> str:
    """Shows a stored timestamp in Dubai time, e.g. 24 Oct 2026, 19:40."""
    return value.astimezone(DUBAI).strftime("%d %b %Y, %H:%M") if value else ""


def format_date(value) -> str:
    """Shows a date like: Sat 24 Oct 2026."""
    return value.strftime("%a %d %b %Y") if value else ""


templates.env.filters["dubai"] = dubai_time
templates.env.filters["fdate"] = format_date
