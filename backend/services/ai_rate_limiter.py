"""
AI Rate Limiter - Per-user AI request quotas using Redis.
"""
import time
import structlog
from typing import Optional, Tuple
from backend.config import settings

logger = structlog.get_logger("nomadnest.rate_limiter")

try:
    import redis
    redis_client = redis.from_url(settings.REDIS_URL)
    REDIS_AVAILABLE = True
except (ImportError, Exception):
    redis_client = None
    REDIS_AVAILABLE = False


# Default quotas by subscription tier (requests per day)
TIER_QUOTAS = {
    "free": 10,
    "nomad": 100,
    "pro": 999999,      # effectively unlimited
    "annual": 999999,
    # Legacy aliases
    "basic": 100,
    "enterprise": 2000,
    "unlimited": float("inf"),
}

# Token limits per request by tier
TIER_TOKEN_LIMITS = {
    "free": 2000,
    "nomad": 4000,
    "pro": 8000,
    "annual": 8000,
    # Legacy aliases
    "basic": 4000,
    "enterprise": 16000,
    "unlimited": float("inf"),
}

# Feature gating — which features each tier can access
TIER_FEATURES = {
    "free": {"basic_search", "safety_briefs", "cost_comparison"},
    "nomad": {"basic_search", "safety_briefs", "cost_comparison",
              "trip_planning", "visa_wizard", "community_matching",
              "destination_brief", "relocation"},
    "pro": {"basic_search", "safety_briefs", "cost_comparison",
            "trip_planning", "visa_wizard", "community_matching",
            "destination_brief", "relocation",
            "voice_concierge", "do_it_for_me", "priority_support"},
    "annual": {"basic_search", "safety_briefs", "cost_comparison",
               "trip_planning", "visa_wizard", "community_matching",
               "destination_brief", "relocation",
               "voice_concierge", "do_it_for_me", "priority_support"},
}


