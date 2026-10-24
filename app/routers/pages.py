from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.auth import check_credentials, require_login
from app.db import query
from app.templating import templates

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    if request.session.get("email"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    result = check_credentials(email, password)
    if result == "ok":
        request.session["email"] = email.strip().lower()
        return RedirectResponse("/", status_code=303)
    if result == "error":
        message, status = "Could not reach the login service. Please try again.", 503
    else:
        message, status = "Wrong email or password.", 401
    return templates.TemplateResponse(request, "login.html", {"error": message}, status_code=status)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/")
def home(request: Request, email: str = Depends(require_login)):
    try:
        db_ok = bool(query("select 1 as ok"))
    except Exception:
        db_ok = False
    return templates.TemplateResponse(request, "home.html", {"email": email, "db_ok": db_ok})
