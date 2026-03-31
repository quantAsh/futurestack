from contextvars import ContextVar
from typing import Optional

# Context variable to store the request ID for the current task/request
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
# Context variable to store the user ID for the current task/request
user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

def get_request_id() -> Optional[str]:
    return request_id_ctx.get()

def set_request_id(request_id: str) -> None:
    request_id_ctx.set(request_id)

def get_user_id() -> Optional[str]:
    return user_id_ctx.get()

def set_user_id(user_id: str) -> None:
    user_id_ctx.set(user_id)
