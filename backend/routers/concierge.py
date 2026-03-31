from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Any
from backend.services import ai_concierge
from backend.services import demo_concierge
from backend.config import settings

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"
    user_id: Optional[str] = "user-1"


class ToolCall(BaseModel):
    tool: str
    arguments: dict
    result: Any  # Can be dict, list, or primitive


class ChatResponse(BaseModel):
    response: str
    tool_calls: List[ToolCall] = []
    session_id: str = "default"
    demo_mode: Optional[bool] = False


class ClearSessionRequest(BaseModel):
    session_id: str


def has_llm_api_key() -> bool:
    """Check if any LLM API key is configured."""
    return bool(settings.OPENAI_API_KEY or settings.GEMINI_API_KEY)


@router.post("/chat")
def chat_concierge(request: ChatRequest):
    """
    Agentic chat endpoint. Supports tool-calling for bookings, searches, etc.
    Falls back to demo mode when no LLM API key is available.
    """
    if has_llm_api_key():
        # Use real AI with LLM
        result = ai_concierge.agentic_chat(
            query=request.query,
            session_id=request.session_id or "default",
            user_id=request.user_id or "user-1",
        )
        result["demo_mode"] = False
    else:
        # Use demo mode with database-powered responses
        result = demo_concierge.demo_chat(
            query=request.query,
            session_id=request.session_id or "default",
            user_id=request.user_id or "user-1",
        )
    
    return result


@router.post("/clear-session")
def clear_session(request: ClearSessionRequest):
    """Clear conversation memory for a session."""
    ai_concierge.clear_conversation(request.session_id)
    return {"status": "cleared", "session_id": request.session_id}


@router.get("/status")
def concierge_status():
    """Check if concierge is using real AI or demo mode."""
    return {
        "demo_mode": not has_llm_api_key(),
        "llm_available": has_llm_api_key(),
        "message": "Real AI enabled" if has_llm_api_key() else "Demo mode - using database-powered contextual responses"
    }


# --- SSE Streaming Endpoint ---

from fastapi import Request
from fastapi.responses import StreamingResponse
import asyncio
import json


class StreamChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"
    user_id: Optional[str] = "user-1"


def format_sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/chat/stream/{session_id}")
async def stream_chat(
    session_id: str,
    query: str,
    user_id: str = "user-1",
    request: Request = None,
):
    """
    SSE streaming endpoint for AI chat.
    Sends real-time progress updates as the AI processes the request.
    
    Events sent:
    - thinking: AI is processing
    - tool_start: Starting a tool call
    - tool_result: Tool completed
    - chunk: Text response chunk
    - done: Response complete
    """
    
    async def event_generator():
        try:
            # Send thinking event
            yield format_sse("thinking", {"message": "Processing your request..."})
            await asyncio.sleep(0.1)
            
            if has_llm_api_key():
                # Real AI mode with streaming simulation
                yield format_sse("thinking", {"message": "Analyzing query..."})
                
                # Call the AI
                result = ai_concierge.agentic_chat(
                    query=query,
                    session_id=session_id,
                    user_id=user_id,
                )
                
                # Stream tool calls if any
                for i, tool_call in enumerate(result.get("tool_calls", [])):
                    yield format_sse("tool_start", {
                        "tool": tool_call["tool"],
                        "index": i,
                    })
                    await asyncio.sleep(0.2)
                    yield format_sse("tool_result", {
                        "tool": tool_call["tool"],
                        "result": tool_call["result"],
                        "index": i,
                    })
                    await asyncio.sleep(0.1)
                
                # Stream response in chunks
                response_text = result.get("response", "")
                words = response_text.split()
                chunk_size = 5  # words per chunk
                
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i:i+chunk_size])
                    yield format_sse("chunk", {"text": chunk + " "})
                    await asyncio.sleep(0.05)
                
                yield format_sse("done", {
                    "session_id": session_id,
                    "full_response": response_text,
                    "tool_calls_count": len(result.get("tool_calls", [])),
                })
            else:
                # Demo mode
                yield format_sse("thinking", {"message": "Demo mode active..."})
                
                result = demo_concierge.demo_chat(
                    query=query,
                    session_id=session_id,
                    user_id=user_id,
                )
                
                # Stream response in word chunks
                response_text = result.get("response", "No response")
                words = response_text.split()
                chunk_size = 3
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i:i+chunk_size])
                    yield format_sse("chunk", {"text": chunk + " "})
                    await asyncio.sleep(0.04)
                
                yield format_sse("done", {
                    "session_id": session_id,
                    "full_response": response_text,
                    "demo_mode": True,
                })
                
        except Exception as e:
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

