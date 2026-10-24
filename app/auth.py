"""Single-user login. Supabase checks the password; the app keeps a signed
cookie session. Every page except /login, /health and /static needs it."""
import httpx
from fastapi import Request

from app.config import settings


class NotLoggedIn(Exception):
    """Raised when a page needs login. main.py turns it into a redirect."""


def require_login(request: Request) -> str:
    """Add Depends(require_login) to a route (or router) to protect it.
    Returns the logged-in email."""
    email = request.session.get("email")
    if not email:
        raise NotLoggedIn()
    return email


def check_credentials(email: str, password: str) -> str:
    """Returns 'ok', 'bad' (wrong email/password) or 'error' (login service problem).
    When something is wrong with the setup, the reason is printed in the terminal
    (locally) or in the Render logs (when deployed). Passwords are never printed."""
    if email.strip().lower() != settings.admin_email.strip().lower():
        return "bad"

    base = settings.supabase_url.strip().rstrip("/")
    if not base.startswith("https://"):
        print("Login service problem: SUPABASE_URL must start with https:// "
              "(example: https://abcdefgh.supabase.co)", flush=True)
        return "error"
    url = f"{base}/auth/v1/token"

    try:
        response = httpx.post(
            url,
            params={"grant_type": "password"},
            headers={"apikey": settings.supabase_key.strip()},
            json={"email": email.strip(), "password": password},
            timeout=15,
        )
    except Exception as exc:
        print(f"Login service problem: could not call {url} -> "
              f"{type(exc).__name__}: {exc}", flush=True)
        return "error"

    if response.status_code == 200:
        return "ok"
    print(f"Login service answered {response.status_code}: {response.text[:300]}", flush=True)
    if response.status_code in (400, 401, 422):
        return "bad"
    return "error"
