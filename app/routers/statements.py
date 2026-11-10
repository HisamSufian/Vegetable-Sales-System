from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.services import statements
from app.services.business import get_business
from app.services.profiles import get_kind, get_profile
from app.services.trips import to_int
from app.templating import templates
from app.timeutil import dubai_today, month_start

router = APIRouter(prefix="/statements", dependencies=[Depends(require_login)])

MESSAGES = {
    "choose": "Please choose a farm owner or a customer from the list.",
    "walkin": "Walk-in / Cash customers pay on the spot, so there is no statement for them.",
}


def _parse(text: str) -> date | None:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


def _range(date_from: str, date_to: str) -> tuple[date, date, list[str]]:
    """The requested period, or this month so far when it is missing or wrong."""
    today = dubai_today()
    d_from, d_to = _parse(date_from), _parse(date_to)
    errors = []
    if (date_from or date_to) and not (d_from and d_to):
        errors.append("Please choose both dates. Showing this month instead.")
    if d_from and d_to and d_from > d_to:
        errors.append("The first date is after the last date. Showing this month instead.")
        d_from = d_to = None
    if not (d_from and d_to):
        d_from, d_to = month_start(today), today
    return d_from, d_to, errors


@router.get("")
def chooser(request: Request, error: str = ""):
    today = dubai_today()
    return templates.TemplateResponse(request, "statements/index.html", {
        "date_from": month_start(today).isoformat(), "date_to": today.isoformat(),
        "error": MESSAGES.get(error)})


@router.get("/open")
def open_statement(kind: str = "", party_id: str = "", date_from: str = "", date_to: str = ""):
    pid = to_int(party_id)
    if kind not in ("farm-owner", "customer") or not pid:
        return RedirectResponse("/statements?error=choose", status_code=303)
    query_string = urlencode({"date_from": date_from, "date_to": date_to})
    return RedirectResponse(f"/statements/{kind}/{pid}?{query_string}", status_code=303)


@router.get("/farm-owner/{owner_id:int}")
def farm_owner_statement(request: Request, owner_id: int, date_from: str = "", date_to: str = ""):
    if get_profile(get_kind("farm-owners"), owner_id) is None:
        raise HTTPException(status_code=404, detail="Farm owner not found")
    d_from, d_to, errors = _range(date_from, date_to)
    return templates.TemplateResponse(request, "statements/farm_owner.html", {
        "s": statements.farm_owner_statement(owner_id, d_from, d_to), "biz": get_business(),
        "d_from": d_from, "d_to": d_to, "today": dubai_today(), "errors": errors})


@router.get("/customer/{customer_id:int}")
def customer_statement(request: Request, customer_id: int, date_from: str = "", date_to: str = ""):
    customer = get_profile(get_kind("customers"), customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer["is_walk_in"]:
        return RedirectResponse("/statements?error=walkin", status_code=303)
    d_from, d_to, errors = _range(date_from, date_to)
    return templates.TemplateResponse(request, "statements/customer.html", {
        "s": statements.customer_statement(customer_id, d_from, d_to), "biz": get_business(),
        "d_from": d_from, "d_to": d_to, "today": dubai_today(), "errors": errors})
