"""
Server-Sent Events (SSE) Router - Replaces Socket.IO for real-time updates.
Uses SSE for one-way streaming (server → client) which works better with Cloud Run.
"""
import asyncio
import json
from datetime import datetime
from typing import Optional, AsyncGenerator
import structlog

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_optional_user

logger = structlog.get_logger("nomadnest.sse")

router = APIRouter(prefix="/sse", tags=["sse"])


# ============================================================================
# SSE Helpers
# ============================================================================

def format_sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    json_data = json.dumps(data)
    return f"event: {event}\ndata: {json_data}\n\n"


def format_keepalive() -> str:
    """Format a keepalive comment to keep connection alive."""
    return ": keepalive\n\n"


# ============================================================================
# AI Chat Streaming
# ============================================================================

# In-memory storage for active AI streams (production would use Redis)
_ai_streams: dict[str, asyncio.Queue] = {}


async def push_to_stream(session_id: str, event: str, data: dict):
    """Push an event to an SSE stream (called from AI concierge)."""
    if session_id in _ai_streams:
        await _ai_streams[session_id].put({"event": event, "data": data})


async def close_stream(session_id: str):
    """Close an SSE stream."""
    if session_id in _ai_streams:
        await _ai_streams[session_id].put(None)  # Signal end


@router.get("/ai/{session_id}")
async def ai_chat_stream(
    session_id: str,
    request: Request,
    current_user: models.User = Depends(get_optional_user),
):
    """
    SSE endpoint for AI chat streaming.
    Client connects here to receive AI response chunks in real-time.
    """
    
    async def event_generator() -> AsyncGenerator[str, None]:
        # Create queue for this session
        queue = asyncio.Queue()
        _ai_streams[session_id] = queue
        
        logger.info("sse_ai_stream_started", session_id=session_id)
        
        try:
            # Send initial connection event
            yield format_sse("connected", {"session_id": session_id})
            
            # Keepalive interval
            keepalive_interval = 15  # seconds
            
            while True:
                try:
                    # Wait for next message with timeout for keepalive
                    message = await asyncio.wait_for(
                        queue.get(),
                        timeout=keepalive_interval
                    )
                    
                    if message is None:
                        # Stream ended
                        yield format_sse("done", {"session_id": session_id})
                        break
                    
                    yield format_sse(message["event"], message["data"])
                    
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield format_keepalive()
                
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("sse_client_disconnected", session_id=session_id)
                    break
                    
        finally:
            # Cleanup
            if session_id in _ai_streams:
                del _ai_streams[session_id]
            logger.info("sse_ai_stream_ended", session_id=session_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# ============================================================================
# Notifications Stream
# ============================================================================

# Notification queues per user
_notification_streams: dict[str, asyncio.Queue] = {}


async def push_notification(user_id: str, notification_type: str, data: dict):
    """Push a notification to a user's SSE stream."""
    if user_id in _notification_streams:
        await _notification_streams[user_id].put({
            "event": notification_type,
            "data": {
                **data,
                "timestamp": datetime.utcnow().isoformat(),
            }
        })


@router.get("/notifications")
async def notifications_stream(
    request: Request,
    current_user: models.User = Depends(get_optional_user),
):
    """
    SSE endpoint for real-time notifications.
    Includes: booking updates, AI insights, escalation updates.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = current_user.id
    
    async def event_generator() -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()
        _notification_streams[user_id] = queue
        
        logger.info("sse_notifications_started", user_id=user_id)
        
        try:
            yield format_sse("connected", {"user_id": user_id})
            
            keepalive_interval = 30
            
            while True:
                try:
                    message = await asyncio.wait_for(
                        queue.get(),
                        timeout=keepalive_interval
                    )
                    
                    if message is None:
                        break
                    
                    yield format_sse(message["event"], message["data"])
                    
                except asyncio.TimeoutError:
                    yield format_keepalive()
                
                if await request.is_disconnected():
                    break
                    
        finally:
            if user_id in _notification_streams:
                del _notification_streams[user_id]
            logger.info("sse_notifications_ended", user_id=user_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# Agent Job Streaming
# ============================================================================

_agent_streams: dict[str, asyncio.Queue] = {}


async def push_agent_update(job_id: str, event: str, data: dict):
    """Push an agent job update to subscribers."""
    if job_id in _agent_streams:
        await _agent_streams[job_id].put({"event": event, "data": data})


@router.get("/agent/{job_id}")
async def agent_job_stream(
    job_id: str,
    request: Request,
):
    """
    SSE endpoint for agent job progress updates.
    """
    
    async def event_generator() -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()
        _agent_streams[job_id] = queue
        
        logger.info("sse_agent_stream_started", job_id=job_id)
        
        try:
            yield format_sse("subscribed", {"job_id": job_id})
            
            keepalive_interval = 15
            
            while True:
                try:
                    message = await asyncio.wait_for(
                        queue.get(),
                        timeout=keepalive_interval
                    )
                    
                    if message is None:
                        yield format_sse("job_complete", {"job_id": job_id})
                        break
                    
                    yield format_sse(message["event"], message["data"])
                    
                except asyncio.TimeoutError:
                    yield format_keepalive()
                
                if await request.is_disconnected():
                    break
                    
        finally:
            if job_id in _agent_streams:
                del _agent_streams[job_id]
            logger.info("sse_agent_stream_ended", job_id=job_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# Compatibility Layer (for existing code using websocket.py functions)
# ============================================================================

async def emit_agent_step(job_id: str, step_data: dict):
    """Compatibility: emit agent step update."""
    await push_agent_update(job_id, "agent_step", step_data)


async def emit_booking_created(user_id: str, booking_data: dict):
    """Compatibility: emit booking creation."""
    await push_notification(user_id, "booking_created", booking_data)


async def emit_notification(user_id: str, notification_data: dict):
    """Compatibility: emit notification."""
    await push_notification(user_id, "new_notification", notification_data)


async def emit_agent_job_status(job_id: str, status: str, result: Optional[dict] = None):
    """Compatibility: emit job status."""
    await push_agent_update(job_id, "job_status", {
        "job_id": job_id,
        "status": status,
        "result": result
    })
    if status in ["completed", "failed"]:
        await close_stream(job_id)


async def emit_proactive_insight(user_id: str, insight_data: dict):
    """Compatibility: emit AI insight."""
    await push_notification(user_id, "ai_insight", {
        **insight_data,
        "ai_generated": True
    })


async def emit_escalation_update(user_id: str, escalation_data: dict):
    """Compatibility: emit escalation update."""
    await push_notification(user_id, "escalation_update", escalation_data)
