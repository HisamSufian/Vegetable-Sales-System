"""Search-as-you-type dropdowns with quick-add. Forms reuse these through
the picker macro in templates/_picker.html."""
from fastapi import APIRouter, Depends, Request

from app.auth import require_login
from app.deps import form_data
from app.services.profiles import (
    UniqueViolation, clean_values, create_profile, duplicate_message,
    exact_match_exists, get_kind, search_options,
)
from app.services.stock import describe, search_stock
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_login)])


@router.get("/pickers/stock/search")
def search_stock_options(request: Request, q: str = ""):
    """Stock dropdown for sales: vegetable, cartons left, farm owner, trip, date, vehicle."""
    q = q.strip()
    rows = [describe(r) for r in search_stock(q)]
    return templates.TemplateResponse(request, "_picker_results.html", {
        "kind": "stock", "rows": rows, "q": q, "can_add": False})


@router.get("/pickers/{kind}/search")
def search(request: Request, kind: str, q: str = ""):
    cfg = get_kind(kind)
    q = q.strip()
    rows = search_options(cfg, q)
    add_label = q.upper() if cfg["fields"][0]["upper"] else q
    can_add = bool(q) and not exact_match_exists(cfg, add_label)
    return templates.TemplateResponse(request, "_picker_results.html", {
        "kind": kind, "rows": rows, "q": add_label, "can_add": can_add})


@router.post("/pickers/{kind}/quick-add")
def quick_add(request: Request, kind: str, form: dict = Depends(form_data)):
    """Creates a profile with only its main field (name, or plate for vehicles)."""
    cfg = get_kind(kind)
    values, errors = clean_values(cfg, {cfg["name_field"]: form.get("name", "")})
    if errors:
        return templates.TemplateResponse(request, "_picker_chosen.html", {"error": errors[0]})
    try:
        new_id = create_profile(cfg, values)
    except UniqueViolation:
        return templates.TemplateResponse(request, "_picker_chosen.html", {
            "error": duplicate_message(cfg, values[cfg["name_field"]])})
    return templates.TemplateResponse(request, "_picker_chosen.html", {
        "id": new_id, "label": values[cfg["name_field"]]})
