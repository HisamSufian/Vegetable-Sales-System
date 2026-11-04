from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services import calc, farm_money, opening
from app.services.profiles import get_kind, get_profile
from app.services.stock_entries import parse_date
from app.templating import templates
from app.timeutil import dubai_today

router = APIRouter(prefix="/farms/{owner_id:int}", dependencies=[Depends(require_login)])


def _owner_or_404(owner_id: int) -> dict:
    owner = get_profile(get_kind("farm-owners"), owner_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Farm owner not found")
    return owner


def _back(owner_id: int) -> RedirectResponse:
    return RedirectResponse(f"/profiles/farm-owners/{owner_id}", status_code=303)


# ======================= payments =======================
def _payment_page(request, owner, values, action, heading, errors=None, status=200):
    return templates.TemplateResponse(request, "farm/payment_form.html", {
        "owner": owner, "v": values, "action": action, "heading": heading, "errors": errors or [],
        "methods": farm_money.METHODS, "method_labels": farm_money.METHOD_LABELS,
        "statuses": farm_money.CHEQUE_STATUSES}, status_code=status)


def _blank_payment() -> dict:
    return {"amount_text": "", "method": "cash", "date_text": dubai_today().isoformat(), "note_text": "",
            "cheque_no_text": "", "bank_text": "", "due_text": "", "status": "pending"}


@router.get("/payments/new")
def new_payment(request: Request, owner_id: int):
    owner = _owner_or_404(owner_id)
    return _payment_page(request, owner, _blank_payment(), f"/farms/{owner_id}/payments/new", "Add payment")


@router.post("/payments/new")
def create_payment(request: Request, owner_id: int, form: dict = Depends(form_data)):
    owner = _owner_or_404(owner_id)
    values, errors = farm_money.check_payment_form(form)
    if errors:
        return _payment_page(request, owner, values, f"/farms/{owner_id}/payments/new",
                             "Add payment", errors, 400)
    farm_money.create_payment(owner_id, values)
    return _back(owner_id)


def _payment_or_404(owner_id: int, payment_id: int) -> dict:
    payment = farm_money.get_payment(payment_id)
    if payment is None or payment["farm_owner_id"] != owner_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.get("/payments/{payment_id:int}/edit")
def edit_payment_form(request: Request, owner_id: int, payment_id: int):
    owner = _owner_or_404(owner_id)
    p = _payment_or_404(owner_id, payment_id)
    values = {"amount_text": str(p["amount"]), "method": p["method"], "date_text": p["pay_date"].isoformat(),
              "note_text": p["note"] or "", "cheque_no_text": p["cheque_no"] or "", "bank_text": p["bank"] or "",
              "due_text": p["due_date"].isoformat() if p["due_date"] else "",
              "status": p["cheque_status"] or "pending"}
    return _payment_page(request, owner, values, f"/farms/{owner_id}/payments/{payment_id}/edit", "Edit payment")


@router.post("/payments/{payment_id:int}/edit")
def edit_payment(request: Request, owner_id: int, payment_id: int, form: dict = Depends(form_data)):
    owner = _owner_or_404(owner_id)
    _payment_or_404(owner_id, payment_id)
    values, errors = farm_money.check_payment_form(form)
    if errors:
        values["status"] = form.get("cheque_status") or "pending"
        return _payment_page(request, owner, values, f"/farms/{owner_id}/payments/{payment_id}/edit",
                             "Edit payment", errors, 400)
    farm_money.update_payment(payment_id, values)
    return _back(owner_id)


@router.post("/payments/{payment_id:int}/status")
def cheque_status(owner_id: int, payment_id: int, form: dict = Depends(form_data)):
    _owner_or_404(owner_id)
    _payment_or_404(owner_id, payment_id)
    if form.get("status") in farm_money.CHEQUE_STATUSES:
        farm_money.set_cheque_status(payment_id, form["status"])
    return _back(owner_id)


@router.post("/payments/{payment_id:int}/hide")
def hide_payment(owner_id: int, payment_id: int):
    _owner_or_404(owner_id)
    _payment_or_404(owner_id, payment_id)
    farm_money.hide_payment(payment_id)
    return _back(owner_id)


# ======================= extra costs =======================
def _cost_page(request, owner, values, action, heading, errors=None, status=200, lock_trip=False):
    return templates.TemplateResponse(request, "farm/cost_form.html", {
        "owner": owner, "v": values, "action": action, "heading": heading, "errors": errors or [],
        "trips": farm_money.owner_trip_choices(owner["id"])}, status_code=status)


def _blank_cost(trip_id="") -> dict:
    return {"amount_text": "", "borne_by": "farm_owner", "date_text": dubai_today().isoformat(),
            "note_text": "", "trip_id": trip_id}


@router.get("/costs/new")
def new_cost(request: Request, owner_id: int, trip_id: str = ""):
    owner = _owner_or_404(owner_id)
    return _cost_page(request, owner, _blank_cost(trip_id), f"/farms/{owner_id}/costs/new", "Add extra cost")


@router.post("/costs/new")
def create_cost(request: Request, owner_id: int, form: dict = Depends(form_data)):
    owner = _owner_or_404(owner_id)
    values, errors = farm_money.check_cost_form(form, owner_id)
    if errors:
        values["trip_id"] = values["trip_id"] or ""
        return _cost_page(request, owner, values, f"/farms/{owner_id}/costs/new", "Add extra cost", errors, 400)
    farm_money.create_cost(owner_id, values)
    if values["trip_id"] and form.get("next") == "settlement":
        return RedirectResponse(f"/trips/{values['trip_id']}/settlement", status_code=303)
    return _back(owner_id)


def _cost_or_404(owner_id: int, cost_id: int) -> dict:
    cost = farm_money.get_cost(cost_id)
    if cost is None or cost["farm_owner_id"] != owner_id:
        raise HTTPException(status_code=404, detail="Cost not found")
    return cost


@router.get("/costs/{cost_id:int}/edit")
def edit_cost_form(request: Request, owner_id: int, cost_id: int):
    owner = _owner_or_404(owner_id)
    c = _cost_or_404(owner_id, cost_id)
    values = {"amount_text": str(c["amount"]), "borne_by": c["borne_by"], "date_text": c["cost_date"].isoformat(),
              "note_text": c["note"] or "", "trip_id": c["trip_id"] or ""}
    return _cost_page(request, owner, values, f"/farms/{owner_id}/costs/{cost_id}/edit", "Edit extra cost")


@router.post("/costs/{cost_id:int}/edit")
def edit_cost(request: Request, owner_id: int, cost_id: int, form: dict = Depends(form_data)):
    owner = _owner_or_404(owner_id)
    _cost_or_404(owner_id, cost_id)
    values, errors = farm_money.check_cost_form(form, owner_id)
    if errors:
        values["trip_id"] = values["trip_id"] or ""
        return _cost_page(request, owner, values, f"/farms/{owner_id}/costs/{cost_id}/edit",
                          "Edit extra cost", errors, 400)
    farm_money.update_cost(cost_id, values)
    return _back(owner_id)


@router.post("/costs/{cost_id:int}/hide")
def hide_cost(owner_id: int, cost_id: int):
    _owner_or_404(owner_id)
    _cost_or_404(owner_id, cost_id)
    farm_money.hide_cost(cost_id)
    return _back(owner_id)


# ======================= opening balances =======================
def _opening_page(request, owner, values, action, heading, errors=None, status=200):
    return templates.TemplateResponse(request, "farm/opening_form.html", {
        "owner": owner, "v": values, "action": action, "heading": heading,
        "errors": errors or []}, status_code=status)


def _check_opening(form: dict) -> tuple[dict, list[str]]:
    errors = []
    amount, amount_error = calc.parse_signed_money(form.get("amount"))
    if amount_error:
        errors.append(f"Amount: {amount_error}")
    when, date_error = parse_date(form.get("balance_date") or dubai_today().isoformat())
    if date_error:
        errors.append(date_error)
    note = (form.get("note") or "").strip()
    return {"amount": amount, "when": when, "note": note or None,
            "amount_text": (form.get("amount") or "").strip(),
            "date_text": (form.get("balance_date") or "").strip(), "note_text": note}, errors


@router.get("/opening/new")
def new_opening(request: Request, owner_id: int):
    owner = _owner_or_404(owner_id)
    values = {"amount_text": "", "date_text": dubai_today().isoformat(), "note_text": ""}
    return _opening_page(request, owner, values, f"/farms/{owner_id}/opening/new", "Add opening balance")


@router.post("/opening/new")
def create_opening(request: Request, owner_id: int, form: dict = Depends(form_data)):
    owner = _owner_or_404(owner_id)
    values, errors = _check_opening(form)
    if errors:
        return _opening_page(request, owner, values, f"/farms/{owner_id}/opening/new",
                             "Add opening balance", errors, 400)
    opening.create_opening("farm_owner", owner_id, values["amount"], values["when"], values["note"])
    return _back(owner_id)


def _opening_or_404(owner_id: int, opening_id: int) -> dict:
    row = opening.get_opening(opening_id)
    if row is None or row["farm_owner_id"] != owner_id:
        raise HTTPException(status_code=404, detail="Opening balance not found")
    return row


@router.get("/opening/{opening_id:int}/edit")
def edit_opening_form(request: Request, owner_id: int, opening_id: int):
    owner = _owner_or_404(owner_id)
    row = _opening_or_404(owner_id, opening_id)
    values = {"amount_text": str(row["amount"]), "date_text": row["balance_date"].isoformat(),
              "note_text": row["note"] or ""}
    return _opening_page(request, owner, values, f"/farms/{owner_id}/opening/{opening_id}/edit",
                         "Edit opening balance")


@router.post("/opening/{opening_id:int}/edit")
def edit_opening(request: Request, owner_id: int, opening_id: int, form: dict = Depends(form_data)):
    owner = _owner_or_404(owner_id)
    _opening_or_404(owner_id, opening_id)
    values, errors = _check_opening(form)
    if errors:
        return _opening_page(request, owner, values, f"/farms/{owner_id}/opening/{opening_id}/edit",
                             "Edit opening balance", errors, 400)
    opening.update_opening(opening_id, values["amount"], values["when"], values["note"])
    return _back(owner_id)


@router.post("/opening/{opening_id:int}/hide")
def hide_opening(owner_id: int, opening_id: int):
    _owner_or_404(owner_id)
    _opening_or_404(owner_id, opening_id)
    opening.hide_opening(opening_id)
    return _back(owner_id)
