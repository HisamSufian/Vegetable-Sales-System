from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services.days import get_day, list_days, set_day_status, start_day
from app.services.trips import trips_for_day
from app.templating import templates
from app.timeutil import dubai_today

router = APIRouter(dependencies=[Depends(require_login)])


def _sales_page(request: Request, errors=None, status=200):
    return templates.TemplateResponse(request, "sales/index.html", {
        "days": list_days(), "today": dubai_today(), "errors": errors or []},
        status_code=status)


def _day_or_404(day_id: int) -> dict:
    day = get_day(day_id)
    if day is None:
        raise HTTPException(status_code=404, detail="Day not found")
    return day


@router.get("/sales")
def sales_home(request: Request):
    return _sales_page(request)


@router.post("/sales/start-day")
def start(request: Request, form: dict = Depends(form_data)):
    try:
        day_date = date.fromisoformat((form.get("day_date") or "").strip())
    except ValueError:
        return _sales_page(request, errors=["Please choose a valid date."], status=400)
    day_id, created = start_day(day_date)
    suffix = "" if created else "?existing=1"
    return RedirectResponse(f"/sales/day/{day_id}{suffix}", status_code=303)


@router.get("/sales/day/{day_id:int}")
def day_page(request: Request, day_id: int, existing: str = ""):
    day = _day_or_404(day_id)
    trips = trips_for_day(day_id)
    return templates.TemplateResponse(request, "sales/day.html", {
        "day": day, "trips": trips, "total": sum(t["total"] for t in trips),
        "existing": bool(existing)})


@router.post("/sales/day/{day_id:int}/close")
def close_day(day_id: int):
    _day_or_404(day_id)
    set_day_status(day_id, "closed")
    return RedirectResponse("/sales", status_code=303)


@router.post("/sales/day/{day_id:int}/reopen")
def reopen_day(day_id: int):
    _day_or_404(day_id)
    set_day_status(day_id, "open")
    return RedirectResponse(f"/sales/day/{day_id}", status_code=303)
