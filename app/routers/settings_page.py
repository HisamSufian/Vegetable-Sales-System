from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.auth import require_login
from app.deps import form_data
from app.services.business import get_business, save_business
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_login)])


@router.get("/settings")
def settings_form(request: Request, saved: str = ""):
    return templates.TemplateResponse(request, "settings.html", {
        "biz": get_business(), "saved": bool(saved)})


@router.post("/settings")
def settings_save(form: dict = Depends(form_data)):
    save_business((form.get("business_name") or "").strip(),
                  (form.get("business_phone") or "").strip(),
                  (form.get("statement_footer") or "").strip())
    return RedirectResponse("/settings?saved=1", status_code=303)
