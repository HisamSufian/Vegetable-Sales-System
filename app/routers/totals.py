from datetime import date

from fastapi import APIRouter, Depends, Request

from app.auth import require_login
from app.services.totals import totals_overview
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_login)])


def _parse(text: str) -> date | None:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


@router.get("/totals")
def totals_page(request: Request, date_from: str = "", date_to: str = ""):
    d_from, d_to = _parse(date_from), _parse(date_to)
    return templates.TemplateResponse(request, "totals/index.html", {
        "t": totals_overview(d_from, d_to), "date_from": d_from.isoformat() if d_from else "",
        "date_to": d_to.isoformat() if d_to else "", "filtered": bool(d_from or d_to)})
