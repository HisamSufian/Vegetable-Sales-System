from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services import calc, customer_money, opening
from app.services.profiles import get_kind, get_profile
from app.services.stock_entries import parse_date
from app.templating import templates
from app.timeutil import dubai_today

router = APIRouter(prefix="/customers/{customer_id:int}", dependencies=[Depends(require_login)])


def _customer_or_404(customer_id: int) -> dict:
    customer = get_profile(get_kind("customers"), customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer["is_walk_in"]:
        raise HTTPException(status_code=400, detail="Walk-in / Cash pays on the spot, so it has no "
                                                    "balance, payments, write-offs or opening balance.")
    return customer


def _back(customer_id: int) -> RedirectResponse:
    return RedirectResponse(f"/profiles/customers/{customer_id}", status_code=303)


# ======================= payments / cheques =======================
def _payment_page(request, customer, values, action, heading, errors=None, status=200):
    return templates.TemplateResponse(request, "customer/payment_form.html", {
        "customer": customer, "v": values, "action": action, "heading": heading,
        "errors": errors or [], "methods": customer_money.METHODS,
        "method_labels": customer_money.METHOD_LABELS if hasattr(customer_money, "METHOD_LABELS") else {},
        "statuses": customer_money.CHEQUE_STATUSES}, status_code=status)


def _blank_payment() -> dict:
    return {"amount_text": "", "method": "cash", "date_text": dubai_today().isoformat(), "note_text": "",
            "cheque_no_text": "", "bank_text": "", "due_text": "", "status": "pending"}


def _payment_or_404(customer_id: int, payment_id: int) -> dict:
    payment = customer_money.get_payment(payment_id)
    if payment is None or payment["customer_id"] != customer_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.get("/payments/new")
def new_payment(request: Request, customer_id: int):
    customer = _customer_or_404(customer_id)
    return _payment_page(request, customer, _blank_payment(),
                         f"/customers/{customer_id}/payments/new", "Add payment received")


@router.post("/payments/new")
def create_payment(request: Request, customer_id: int, form: dict = Depends(form_data)):
    customer = _customer_or_404(customer_id)
    values, errors = customer_money.check_payment_form(form)
    if errors:
        return _payment_page(request, customer, values, f"/customers/{customer_id}/payments/new",
                             "Add payment received", errors, 400)
    customer_money.create_payment(customer_id, values)
    return _back(customer_id)


@router.get("/payments/{payment_id:int}/edit")
def edit_payment_form(request: Request, customer_id: int, payment_id: int):
    customer = _customer_or_404(customer_id)
    p = _payment_or_404(customer_id, payment_id)
    values = {"amount_text": str(p["amount"]), "method": p["method"], "date_text": p["pay_date"].isoformat(),
              "note_text": p["note"] or "", "cheque_no_text": p["cheque_no"] or "", "bank_text": p["bank"] or "",
              "due_text": p["due_date"].isoformat() if p["due_date"] else "",
              "status": p["cheque_status"] or "pending"}
    return _payment_page(request, customer, values,
                         f"/customers/{customer_id}/payments/{payment_id}/edit", "Edit payment")


@router.post("/payments/{payment_id:int}/edit")
def edit_payment(request: Request, customer_id: int, payment_id: int, form: dict = Depends(form_data)):
    customer = _customer_or_404(customer_id)
    _payment_or_404(customer_id, payment_id)
    values, errors = customer_money.check_payment_form(form)
    if errors:
        values["status"] = form.get("cheque_status") or "pending"
        return _payment_page(request, customer, values,
                             f"/customers/{customer_id}/payments/{payment_id}/edit", "Edit payment", errors, 400)
    customer_money.update_payment(payment_id, values)
    return _back(customer_id)


@router.post("/payments/{payment_id:int}/status")
def cheque_status(customer_id: int, payment_id: int, form: dict = Depends(form_data)):
    _customer_or_404(customer_id)
    _payment_or_404(customer_id, payment_id)
    if form.get("status") in customer_money.CHEQUE_STATUSES:
        customer_money.set_cheque_status(payment_id, form["status"])
    return _back(customer_id)


@router.post("/payments/{payment_id:int}/hide")
def hide_payment(customer_id: int, payment_id: int):
    _customer_or_404(customer_id)
    _payment_or_404(customer_id, payment_id)
    customer_money.hide_payment(payment_id)
    return _back(customer_id)


# ======================= write-offs =======================
def _writeoff_page(request, customer, values, action, heading, errors=None, status=200):
    return templates.TemplateResponse(request, "customer/writeoff_form.html", {
        "customer": customer, "v": values, "action": action, "heading": heading,
        "errors": errors or []}, status_code=status)


def _writeoff_or_404(customer_id: int, writeoff_id: int) -> dict:
    row = customer_money.get_writeoff(writeoff_id)
    if row is None or row["customer_id"] != customer_id:
        raise HTTPException(status_code=404, detail="Write-off not found")
    return row


@router.get("/writeoffs/new")
def new_writeoff(request: Request, customer_id: int):
    customer = _customer_or_404(customer_id)
    values = {"amount_text": "", "reason_text": "", "date_text": dubai_today().isoformat()}
    return _writeoff_page(request, customer, values, f"/customers/{customer_id}/writeoffs/new", "Add write-off")


@router.post("/writeoffs/new")
def create_writeoff(request: Request, customer_id: int, form: dict = Depends(form_data)):
    customer = _customer_or_404(customer_id)
    values, errors = customer_money.check_writeoff_form(form)
    if errors:
        return _writeoff_page(request, customer, values, f"/customers/{customer_id}/writeoffs/new",
                              "Add write-off", errors, 400)
    customer_money.create_writeoff(customer_id, values)
    return _back(customer_id)


@router.get("/writeoffs/{writeoff_id:int}/edit")
def edit_writeoff_form(request: Request, customer_id: int, writeoff_id: int):
    customer = _customer_or_404(customer_id)
    w = _writeoff_or_404(customer_id, writeoff_id)
    values = {"amount_text": str(w["amount"]), "reason_text": w["reason"], "date_text": w["adj_date"].isoformat()}
    return _writeoff_page(request, customer, values,
                          f"/customers/{customer_id}/writeoffs/{writeoff_id}/edit", "Edit write-off")


@router.post("/writeoffs/{writeoff_id:int}/edit")
def edit_writeoff(request: Request, customer_id: int, writeoff_id: int, form: dict = Depends(form_data)):
    customer = _customer_or_404(customer_id)
    _writeoff_or_404(customer_id, writeoff_id)
    values, errors = customer_money.check_writeoff_form(form)
    if errors:
        return _writeoff_page(request, customer, values,
                              f"/customers/{customer_id}/writeoffs/{writeoff_id}/edit", "Edit write-off", errors, 400)
    customer_money.update_writeoff(writeoff_id, values)
    return _back(customer_id)


@router.post("/writeoffs/{writeoff_id:int}/hide")
def hide_writeoff(customer_id: int, writeoff_id: int):
    _customer_or_404(customer_id)
    _writeoff_or_404(customer_id, writeoff_id)
    customer_money.hide_writeoff(writeoff_id)
    return _back(customer_id)


# ======================= opening balances =======================
def _opening_page(request, customer, values, action, heading, errors=None, status=200):
    return templates.TemplateResponse(request, "customer/opening_form.html", {
        "customer": customer, "v": values, "action": action, "heading": heading,
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


def _opening_or_404(customer_id: int, opening_id: int) -> dict:
    row = opening.get_opening(opening_id)
    if row is None or row["customer_id"] != customer_id:
        raise HTTPException(status_code=404, detail="Opening balance not found")
    return row


@router.get("/opening/new")
def new_opening(request: Request, customer_id: int):
    customer = _customer_or_404(customer_id)
    values = {"amount_text": "", "date_text": dubai_today().isoformat(), "note_text": ""}
    return _opening_page(request, customer, values, f"/customers/{customer_id}/opening/new",
                         "Add opening balance")


@router.post("/opening/new")
def create_opening(request: Request, customer_id: int, form: dict = Depends(form_data)):
    customer = _customer_or_404(customer_id)
    values, errors = _check_opening(form)
    if errors:
        return _opening_page(request, customer, values, f"/customers/{customer_id}/opening/new",
                             "Add opening balance", errors, 400)
    opening.create_opening("customer", customer_id, values["amount"], values["when"], values["note"])
    return _back(customer_id)


@router.get("/opening/{opening_id:int}/edit")
def edit_opening_form(request: Request, customer_id: int, opening_id: int):
    customer = _customer_or_404(customer_id)
    row = _opening_or_404(customer_id, opening_id)
    values = {"amount_text": str(row["amount"]), "date_text": row["balance_date"].isoformat(),
              "note_text": row["note"] or ""}
    return _opening_page(request, customer, values, f"/customers/{customer_id}/opening/{opening_id}/edit",
                         "Edit opening balance")


@router.post("/opening/{opening_id:int}/edit")
def edit_opening(request: Request, customer_id: int, opening_id: int, form: dict = Depends(form_data)):
    customer = _customer_or_404(customer_id)
    _opening_or_404(customer_id, opening_id)
    values, errors = _check_opening(form)
    if errors:
        return _opening_page(request, customer, values, f"/customers/{customer_id}/opening/{opening_id}/edit",
                             "Edit opening balance", errors, 400)
    opening.update_opening(opening_id, values["amount"], values["when"], values["note"])
    return _back(customer_id)


@router.post("/opening/{opening_id:int}/hide")
def hide_opening(customer_id: int, opening_id: int):
    _customer_or_404(customer_id)
    _opening_or_404(customer_id, opening_id)
    opening.hide_opening(opening_id)
    return _back(customer_id)
