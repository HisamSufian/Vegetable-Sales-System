from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.db import query
from app.services import calc, settlement
from app.services.farm_money import costs_for_trip
from app.services.trips import get_trip
from app.templating import templates
from app.timeutil import dubai_today

router = APIRouter(dependencies=[Depends(require_login)])


def _trip_or_404(trip_id: int) -> dict:
    trip = get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def _page(request: Request, trip: dict, errors=None, status=200):
    overview = settlement.settlement_overview(trip["id"])
    costs = costs_for_trip(trip["id"])
    owner_costs = sum((c["amount"] for c in costs if c["borne_by"] == "farm_owner"), calc.ZERO)
    my_costs = sum((c["amount"] for c in costs if c["borne_by"] == "me"), calc.ZERO)
    return templates.TemplateResponse(request, "trips/settlement.html", {
        "trip": trip, "rows": overview["rows"], "settled_amount": overview["settled_amount"],
        "costs": costs, "owner_costs": owner_costs, "my_costs": my_costs,
        "net": overview["settled_amount"] - owner_costs, "errors": errors or [],
        "today": dubai_today()}, status_code=status)


def _line_trip_check(trip_id: int, line: dict) -> dict:
    rows = query(settlement.ROWS_BASE + " AND r.id = %s AND r.trip_id = %s",
                            [line["trip_row_id"], trip_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Settlement line not found")
    return rows[0]


@router.get("/trips/{trip_id:int}/settlement")
def settlement_page(request: Request, trip_id: int):
    return _page(request, _trip_or_404(trip_id))


@router.post("/trips/{trip_id:int}/settlement/lines")
def add_line(request: Request, trip_id: int, form: dict = Depends(form_data)):
    trip = _trip_or_404(trip_id)
    values, errors = settlement.check_line_form(form, trip_id)
    if errors:
        return _page(request, trip, errors=errors, status=400)
    settlement.create_line(values)
    return RedirectResponse(f"/trips/{trip_id}/settlement", status_code=303)


@router.get("/trips/{trip_id:int}/settlement/lines/{line_id:int}/edit")
def edit_line_form(request: Request, trip_id: int, line_id: int):
    trip = _trip_or_404(trip_id)
    line = settlement.get_line(line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Settlement line not found")
    row = _line_trip_check(trip_id, line)
    values = {"qty_text": str(line["qty"]), "rate_text": str(line["rate"]),
              "date_text": line["line_date"].isoformat()}
    return templates.TemplateResponse(request, "trips/settlement_line_form.html", {
        "trip": trip, "line": line, "row": row, "v": values, "errors": []})


@router.post("/trips/{trip_id:int}/settlement/lines/{line_id:int}/edit")
def edit_line(request: Request, trip_id: int, line_id: int, form: dict = Depends(form_data)):
    trip = _trip_or_404(trip_id)
    line = settlement.get_line(line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Settlement line not found")
    row = _line_trip_check(trip_id, line)
    values, errors = settlement.check_line_form({**form, "trip_row_id": line["trip_row_id"]},
                                                trip_id, exclude_line_id=line_id)
    if errors:
        return templates.TemplateResponse(request, "trips/settlement_line_form.html", {
            "trip": trip, "line": line, "row": row, "v": values, "errors": errors}, status_code=400)
    settlement.update_line(line_id, values)
    return RedirectResponse(f"/trips/{trip_id}/settlement", status_code=303)


@router.post("/trips/{trip_id:int}/settlement/lines/{line_id:int}/hide")
def hide_line(trip_id: int, line_id: int):
    _trip_or_404(trip_id)
    line = settlement.get_line(line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Settlement line not found")
    _line_trip_check(trip_id, line)
    settlement.hide_line(line_id)
    return RedirectResponse(f"/trips/{trip_id}/settlement", status_code=303)
