from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services import calc
from app.services.days import get_day
from app.services.sales import (
    add_line, bills_for_day, check_line_form, customer_is_visible, get_bill, get_line,
    get_or_create_bill, hide_bill, hide_line, lines_for_bill, negative_stock_warning,
    pending_lines, set_rate, update_bill_details, update_line, walk_in_customer_id,
)
from app.services.trips import profile_label, to_int
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_login)])

EMPTY_ADD = {"stock_key": "", "stock_label": "", "qty_text": "", "rate_text": ""}


def _bill_or_404(bill_id: int) -> dict:
    bill = get_bill(bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


def _line_or_404(bill_id: int, line_id: int) -> dict:
    line = get_line(line_id)
    if line is None or line["bill_id"] != bill_id:
        raise HTTPException(status_code=404, detail="Line not found")
    return line


def _bill_page(request: Request, bill: dict, errors=None, add=None, details=None, status=200):
    lines = lines_for_bill(bill["id"])
    totals = calc.bill_totals(lines, bill["discount_amount"])
    return templates.TemplateResponse(request, "bills/detail.html", {
        "bill": bill, "lines": lines, "totals": totals, "errors": errors or [],
        "add": add or EMPTY_ADD,
        "details": details or {"discount": bill["discount_amount"], "note": bill["note"] or ""},
        "flash": request.session.pop("flash", None),
        "warn": request.session.pop("flash_warn", None)}, status_code=status)


# ---------------- starting a sale ----------------
@router.get("/sales/day/{day_id:int}/sale")
def new_sale_form(request: Request, day_id: int):
    if get_day(day_id) is None:
        raise HTTPException(status_code=404, detail="Day not found")
    return templates.TemplateResponse(request, "bills/new.html", {
        "day_id": day_id, "errors": [], "customer_id": "", "customer_label": ""})


@router.post("/sales/day/{day_id:int}/sale")
def start_sale(request: Request, day_id: int, form: dict = Depends(form_data)):
    if get_day(day_id) is None:
        raise HTTPException(status_code=404, detail="Day not found")
    customer_id = to_int(form.get("customer_id"))
    if not customer_id or not customer_is_visible(customer_id):
        return templates.TemplateResponse(request, "bills/new.html", {
            "day_id": day_id, "errors": ["Please choose a customer."],
            "customer_id": "", "customer_label": ""}, status_code=400)
    return _open_bill(request, day_id, customer_id)


@router.post("/sales/day/{day_id:int}/walk-in")
def walk_in_sale(request: Request, day_id: int):
    if get_day(day_id) is None:
        raise HTTPException(status_code=404, detail="Day not found")
    return _open_bill(request, day_id, walk_in_customer_id())


def _open_bill(request: Request, day_id: int, customer_id: int):
    bill_id, created = get_or_create_bill(day_id, customer_id)
    if not created:
        name = profile_label("customers", customer_id)
        request.session["flash"] = (f"{name} already has a bill for this Day, so new lines "
                                    f"go on the same bill.")
    return RedirectResponse(f"/bills/{bill_id}", status_code=303)


# ---------------- the bill page ----------------
@router.get("/bills/{bill_id:int}")
def bill_page(request: Request, bill_id: int):
    return _bill_page(request, _bill_or_404(bill_id))


@router.post("/bills/{bill_id:int}/details")
def save_details(request: Request, bill_id: int, form: dict = Depends(form_data)):
    bill = _bill_or_404(bill_id)
    discount, error = calc.parse_money(form.get("discount"), blank=calc.ZERO)
    note = (form.get("note") or "").strip()
    if error:
        return _bill_page(request, bill, errors=[f"Discount: {error}"],
                          details={"discount": form.get("discount") or "", "note": note}, status=400)
    update_bill_details(bill_id, discount, note or None)
    return RedirectResponse(f"/bills/{bill_id}", status_code=303)


@router.post("/bills/{bill_id:int}/hide")
def hide(request: Request, bill_id: int):
    bill = _bill_or_404(bill_id)
    hide_bill(bill_id)
    return RedirectResponse(f"/sales/day/{bill['day_id']}", status_code=303)


# ---------------- lines ----------------
@router.post("/bills/{bill_id:int}/lines")
def add_sale_line(request: Request, bill_id: int, form: dict = Depends(form_data)):
    bill = _bill_or_404(bill_id)
    values, errors = check_line_form(form)
    if errors:
        return _bill_page(request, bill, errors=errors, add=values, status=400)
    add_line(bill_id, values)
    warning = negative_stock_warning(values["trip_row_id"], values["vehicle_id"])
    if warning:
        request.session["flash_warn"] = warning
    return RedirectResponse(f"/bills/{bill_id}", status_code=303)


@router.get("/bills/{bill_id:int}/lines/{line_id:int}/edit")
def edit_line_form(request: Request, bill_id: int, line_id: int):
    bill = _bill_or_404(bill_id)
    line = _line_or_404(bill_id, line_id)
    from app.services import stock
    option = stock.get_stock(line["trip_row_id"], line["from_vehicle_id"])
    shown = stock.describe(option) if option else {"id": "", "label": "", "sub": ""}
    values = {"stock_key": shown["id"], "stock_label": f"{shown['label']} | {shown['sub']}" if option else "",
              "qty_text": str(line["qty"]),
              "rate_text": "" if line["rate"] is None else str(line["rate"])}
    return templates.TemplateResponse(request, "bills/line_form.html", {
        "bill": bill, "line": line, "v": values, "errors": []})


@router.post("/bills/{bill_id:int}/lines/{line_id:int}/edit")
def edit_line(request: Request, bill_id: int, line_id: int, form: dict = Depends(form_data)):
    bill = _bill_or_404(bill_id)
    line = _line_or_404(bill_id, line_id)
    values, errors = check_line_form(form)
    if errors:
        return templates.TemplateResponse(request, "bills/line_form.html", {
            "bill": bill, "line": line, "v": values, "errors": errors}, status_code=400)
    update_line(line_id, values)
    warning = negative_stock_warning(values["trip_row_id"], values["vehicle_id"])
    if warning:
        request.session["flash_warn"] = warning
    return RedirectResponse(f"/bills/{bill_id}", status_code=303)


@router.post("/bills/{bill_id:int}/lines/{line_id:int}/hide")
def hide_sale_line(bill_id: int, line_id: int):
    _bill_or_404(bill_id)
    _line_or_404(bill_id, line_id)
    hide_line(line_id)
    return RedirectResponse(f"/bills/{bill_id}", status_code=303)


# ---------------- Rate pending list ----------------
def _pending_page(request: Request, errors=None, status=200):
    return templates.TemplateResponse(request, "bills/rate_pending.html", {
        "lines": pending_lines(), "errors": errors or []}, status_code=status)


@router.get("/rate-pending")
def rate_pending(request: Request):
    return _pending_page(request)


@router.post("/rate-pending/{line_id:int}")
def save_rate(request: Request, line_id: int, form: dict = Depends(form_data)):
    if get_line(line_id) is None:
        raise HTTPException(status_code=404, detail="Line not found")
    rate, error = calc.parse_money(form.get("rate"), blank=None)
    if error or rate is None:
        return _pending_page(request, errors=[f"Rate: {error or 'Please enter a rate.'}"], status=400)
    set_rate(line_id, rate)
    return RedirectResponse("/rate-pending", status_code=303)
