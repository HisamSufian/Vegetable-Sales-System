"""Files a phone needs to install the site as an app. They are public (no login),
because the browser asks for them before you are logged in."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse, Response

router = APIRouter()

SW_FILE = Path(__file__).parent.parent / "static" / "js" / "sw.js"

MANIFEST = {
    "name": "Sufi Vegetable Sales System",
    "short_name": "Sufi Veg",
    "description": "Vegetable wholesale: trips, sales, stock, farm owners and customers.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#f4f6f4",
    "theme_color": "#1f6b34",
    "icons": [
        {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return JSONResponse(MANIFEST, media_type="application/manifest+json")


@router.get("/sw.js", include_in_schema=False)
def service_worker():
    """Served from the site root so it covers every page. Never cached by the browser."""
    return Response(SW_FILE.read_text(encoding="utf-8"), media_type="application/javascript",
                    headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/icons/icon-192.png", status_code=302)
