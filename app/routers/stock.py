from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services import stock, stock_entries
from app.services.stock_entries import TITLES
from app.templating import templates

router = APIRouter(prefix="/stock", dependencies=[Depends(require_login)])


def _kind_or_404(kind: str) -> str:
    if kind not in TITLES:
        raise HTTPException(status_code=404, detail="Unknown stock entry type")
    return kind


def _entry_or_404(kind: str, entry_id: int) -> dict:
    entry = stock_entries.load(kind, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


def _form_page(request, kind, values, action, errors=None, status=200):
    return templates.TemplateResponse(request, "stock/entry_form.html", {
        "kind": kind, "title": TITLES[kind], "v": values, "action": action,
        "errors": errors or []}, status_code=status)


@router.get("")
def stock_page(request: Request, view: str = "vehicle"):
    view = "vegetable" if view == "vegetable" else "vehicle"
    groups = stock.group_stock(stock.stock_overview(), view)
    return templates.TemplateResponse(request, "stock/index.html", {
        "groups": groups, "view": view, "entries": stock_entries.recent_entries(40),
        "flash": request.session.pop("flash", None),
        "warn": request.session.pop("flash_warn", None)})


@router.get("/{kind}/new")
def new_entry(request: Request, kind: str, stock_key: str = ""):
    _kind_or_404(kind)
    return _form_page(request, kind, stock_entries.empty_values(stock_key), f"/stock/{kind}/new")


@router.post("/{kind}/new")
def create_entry(request: Request, kind: str, form: dict = Depends(form_data)):
    _kind_or_404(kind)
    values, errors = stock_entries.check_form(kind, form)
    if errors:
        return _form_page(request, kind, values, f"/stock/{kind}/new", errors, 400)
    stock_entries.create(kind, values)
    return _saved(request, values)


@router.get("/{kind}/{entry_id:int}/edit")
def edit_entry_form(request: Request, kind: str, entry_id: int):
    _kind_or_404(kind)
    entry = _entry_or_404(kind, entry_id)
    return _form_page(request, kind, stock_entries.values_from_entry(kind, entry),
                      f"/stock/{kind}/{entry_id}/edit")


@router.post("/{kind}/{entry_id:int}/edit")
def edit_entry(request: Request, kind: str, entry_id: int, form: dict = Depends(form_data)):
    _kind_or_404(kind)
    _entry_or_404(kind, entry_id)
    values, errors = stock_entries.check_form(kind, form)
    if errors:
        return _form_page(request, kind, values, f"/stock/{kind}/{entry_id}/edit", errors, 400)
    stock_entries.update(kind, entry_id, values)
    return _saved(request, values)


@router.post("/{kind}/{entry_id:int}/hide")
def hide_entry(kind: str, entry_id: int):
    _kind_or_404(kind)
    _entry_or_404(kind, entry_id)
    stock_entries.hide(kind, entry_id)
    return RedirectResponse("/stock", status_code=303)


def _saved(request: Request, values: dict):
    request.session["flash"] = "Saved."
    warning = stock.negative_message(values["trip_row_id"], values["vehicle_id"])
    if warning:
        request.session["flash_warn"] = warning
    return RedirectResponse("/stock", status_code=303)
