from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import query

router = APIRouter()


@router.get("/health")
def health():
    """Public and lightweight. cron-job.org pings this every 10 minutes so Render
    stays awake, and the tiny database query keeps Supabase active too."""
    try:
        query("select 1 as ok")
    except Exception:
        return JSONResponse({"status": "error", "database": "down"}, status_code=503)
    return {"status": "ok", "database": "ok"}
