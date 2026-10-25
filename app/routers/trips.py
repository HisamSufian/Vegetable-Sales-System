from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services.days import get_day
from app.services.trips import (
    add_row, check_choices, check_row_form, create_trip, get_row, get_trip, hide_row, hide_trip,
    parse_trip_form, row_blockers, rows_for_trip, trip_blockers, update_row, update_trip,
)
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_login)])

EMPTY_ADD = {"vegetable_id": "", "vegetable_label": "", "qty_text": ""}


def _trip_or_404(trip_id: int) -> dict:
    trip = get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def _row_or_404(trip_id: int, row_id: int) -> dict:
    row = get_row(row_id)
    if row is None or row["trip_id"] != trip_id:
        raise HTTPException(status_code=404, detail="Row not found")
    return row


def _trip_form(request, heading, action, back_url, values, errors=None, status=200):
    return templates.TemplateResponse(request, "trips/form.html", {
        "heading": heading, "action": action, "back_url": back_url,
        "v": values, "errors": errors or []}, status_code=status)


def _trip_page(request, trip, errors=None, add=None, status=200):
    rows = rows_for_trip(trip["id"])
    return templates.TemplateResponse(request, "trips/detail.html", {
        "trip": trip, "rows": rows, "total": sum(r["arrived_qty"] for r in rows),
        "errors": errors or [], "add": add or EMPTY_ADD}, status_code=status)


# ---------------- trips ----------------
@router.get("/sales/day/{day_id:int}/trips/new")
def new_trip_form(request: Request, day_id: int):
    day = get_day(day_id)
    if day is None:
        raise HTTPException(status_code=404, detail="Day not found")
    empty = {"vehicle_id": "", "vehicle_label": "", "farm_owner_id": "", "farm_owner_label": "",
             "driver_id": "", "driver_label": "", "note": ""}
    return _trip_form(request, "New trip", f"/sales/day/{day_id}/trips/new",
                      f"/sales/day/{day_id}", empty)


@router.post("/sales/day/{day_id:int}/trips/new")
def create(request: Request, day_id: int, form: dict = Depends(form_data)):
    if get_day(day_id) is None:
        raise HTTPException(status_code=404, detail="Day not found")
    values = parse_trip_form(form)
    errors = check_choices(values)
    if errors:
        return _trip_form(request, "New trip", f"/sales/day/{day_id}/trips/new",
                          f"/sales/day/{day_id}", values, errors, 400)
    trip_id = create_trip(day_id, values)
    return RedirectResponse(f"/trips/{trip_id}", status_code=303)


@router.get("/trips/{trip_id:int}")
def trip_detail(request: Request, trip_id: int):
    return _trip_page(request, _trip_or_404(trip_id))


@router.get("/trips/{trip_id:int}/edit")
def edit_trip_form(request: Request, trip_id: int):
    trip = _trip_or_404(trip_id)
    values = {"vehicle_id": trip["vehicle_id"], "vehicle_label": trip["plate_number"],
              "farm_owner_id": trip["farm_owner_id"], "farm_owner_label": trip["farm_owner_name"],
              "driver_id": trip["driver_id"], "driver_label": trip["driver_name"],
              "note": trip["note"] or ""}
    return _trip_form(request, f"Edit {trip['trip_no']}", f"/trips/{trip_id}/edit",
                      f"/trips/{trip_id}", values)


@router.post("/trips/{trip_id:int}/edit")
def edit_trip(request: Request, trip_id: int, form: dict = Depends(form_data)):
    trip = _trip_or_404(trip_id)
    values = parse_trip_form(form)
    errors = check_choices(values, current=trip)
    if errors:
        return _trip_form(request, f"Edit {trip['trip_no']}", f"/trips/{trip_id}/edit",
                          f"/trips/{trip_id}", values, errors, 400)
    update_trip(trip_id, values)
    return RedirectResponse(f"/trips/{trip_id}", status_code=303)


@router.post("/trips/{trip_id:int}/hide")
def hide(request: Request, trip_id: int):
    trip = _trip_or_404(trip_id)
    problems = trip_blockers(trip_id)
    if problems:
        return _trip_page(request, trip, errors=problems, status=400)
    hide_trip(trip_id)
    return RedirectResponse(f"/sales/day/{trip['day_id']}", status_code=303)


# ---------------- vegetable rows ----------------
@router.post("/trips/{trip_id:int}/rows")
def add_trip_row(request: Request, trip_id: int, form: dict = Depends(form_data)):
    trip = _trip_or_404(trip_id)
    values, errors = check_row_form(form, minimum=1)
    if errors:
        return _trip_page(request, trip, errors=errors, add=values, status=400)
    add_row(trip_id, values["vegetable_id"], values["arrived_qty"])
    return RedirectResponse(f"/trips/{trip_id}", status_code=303)


@router.get("/trips/{trip_id:int}/rows/{row_id:int}/edit")
def edit_row_form(request: Request, trip_id: int, row_id: int):
    trip = _trip_or_404(trip_id)
    row = _row_or_404(trip_id, row_id)
    add = {"vegetable_id": row["vegetable_id"], "vegetable_label": row["vegetable_name"],
           "qty_text": str(row["arrived_qty"])}
    return templates.TemplateResponse(request, "trips/row_form.html", {
        "trip": trip, "row": row, "v": add, "errors": []})


@router.post("/trips/{trip_id:int}/rows/{row_id:int}/edit")
def edit_row(request: Request, trip_id: int, row_id: int, form: dict = Depends(form_data)):
    trip = _trip_or_404(trip_id)
    row = _row_or_404(trip_id, row_id)
    values, errors = check_row_form(form, minimum=0, current_vegetable_id=row["vegetable_id"])
    if errors:
        return templates.TemplateResponse(request, "trips/row_form.html", {
            "trip": trip, "row": row, "v": values, "errors": errors}, status_code=400)
    update_row(row_id, values["vegetable_id"], values["arrived_qty"])
    return RedirectResponse(f"/trips/{trip_id}", status_code=303)


@router.post("/trips/{trip_id:int}/rows/{row_id:int}/hide")
def hide_trip_row(request: Request, trip_id: int, row_id: int):
    trip = _trip_or_404(trip_id)
    _row_or_404(trip_id, row_id)
    problems = row_blockers(row_id)
    if problems:
        return _trip_page(request, trip, errors=problems, status=400)
    hide_row(row_id)
    return RedirectResponse(f"/trips/{trip_id}", status_code=303)
