from fastapi import APIRouter
from app.core.logger import get_logs

router = APIRouter()


@router.get("/logs")
def fetch_logs():
    """Return all backend logs."""
    return {"logs": get_logs()}
