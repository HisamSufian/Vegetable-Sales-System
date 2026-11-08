from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services import calc, expenses as svc
from app.templating import templates
from app.timeutil import dubai_today, month_end, month_start

router = APIRouter(prefix="/expenses", dependencies=[Depends(require_login)])


def _parse(text: str, default: date) -> date:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return default


def _form_page(request, values, action, heading, errors=None, status=200):
    return templates.TemplateResponse(request, "expenses/form.html", {
        "v": values, "action": action, "heading": heading, "errors": errors or []}, status_code=status)


def _expense_or_404(expense_id: int) -> dict:
    row = svc.get_expense(expense_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return row


@router.get("")
def expenses_page(request: Request, date_from: str = "", date_to: str = ""):
    today = dubai_today()
    d_from, d_to = _parse(date_from, month_start(today)), _parse(date_to, month_end(today))
    rows = svc.list_expenses(d_from, d_to)
    return templates.TemplateResponse(request, "expenses/index.html", {
        "rows": rows, "total": sum((r["amount"] for r in rows), calc.ZERO),
        "date_from": d_from.isoformat(), "date_to": d_to.isoformat()})


@router.get("/new")
def new_expense(request: Request):
    values = {"amount_text": "", "date_text": dubai_today().isoformat(), "note_text": "",
              "trip_id": "", "trip_label": ""}
    return _form_page(request, values, "/expenses/new", "Add expense")


@router.post("/new")
def create_expense(request: Request, form: dict = Depends(form_data)):
    values, errors = svc.check_form(form)
    if errors:
        values["trip_id"] = values["trip_id"] or ""
        return _form_page(request, values, "/expenses/new", "Add expense", errors, 400)
    svc.create_expense(values)
    return RedirectResponse("/expenses", status_code=303)


@router.get("/{expense_id:int}/edit")
def edit_expense_form(request: Request, expense_id: int):
    e = _expense_or_404(expense_id)
    values = {"amount_text": str(e["amount"]), "date_text": e["expense_date"].isoformat(),
              "note_text": e["note"] or "", "trip_id": e["trip_id"] or "",
              "trip_label": svc.trip_label(e["trip_id"])}
    return _form_page(request, values, f"/expenses/{expense_id}/edit", "Edit expense")


@router.post("/{expense_id:int}/edit")
def edit_expense(request: Request, expense_id: int, form: dict = Depends(form_data)):
    _expense_or_404(expense_id)
    values, errors = svc.check_form(form)
    if errors:
        values["trip_id"] = values["trip_id"] or ""
        return _form_page(request, values, f"/expenses/{expense_id}/edit", "Edit expense", errors, 400)
    svc.update_expense(expense_id, values)
    return RedirectResponse("/expenses", status_code=303)


@router.post("/{expense_id:int}/hide")
def hide_expense(expense_id: int):
    _expense_or_404(expense_id)
    svc.hide_expense(expense_id)
    return RedirectResponse("/expenses", status_code=303)
