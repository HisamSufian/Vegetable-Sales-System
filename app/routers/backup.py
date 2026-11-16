from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.auth import require_login
from app.services.backup import make_backup

router = APIRouter(dependencies=[Depends(require_login)])


@router.post("/backup/download")
def download_backup():
    """Builds the zip on the spot and sends it. Nothing is stored on the server."""
    data, filename = make_backup()
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
