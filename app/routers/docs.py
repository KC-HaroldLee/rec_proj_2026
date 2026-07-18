from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.deps import require_login

router = APIRouter()

DOCS_ROOT = Path("data/docs/rec").resolve()


@router.get("/rec/{filename}")
def rec_doc(filename: str, user: dict = Depends(require_login)):
    path = (DOCS_ROOT / filename).resolve()
    if path.parent != DOCS_ROOT or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="application/pdf")