class AIRateLimiter:
    """Rate limiter for AI API requests per user."""
    
    def __init__(self):
        self.enabled = REDIS_AVAILABLE
        self.key_prefix = "ai_quota:"
        self.window_seconds = 86400  # 24 hours
    
    def _get_key(self, user_id: str) -> str:
        return f"{self.key_prefix}{user_id}"
    
    def check_quota(
        self, 
        user_id: str, 
        tier: str = "free"
    ) -> Tuple[bool, dict]:
        """
        Check if user has remaining quota.
        
        Returns:
            (allowed, info) where info contains quota details
        """
        if not self.enabled:
            return True, {"quota_enabled": False, "message": "Quota tracking disabled"}
        
        quota = TIER_QUOTAS.get(tier, TIER_QUOTAS["free"])
        if quota == float("inf"):
            return True, {"quota": "unlimited", "remaining": "unlimited"}
        
        key = self._get_key(user_id)
        
        try:
            current = redis_client.get(key)
            used = int(current) if current else 0
            remaining = max(0, quota - used)
            
            # Get TTL for reset time
            ttl = redis_client.ttl(key)
            reset_in_seconds = ttl if ttl > 0 else self.window_seconds
            
            if used >= quota:
                return False, {
                    "allowed": False,
                    "quota": quota,
                    "used": used,
                    "remaining": 0,
                    "reset_in_seconds": reset_in_seconds,
                    "message": f"AI quota exceeded. Resets in {reset_in_seconds // 3600}h {(reset_in_seconds % 3600) // 60}m",
                }
            
            return True, {
                "allowed": True,
                "quota": quota,
                "used": used,
                "remaining": remaining,
                "reset_in_seconds": reset_in_seconds,
            }
        
        except Exception as e:
            logger.warning("quota_check_failed", error=str(e))
            return True, {"error": str(e), "allowed": True}
    
    def consume_quota(self, user_id: str, count: int = 1) -> bool:
        """
        Consume quota for a user.
        
        Args:
            user_id: User identifier
            count: Number of requests to consume (usually 1)
        
        Returns:
            True if successful
        """
        if not self.enabled:
            return True
        
        key = self._get_key(user_id)
        
        try:
            pipe = redis_client.pipeline()
            pipe.incr(key, count)
            # Set expiry if key is new
            pipe.expire(key, self.window_seconds)
            pipe.execute()
            return True
        except Exception as e:
            logger.warning("quota_consumption_failed", error=str(e))
            return False
    
    def get_usage(self, user_id: str) -> dict:
        """Get current usage for a user."""
        if not self.enabled:
            return {"enabled": False}
        
        key = self._get_key(user_id)
        
        try:
            current = redis_client.get(key)
            used = int(current) if current else 0
            ttl = redis_client.ttl(key)
            
            return {
                "used": used,
                "reset_in_seconds": ttl if ttl > 0 else 0,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def reset_quota(self, user_id: str) -> bool:
        """Reset quota for a user (admin action)."""
        if not self.enabled:
            return False
        
        key = self._get_key(user_id)
        try:
            redis_client.delete(key)
            return True
        except Exception:
            return False
    
    def check_token_limit(self, tier: str, estimated_tokens: int) -> Tuple[bool, int]:
        """
        Check if request is within token limit for tier.
        
        Returns:
            (allowed, max_tokens)
        """
        max_tokens = TIER_TOKEN_LIMITS.get(tier, TIER_TOKEN_LIMITS["free"])
        if max_tokens == float("inf"):
            return True, 16000  # Still cap for safety
        
        return estimated_tokens <= max_tokens, int(max_tokens)


# Singleton instance
ai_rate_limiter = AIRateLimiter()


def check_ai_quota(user_id: str, tier: str = "free") -> Tuple[bool, dict]:
    """Check if user can make an AI request."""
    return ai_rate_limiter.check_quota(user_id, tier)


def consume_ai_quota(user_id: str) -> bool:
    """Record an AI request against user's quota."""
    return ai_rate_limiter.consume_quota(user_id)


def get_user_tier(db, user_id: str) -> str:
    """Get user's subscription tier from database."""
    from backend import models
    
    sub = db.query(models.Subscription).filter(
        models.Subscription.user_id == user_id,
        models.Subscription.status == "active"
    ).first()
    
    return sub.tier if sub else "free"


def check_feature_access(tier: str, feature: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a feature is available for a given tier.
    
    Returns:
        (allowed, upgrade_message) — upgrade_message is None if allowed
    """
    allowed_features = TIER_FEATURES.get(tier, TIER_FEATURES["free"])
    if feature in allowed_features:
        return True, None
    
    # Determine which tier unlocks this feature
    upgrade_to = "nomad"
    for check_tier in ["nomad", "pro"]:
        if feature in TIER_FEATURES.get(check_tier, set()):
            upgrade_to = check_tier
            break
    
    TIER_PRICES = {"nomad": "$9/mo", "pro": "$29/mo", "annual": "$199/yr"}
    price = TIER_PRICES.get(upgrade_to, "$9/mo")
    
    return False, (
        f"🔒 **{feature.replace('_', ' ').title()}** requires the "
        f"**{upgrade_to.title()}** plan ({price}). "
        f"Upgrade at /pricing to unlock this feature."
    )


def get_upgrade_prompt(tier: str, context: str = "") -> Optional[str]:
    """
    Get a contextual upgrade prompt for free/nomad users.
    Returns None for pro/annual users.
    """
    if tier in ("pro", "annual"):
        return None
    
    if tier == "free":
        return (
            "💡 **Unlock more with NomadNest Nomad ($9/mo)**: "
            "Trip planning, visa wizard, community matching, and 100 daily AI queries. "
            "[Upgrade →](/pricing)"
        )
    elif tier == "nomad":
        return (
            "⚡ **Go Pro ($29/mo)**: "
            "Unlimited AI queries, voice concierge, and Do-It-For-Me bookings. "
            "[Upgrade →](/pricing)"
        )
    return None

