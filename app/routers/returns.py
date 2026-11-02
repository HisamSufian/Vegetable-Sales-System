from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services import returns as ret
from app.services.sales import get_bill, get_line
from app.services.trips import reopen_if_settled
from app.templating import templates
from app.timeutil import dubai_today

router = APIRouter(dependencies=[Depends(require_login)])


def _bill_and_line(bill_id: int, line_id: int) -> tuple[dict, dict]:
    bill, line = get_bill(bill_id), get_line(line_id)
    if bill is None or line is None or line["bill_id"] != bill_id:
        raise HTTPException(status_code=404, detail="Line not found")
    return bill, line


def _form_page(request, bill, line, values, action, errors=None, status=200, return_row=None):
    others = ret.returned_total(line["id"], return_row["id"] if return_row else None)
    return templates.TemplateResponse(request, "bills/return_form.html", {
        "bill": bill, "line": line, "v": values, "action": action, "errors": errors or [],
        "others": others, "max_qty": line["qty"] - others, "return_row": return_row},
        status_code=status)


def _saved(request: Request, line: dict) -> RedirectResponse:
    request.session["flash"] = "Return saved."
    trip_no = reopen_if_settled(line["trip_row_id"])
    if trip_no:
        request.session["flash_warn"] = (f"{trip_no} was settled. It has been reopened so you can "
                                         f"adjust the settlement lines.")
    return RedirectResponse(f"/bills/{line['bill_id']}", status_code=303)


@router.get("/bills/{bill_id:int}/lines/{line_id:int}/return")
def new_return_form(request: Request, bill_id: int, line_id: int):
    bill, line = _bill_and_line(bill_id, line_id)
    values = {"qty_text": "",
              "credit_rate_text": "" if line["rate"] is None else str(line["rate"]),
              "vehicle_id": line["from_vehicle_id"], "vehicle_label": line["plate_number"],
              "date_text": dubai_today().isoformat(), "note_text": ""}
    return _form_page(request, bill, line, values, f"/bills/{bill_id}/lines/{line_id}/return")


@router.post("/bills/{bill_id:int}/lines/{line_id:int}/return")
def create(request: Request, bill_id: int, line_id: int, form: dict = Depends(form_data)):
    bill, line = _bill_and_line(bill_id, line_id)
    values, errors = ret.check_form(form, line)
    if errors:
        values["vehicle_id"] = values["vehicle_id"] or ""
        return _form_page(request, bill, line, values,
                          f"/bills/{bill_id}/lines/{line_id}/return", errors, 400)
    ret.create_return(line_id, values)
    return _saved(request, line)


def _return_context(bill_id: int, return_id: int):
    return_row = ret.get_return(return_id)
    if return_row is None:
        raise HTTPException(status_code=404, detail="Return not found")
    bill, line = _bill_and_line(bill_id, return_row["sale_line_id"])
    return bill, line, return_row


@router.get("/bills/{bill_id:int}/returns/{return_id:int}/edit")
def edit_return_form(request: Request, bill_id: int, return_id: int):
    bill, line, return_row = _return_context(bill_id, return_id)
    from app.services.trips import profile_label
    values = {"qty_text": str(return_row["qty"]), "credit_rate_text": str(return_row["credit_rate"]),
              "vehicle_id": return_row["back_to_vehicle_id"],
              "vehicle_label": profile_label("vehicles", return_row["back_to_vehicle_id"]),
              "date_text": return_row["return_date"].isoformat(), "note_text": return_row["note"] or ""}
    return _form_page(request, bill, line, values, f"/bills/{bill_id}/returns/{return_id}/edit",
                      return_row=return_row)


@router.post("/bills/{bill_id:int}/returns/{return_id:int}/edit")
def edit_return(request: Request, bill_id: int, return_id: int, form: dict = Depends(form_data)):
    bill, line, return_row = _return_context(bill_id, return_id)
    values, errors = ret.check_form(form, line, exclude_return_id=return_id)
    if errors:
        values["vehicle_id"] = values["vehicle_id"] or ""
        return _form_page(request, bill, line, values, f"/bills/{bill_id}/returns/{return_id}/edit",
                          errors, 400, return_row)
    ret.update_return(return_id, values)
    return _saved(request, line)


@router.post("/bills/{bill_id:int}/returns/{return_id:int}/hide")
def hide(bill_id: int, return_id: int):
    _bill, _line, _return_row = _return_context(bill_id, return_id)
    ret.hide_return(return_id)
    return RedirectResponse(f"/bills/{bill_id}", status_code=303)
