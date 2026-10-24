from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import NotLoggedIn
from app.config import settings
from app.db import pool
from app.routers import health, pages

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()      # open database connections when the app starts
    yield
    pool.close()     # and close them when it stops


# The interactive API docs are switched off: this is a private site.
app = FastAPI(title="Sufi Vegetable Sales System", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=60 * 60 * 24 * 30,                    # stay logged in for 30 days
    same_site="lax",
    https_only=(settings.app_env == "production"),
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.exception_handler(NotLoggedIn)
async def send_to_login(request: Request, exc: NotLoggedIn):
    return RedirectResponse("/login", status_code=303)


app.include_router(health.router)
app.include_router(pages.router)
