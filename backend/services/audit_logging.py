"""
Audit Logging Service - Immutable audit trail for admin actions.
Records all sensitive operations to an append-only audit table.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4
from enum import Enum
from sqlalchemy.orm import Session
import structlog

from backend.database import SessionLocal
# Import AuditLog from models to avoid duplicate table definition
from backend.models import AuditLog

logger = structlog.get_logger(__name__)


class AuditAction(str, Enum):
    """Categories of auditable actions."""
    # User management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role_change"
    USER_SUSPEND = "user.suspend"
    
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_PASSWORD_CHANGE = "auth.password_change"
    AUTH_MFA_ENABLE = "auth.mfa_enable"
    AUTH_MFA_DISABLE = "auth.mfa_disable"
    
    # Content moderation
    LISTING_CREATE = "listing.create"
    LISTING_UPDATE = "listing.update"
    LISTING_DELETE = "listing.delete"
    LISTING_APPROVE = "listing.approve"
    LISTING_REJECT = "listing.reject"
    
    # Financial
    BOOKING_CREATE = "booking.create"
    BOOKING_CANCEL = "booking.cancel"
    REFUND_ISSUE = "refund.issue"
    PAYOUT_PROCESS = "payout.process"
    SUBSCRIPTION_CHANGE = "subscription.change"
    
    # Admin
    ADMIN_CONFIG_CHANGE = "admin.config_change"
    ADMIN_FEATURE_TOGGLE = "admin.feature_toggle"
    ADMIN_DATA_EXPORT = "admin.data_export"
    ADMIN_USER_IMPERSONATE = "admin.user_impersonate"
    
    # System
    SYSTEM_BACKUP = "system.backup"
    SYSTEM_RESTORE = "system.restore"
    API_KEY_CREATE = "api_key.create"
    API_KEY_REVOKE = "api_key.revoke"


class AuditLogger:
    """Service for recording audit logs."""
    
    def __init__(self):
        pass
    
    def log(
        self,
        action: AuditAction,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_ip: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        before_state: Optional[Dict] = None,
        after_state: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> str:
        """
        Record an audit log entry.
        
        Args:
            action: The action being performed
            actor_id: ID of user performing action
            actor_email: Email of user
            actor_ip: IP address of request
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            before_state: State before the action
            after_state: State after the action
            metadata: Additional context
            success: Whether action succeeded
            error_message: Error message if failed
            db: Database session (creates one if not provided)
        
        Returns:
            ID of the created audit log
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # Calculate changes diff
            changes = None
            if before_state and after_state:
                changes = self._calculate_diff(before_state, after_state)
            
            log_entry = AuditLog(
                id=str(uuid4()),
                actor_id=actor_id,
                actor_email=actor_email,
                actor_ip=actor_ip,
                action=action.value if isinstance(action, AuditAction) else action,
                resource_type=resource_type,
                resource_id=resource_id,
                before_state=before_state,
                after_state=after_state,
                changes=changes,
                extra_data=metadata,  # Parameter still called metadata for API compatibility
                success="true" if success else "false",
                error_message=error_message,
            )
            
            db.add(log_entry)
            db.commit()
            
            # Also log to structured logger for external aggregation
            logger.info(
                "audit_event",
                action=action.value if isinstance(action, AuditAction) else action,
                actor_id=actor_id,
                resource_type=resource_type,
                resource_id=resource_id,
                success=success,
            )
            
            return log_entry.id
        
        except Exception as e:
            logger.error(f"Audit log failed: {e}")
            db.rollback()
            raise
        
        finally:
            if close_db:
                db.close()
    
    def _calculate_diff(self, before: Dict, after: Dict) -> Dict:
        """Calculate the difference between two states."""
        changes = {}
        
        all_keys = set(before.keys()) | set(after.keys())
        
        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)
            
            if before_val != after_val:
                changes[key] = {
                    "from": before_val,
                    "to": after_val,
                }
        
        return changes
    
    def query(
        self,
        actor_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        db: Optional[Session] = None,
    ) -> List[Dict]:
        """
        Query audit logs.
        
        Args:
            actor_id: Filter by actor
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_date: Filter from date
            end_date: Filter to date
            limit: Maximum results
            db: Database session
        
        Returns:
            List of audit log entries
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            query = db.query(AuditLog)
            
            if actor_id:
                query = query.filter(AuditLog.actor_id == actor_id)
            if action:
                query = query.filter(AuditLog.action == action)
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            if resource_id:
                query = query.filter(AuditLog.resource_id == resource_id)
            if start_date:
                query = query.filter(AuditLog.created_at >= start_date)
            if end_date:
                query = query.filter(AuditLog.created_at <= end_date)
            
            logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
            
            return [
                {
                    "id": log.id,
                    "actor_id": log.actor_id,
                    "actor_email": log.actor_email,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "changes": log.changes,
                    "success": log.success == "true",
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]
        
        finally:
            if close_db:
                db.close()


# Singleton instance
audit_logger = AuditLogger()


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def log_admin_action(
    action: AuditAction,
    actor_id: str,
    resource_type: str = None,
    resource_id: str = None,
    before: Dict = None,
    after: Dict = None,
    metadata: Dict = None,
    db: Session = None,
) -> str:
    """Log an admin action."""
    return audit_logger.log(
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before,
        after_state=after,
        metadata=metadata,
        db=db,
    )


def log_user_action(
    action: AuditAction,
    actor_id: str,
    actor_ip: str = None,
    metadata: Dict = None,
    db: Session = None,
) -> str:
    """Log a user action (login, password change, etc.)."""
    return audit_logger.log(
        action=action,
        actor_id=actor_id,
        actor_ip=actor_ip,
        resource_type="user",
        resource_id=actor_id,
        metadata=metadata,
        db=db,
    )


def log_financial_action(
    action: AuditAction,
    actor_id: str,
    resource_type: str,
    resource_id: str,
    amount_usd: float = None,
    metadata: Dict = None,
    db: Session = None,
) -> str:
    """Log a financial action (booking, refund, payout)."""
    full_metadata = {"amount_usd": amount_usd, **(metadata or {})}
    return audit_logger.log(
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=full_metadata,
        db=db,
    )
