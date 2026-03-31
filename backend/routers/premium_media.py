from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from backend.services.voice_service import voice_service
from backend.services.heygen_service import heygen_service
from backend.middleware.auth import get_current_user
from backend import models
from pydantic import BaseModel

router = APIRouter(
    prefix="/premium",
    tags=["premium-media"],
    responses={404: {"description": "Not found"}},
)

class SpeakRequest(BaseModel):
    text: str
    voice_id: str = None

@router.post("/voice/stream")
async def stream_voice(
    request: SpeakRequest,
    current_user: models.User = Depends(get_current_user)
):
    """
    Stream audio TTS for the given text.
    Protected endpoint.
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    # Generate generator
    audio_generator = voice_service.generate_audio_stream(
        text=request.text,
        voice_id=request.voice_id
    )
    
    return StreamingResponse(
        audio_generator,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=speech.mp3"}
    )

@router.post("/avatar/token")
async def get_avatar_token(
    current_user: models.User = Depends(get_current_user)
):
    """
    Get a temporary access token for HeyGen Interactive Avatar SDK.
    """
    result = heygen_service.get_access_token()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result
