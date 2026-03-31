import structlog
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Any, Dict
from backend.services.ai_proxy import ai_proxy_service
from backend.utils import get_current_user
from backend import models

router = APIRouter()
logger = structlog.get_logger("nomadnest.ai_proxy")


@router.post("/proxy")
async def proxy_ai_request(
    endpoint: str = Body(...),
    body: Dict[str, Any] = Body(...),
    current_user: models.User = Depends(get_current_user),
):
    """
    Proxy point for various AI features to be handled by the backend.
    """
    try:
        result = ai_proxy_service.process_request(endpoint, body)
        return result
    except Exception as e:
        logger.error("ai_proxy_failed", endpoint=endpoint, user_id=current_user.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="AI service error")

