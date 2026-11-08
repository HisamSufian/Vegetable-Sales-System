from datetime import date

from fastapi import APIRouter, Depends, Request

from app.auth import require_login
from app.services.reports import profit_for_range, unsettled_summary
from app.services.sales import pending_count
from app.templating import templates
from app.timeutil import dubai_today, month_end, month_start, previous_month

router = APIRouter(dependencies=[Depends(require_login)])


def _parse(text: str) -> date | None:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


@router.get("/reports")
def reports_page(request: Request, date_from: str = "", date_to: str = ""):
    today = dubai_today()
    d_from, d_to = _parse(date_from), _parse(date_to)
    errors = []
    if (date_from or date_to) and not (d_from and d_to):
        errors.append("Please choose both dates. Showing this month instead.")
    if d_from and d_to and d_from > d_to:
        errors.append("The first date is after the last date. Showing this month instead.")
        d_from = d_to = None
    if not (d_from and d_to):
        d_from, d_to = month_start(today), today
    last = previous_month(today)
    return templates.TemplateResponse(request, "reports/index.html", {
        "p": profit_for_range(d_from, d_to), "unsettled": unsettled_summary(), "pending": pending_count(),
        "date_from": d_from.isoformat(), "date_to": d_to.isoformat(), "errors": errors,
        "this_month": (month_start(today).isoformat(), month_end(today).isoformat()),
        "last_month": (last.isoformat(), month_end(last).isoformat())})


@router.get("/unsettled")
def unsettled_page(request: Request):
    return templates.TemplateResponse(request, "reports/unsettled.html", {"u": unsettled_summary()})
