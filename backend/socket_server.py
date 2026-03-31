"""
WebSocket server using Socket.IO for real-time notifications
"""
import socketio
import structlog
from typing import Optional
from backend.utils import decode_token
from backend.config import settings

logger = structlog.get_logger("nomadnest.socket")

# ============================================================================
# Redis Adapter for Horizontal Scaling
# ============================================================================

def get_client_manager():
    """
    Get Socket.IO client manager with Redis adapter for multi-instance scaling.
    Falls back to in-memory if Redis is unavailable.
    """
    try:
        if settings.REDIS_URL and settings.ENVIRONMENT in ("production", "staging"):
            import socketio
            mgr = socketio.AsyncRedisManager(settings.REDIS_URL)
            logger.info("socketio_redis_adapter", url=settings.REDIS_URL[:30])
            return mgr
    except Exception as e:
        logger.warning("socketio_redis_unavailable", error=str(e))
    
    return None  # Falls back to in-memory


# Create Socket.IO server with Redis adapter in production
client_manager = get_client_manager()

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # TODO: Restrict in production
    logger=True,
    engineio_logger=False,
    client_manager=client_manager,  # Redis adapter for horizontal scaling
)

# Create ASGI app
socket_app = socketio.ASGIApp(sio)


# ============================================================================
# Connection Handlers
# ============================================================================

@sio.event
async def connect(sid, environ, auth):
    """Handle client connection with JWT authentication"""
    logger.info("client_connecting", sid=sid)
    
    # Extract token from auth
    token = auth.get('token') if auth else None
    
    if token:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            
            # Store user_id in session
            await sio.save_session(sid, {'user_id': user_id})
            
            # Join user-specific room
            await sio.enter_room(sid, f'user_{user_id}')
            
            # Auto-join admins to the 'admins' room for escalation alerts
            if payload.get("is_admin"):
                await sio.enter_room(sid, 'admins')
                logger.info("admin_joined_room", sid=sid, user_id=user_id)
            
            logger.info("client_authenticated", sid=sid, user_id=user_id)
            return True
        except Exception as e:
            logger.warning("client_auth_failed", sid=sid, error=str(e))
            return False
    else:
        # Allow unauthenticated connections (limited access)
        logger.info("client_unauthenticated", sid=sid)
        return True


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    session = await sio.get_session(sid)
    user_id = session.get('user_id') if session else None
    logger.info("client_disconnected", sid=sid, user_id=user_id)


# ============================================================================
# Agent Namespace (/agent)
# ============================================================================

@sio.on('connect', namespace='/agent')
async def agent_connect(sid, environ, auth):
    """Agent monitoring connection"""
    logger.info("agent_client_connected", sid=sid)
    
    # Handle auth for agent namespace too if needed
    token = auth.get('token') if auth else None
    if token:
        try:
             # Just logging for now, as we might already have session
             logger.debug("agent_namespace_auth", sid=sid)
        except:
             pass

@sio.on('subscribe_job', namespace='/agent')
async def subscribe_to_job(sid, data):
    """Subscribe to a specific agent job's updates"""
    job_id = data.get('job_id')
    if job_id:
        await sio.enter_room(sid, f'job_{job_id}', namespace='/agent')
        logger.info("job_subscribed", sid=sid, job_id=job_id)
        await sio.emit('subscribed', {'job_id': job_id}, room=sid, namespace='/agent')

@sio.on('unsubscribe_job', namespace='/agent')
async def unsubscribe_from_job(sid, data):
    """Unsubscribe from agent job updates"""
    job_id = data.get('job_id')
    if job_id:
        await sio.leave_room(sid, f'job_{job_id}', namespace='/agent')
        logger.info("job_unsubscribed", sid=sid, job_id=job_id)


# ============================================================================
# Bookings Namespace (/bookings)
# ============================================================================

@sio.on('connect', namespace='/bookings')
async def bookings_connect(sid, environ, auth):
    """Bookings updates connection"""
    logger.info("bookings_client_connected", sid=sid)
    token = auth.get('token') if auth else None
    if token:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            await sio.enter_room(sid, f'user_{user_id}', namespace='/bookings')
            logger.info("bookings_room_joined", sid=sid, user_id=user_id)
        except Exception as e:
            logger.warning("bookings_auth_failed", error=str(e))


# ============================================================================
# Notifications Namespace (/notifications)
# ============================================================================

@sio.on('connect', namespace='/notifications')
async def notifications_connect(sid, environ, auth):
    """Notifications connection"""
    logger.info("notifications_client_connected", sid=sid)
    token = auth.get('token') if auth else None
    if token:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            await sio.enter_room(sid, f'user_{user_id}', namespace='/notifications')
            logger.info("notifications_room_joined", sid=sid, user_id=user_id)
        except Exception as e:
            logger.warning("notifications_auth_failed", error=str(e))


# ============================================================================
# Helper Functions for Emitting Events
# ============================================================================

async def emit_agent_step(job_id: str, step_data: dict):
    """Emit agent step update to subscribers"""
    await sio.emit(
        'agent_step',
        step_data,
        room=f'job_{job_id}',
        namespace='/agent'
    )
    logger.debug("emitted_agent_step", job_id=job_id)


async def emit_booking_created(user_id: str, booking_data: dict):
    """Emit booking creation event to user"""
    await sio.emit(
        'booking_created',
        booking_data,
        room=f'user_{user_id}',
        namespace='/bookings'
    )
    logger.info("emitted_booking_created", user_id=user_id)


async def emit_notification(user_id: str, notification_data: dict):
    """Emit new notification to user"""
    await sio.emit(
        'new_notification',
        notification_data,
        room=f'user_{user_id}',
        namespace='/notifications'
    )
    logger.info("emitted_notification", user_id=user_id)


async def emit_agent_job_status(job_id: str, status: str, result: Optional[dict] = None):
    """Emit agent job status change"""
    await sio.emit(
        'job_status',
        {'job_id': job_id, 'status': status, 'result': result},
        room=f'job_{job_id}',
        namespace='/agent'
    )
    logger.info("emitted_job_status", job_id=job_id, status=status)


async def emit_proactive_insight(user_id: str, insight_data: dict):
    """
    Emit AI-generated proactive insight to user.
    Used for price drops, travel suggestions, booking reminders, etc.
    """
    await sio.emit(
        'ai_insight',
        {
            **insight_data,
            'timestamp': insight_data.get('timestamp') or __import__('datetime').datetime.utcnow().isoformat(),
            'ai_generated': True
        },
        room=f'user_{user_id}',
        namespace='/notifications'
    )
    logger.info("emitted_ai_insight", user_id=user_id, insight_type=insight_data.get('type', 'unknown'))


async def emit_escalation_update(user_id: str, escalation_data: dict):
    """Emit escalation status update to user"""
    await sio.emit(
        'escalation_update',
        escalation_data,
        room=f'user_{user_id}',
        namespace='/notifications'
    )
    logger.info("emitted_escalation_update", user_id=user_id)


async def emit_escalation_to_admins(escalation_data: dict):
    """
    Broadcast escalation alert to all connected admin users.
    Admins auto-join the 'admins' room on connection.
    """
    await sio.emit(
        'escalation_alert',
        {
            **escalation_data,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat(),
        },
        room='admins',
        namespace='/notifications'
    )
    logger.info("emitted_escalation_to_admins", escalation_id=escalation_data.get('escalation_id'))
