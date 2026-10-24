from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services.profiles import (
    KINDS, UniqueViolation, clean_values, create_profile, duplicate_message, get_kind,
    get_profile, list_profiles, set_hidden, update_profile, usage_blockers,
)
from app.templating import templates
from fastapi import HTTPException

router = APIRouter(prefix="/profiles", dependencies=[Depends(require_login)])


def _load(kind: str, profile_id: int):
    cfg = get_kind(kind)
    row = get_profile(cfg, profile_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return cfg, row


def _detail(request: Request, kind: str, cfg: dict, row: dict, errors=None, status=200):
    return templates.TemplateResponse(
        request, "profiles/detail.html",
        {"kind": kind, "cfg": cfg, "row": row, "errors": errors or []}, status_code=status)


@router.get("")
def profiles_home(request: Request):
    return templates.TemplateResponse(request, "profiles/index.html", {"kinds": KINDS})


@router.get("/{kind}")
def list_page(request: Request, kind: str, q: str = "", hidden: str = ""):
    cfg = get_kind(kind)
    rows = list_profiles(cfg, q.strip(), show_hidden=bool(hidden))
    context = {"kind": kind, "cfg": cfg, "rows": rows, "q": q, "hidden": bool(hidden)}
    # Search-as-you-type asks only for the list; a normal visit gets the whole page.
    name = "profiles/_rows.html" if request.headers.get("HX-Request") else "profiles/list.html"
    return templates.TemplateResponse(request, name, context)


@router.get("/{kind}/new")
def new_form(request: Request, kind: str):
    cfg = get_kind(kind)
    return templates.TemplateResponse(request, "profiles/form.html", {
        "kind": kind, "cfg": cfg, "values": {}, "errors": [],
        "heading": f"New {cfg['singular']}", "action": f"/profiles/{kind}/new",
        "cancel_url": f"/profiles/{kind}"})


@router.post("/{kind}/new")
def create(request: Request, kind: str, form: dict = Depends(form_data)):
    cfg = get_kind(kind)
    values, errors = clean_values(cfg, form)
    if not errors:
        try:
            new_id = create_profile(cfg, values)
            return RedirectResponse(f"/profiles/{kind}/{new_id}", status_code=303)
        except UniqueViolation:
            errors.append(duplicate_message(cfg, values[cfg["name_field"]]))
    return templates.TemplateResponse(request, "profiles/form.html", {
        "kind": kind, "cfg": cfg, "values": values, "errors": errors,
        "heading": f"New {cfg['singular']}", "action": f"/profiles/{kind}/new",
        "cancel_url": f"/profiles/{kind}"}, status_code=400)


@router.get("/{kind}/{profile_id:int}")
def detail(request: Request, kind: str, profile_id: int):
    cfg, row = _load(kind, profile_id)
    return _detail(request, kind, cfg, row)


@router.get("/{kind}/{profile_id:int}/edit")
def edit_form(request: Request, kind: str, profile_id: int):
    cfg, row = _load(kind, profile_id)
    return templates.TemplateResponse(request, "profiles/form.html", {
        "kind": kind, "cfg": cfg, "values": row, "errors": [],
        "heading": f"Edit {cfg['singular']}", "action": f"/profiles/{kind}/{profile_id}/edit",
        "cancel_url": f"/profiles/{kind}/{profile_id}"})


@router.post("/{kind}/{profile_id:int}/edit")
def edit(request: Request, kind: str, profile_id: int, form: dict = Depends(form_data)):
    cfg, row = _load(kind, profile_id)
    values, errors = clean_values(cfg, form)
    if not errors:
        try:
            update_profile(cfg, profile_id, values)
            return RedirectResponse(f"/profiles/{kind}/{profile_id}", status_code=303)
        except UniqueViolation:
            errors.append(duplicate_message(cfg, values[cfg["name_field"]]))
    return templates.TemplateResponse(request, "profiles/form.html", {
        "kind": kind, "cfg": cfg, "values": values, "errors": errors,
        "heading": f"Edit {cfg['singular']}", "action": f"/profiles/{kind}/{profile_id}/edit",
        "cancel_url": f"/profiles/{kind}/{profile_id}"}, status_code=400)


@router.post("/{kind}/{profile_id:int}/hide")
def hide(request: Request, kind: str, profile_id: int):
    cfg, row = _load(kind, profile_id)
    problems = usage_blockers(cfg, profile_id)
    if kind == "customers" and row["is_walk_in"]:
        problems.insert(0, "Walk-in / Cash is built in and cannot be hidden.")
    if problems:
        return _detail(request, kind, cfg, row, errors=problems, status=400)
    set_hidden(cfg, profile_id, True)
    return RedirectResponse(f"/profiles/{kind}", status_code=303)


@router.post("/{kind}/{profile_id:int}/restore")
def restore(request: Request, kind: str, profile_id: int):
    cfg, row = _load(kind, profile_id)
    set_hidden(cfg, profile_id, False)
    return RedirectResponse(f"/profiles/{kind}/{profile_id}", status_code=303)
