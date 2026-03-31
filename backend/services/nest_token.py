"""
$NEST Token Service — Tokenomics engine for the NomadNest ecosystem.

Token Economics:
    Total Supply:     100,000,000 NEST
    Community Pool:   40,000,000  (earn rewards, vested 5y)
    Team:             20,000,000  (4y vest, 1y cliff)
    Treasury/DAO:     15,000,000
    Investors:        15,000,000
    Liquidity:        10,000,000

Earn Actions:
    Complete booking        →  50 NEST
    Write verified review   →  25 NEST
    Update safety data      →  15 NEST
    Refer a friend          →  100 NEST
    Help in community       →  10 NEST
    Connect wallet          →  20 NEST
    First booking bonus     →  100 NEST
    30-day streak           →  75 NEST
    Complete SBT milestone  →  50 NEST

Spend Actions:
    Booking discount (5%)   →  500 NEST
    Booking discount (10%)  →  1,000 NEST
    Booking discount (20%)  →  2,500 NEST
    Pro subscription (1mo)  →  2,000 NEST
    Priority matching       →  200 NEST
    Featured profile        →  300 NEST
    Governance vote boost   →  100 NEST per extra weight

Staking:
    30 days  →  5% APY (in NEST)
    90 days  →  12% APY
    180 days →  20% APY
    365 days →  30% APY
"""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import uuid4

logger = logging.getLogger("nomadnest.nest_token")

# ─── Token Constants ───────────────────────────────────────────
TOTAL_SUPPLY = 100_000_000
COMMUNITY_POOL = 40_000_000
TREASURY = 15_000_000

# ─── Earn Rules ────────────────────────────────────────────────
EARN_RULES: Dict[str, Dict[str, Any]] = {
    "booking_complete": {
        "amount": 50,
        "description": "Completed a booking",
        "category": "transaction",
        "icon": "🏨",
        "max_daily": 5,
    },
    "review_written": {
        "amount": 25,
        "description": "Wrote a verified review",
        "category": "contribution",
        "icon": "⭐",
        "max_daily": 3,
    },
    "safety_update": {
        "amount": 15,
        "description": "Updated safety data",
        "category": "contribution",
        "icon": "🛡️",
        "max_daily": 5,
    },
    "referral": {
        "amount": 100,
        "description": "Referred a friend who signed up",
        "category": "growth",
        "icon": "🤝",
        "max_daily": 10,
    },
    "community_help": {
        "amount": 10,
        "description": "Helped a community member",
        "category": "community",
        "icon": "💬",
        "max_daily": 10,
    },
    "wallet_connect": {
        "amount": 20,
        "description": "Connected crypto wallet",
        "category": "onboarding",
        "icon": "🔗",
        "max_daily": 1,
        "one_time": True,
    },
    "first_booking": {
        "amount": 100,
        "description": "First booking bonus!",
        "category": "milestone",
        "icon": "🎉",
        "max_daily": 1,
        "one_time": True,
    },
    "streak_30": {
        "amount": 75,
        "description": "30-day activity streak",
        "category": "streak",
        "icon": "🔥",
        "max_daily": 1,
    },
    "sbt_milestone": {
        "amount": 50,
        "description": "Earned a new achievement badge",
        "category": "achievement",
        "icon": "🏆",
        "max_daily": 3,
    },
}

# ─── Spend Rules ───────────────────────────────────────────────
SPEND_RULES: Dict[str, Dict[str, Any]] = {
    "booking_discount_5": {
        "cost": 500,
        "description": "5% off your next booking",
        "category": "discount",
        "icon": "🏷️",
        "discount_pct": 5,
    },
    "booking_discount_10": {
        "cost": 1000,
        "description": "10% off your next booking",
        "category": "discount",
        "icon": "🏷️",
        "discount_pct": 10,
    },
    "booking_discount_20": {
        "cost": 2500,
        "description": "20% off your next booking",
        "category": "discount",
        "icon": "🏷️",
        "discount_pct": 20,
    },
    "pro_subscription": {
        "cost": 2000,
        "description": "1 month Pro subscription",
        "category": "subscription",
        "icon": "⚡",
    },
    "priority_matching": {
        "cost": 200,
        "description": "Priority in community matching for 7 days",
        "category": "boost",
        "icon": "🎯",
    },
    "featured_profile": {
        "cost": 300,
        "description": "Featured profile badge for 30 days",
        "category": "boost",
        "icon": "✨",
    },
    "governance_boost": {
        "cost": 100,
        "description": "Extra voting weight on proposals",
        "category": "governance",
        "icon": "🗳️",
    },
}

# ─── Staking Tiers ─────────────────────────────────────────────
STAKING_TIERS = {
    30: {"apy": 0.05, "label": "30 Days", "min_stake": 100},
    90: {"apy": 0.12, "label": "90 Days", "min_stake": 500},
    180: {"apy": 0.20, "label": "180 Days", "min_stake": 1000},
    365: {"apy": 0.30, "label": "365 Days", "min_stake": 2500},
}

# ─── In-Memory Ledger (production: use DB) ────────────────────
_user_balances: Dict[str, float] = {}
_transaction_log: List[Dict[str, Any]] = []
_staking_positions: List[Dict[str, Any]] = []
_one_time_claimed: Dict[str, set] = {}  # user_id -> set of action_types


def get_balance(user_id: str) -> Dict[str, Any]:
    """Get user's NEST token balance and summary."""
    balance = _user_balances.get(user_id, 0)
    
    # Calculate staked amount
    staked = sum(
        p["amount"] for p in _staking_positions
        if p["user_id"] == user_id and p["status"] == "active"
    )
    
    # Calculate pending rewards from staking
    pending_rewards = 0
    for p in _staking_positions:
        if p["user_id"] == user_id and p["status"] == "active":
            days_staked = (time.time() - p["start_ts"]) / 86400
            daily_rate = p["apy"] / 365
            pending_rewards += p["amount"] * daily_rate * days_staked
    
    # Count transactions
    total_earned = sum(
        t["amount"] for t in _transaction_log
        if t["user_id"] == user_id and t["type"] == "earn"
    )
    total_spent = sum(
        t["amount"] for t in _transaction_log
        if t["user_id"] == user_id and t["type"] == "spend"
    )
    
    return {
        "user_id": user_id,
        "balance": round(balance, 2),
        "staked": round(staked, 2),
        "pending_rewards": round(pending_rewards, 2),
        "total_earned": round(total_earned, 2),
        "total_spent": round(total_spent, 2),
        "total_value": round(balance + staked + pending_rewards, 2),
    }


def earn_tokens(
    user_id: str,
    action: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Award NEST tokens for a user action.
    
    Args:
        user_id: The user earning tokens
        action: Action type from EARN_RULES
        metadata: Optional context (booking_id, review_id, etc.)
    
    Returns:
        dict with amount earned, new balance, and action details
    """
    rule = EARN_RULES.get(action)
    if not rule:
        return {"error": f"Unknown earn action: {action}"}
    
    # Check one-time actions
    if rule.get("one_time"):
        claimed = _one_time_claimed.get(user_id, set())
        if action in claimed:
            return {"error": f"Already claimed: {action}", "amount": 0}
        claimed.add(action)
        _one_time_claimed[user_id] = claimed
    
    amount = rule["amount"]
    
    # Apply to balance
    _user_balances[user_id] = _user_balances.get(user_id, 0) + amount
    
    # Log transaction
    tx = {
        "id": str(uuid4()),
        "user_id": user_id,
        "type": "earn",
        "action": action,
        "amount": amount,
        "description": rule["description"],
        "category": rule["category"],
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _transaction_log.append(tx)
    
    logger.info(f"nest_earned user={user_id} action={action} amount={amount}")
    
    return {
        "earned": amount,
        "action": action,
        "description": rule["description"],
        "icon": rule["icon"],
        "new_balance": round(_user_balances[user_id], 2),
    }


def spend_tokens(
    user_id: str,
    perk: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Spend NEST tokens on a perk/benefit.
    
    Args:
        user_id: The user spending tokens
        perk: Perk type from SPEND_RULES
        metadata: Optional context
    
    Returns:
        dict with cost, new balance, and perk details
    """
    rule = SPEND_RULES.get(perk)
    if not rule:
        return {"error": f"Unknown perk: {perk}"}
    
    balance = _user_balances.get(user_id, 0)
    cost = rule["cost"]
    
    if balance < cost:
        return {
            "error": "Insufficient NEST balance",
            "balance": round(balance, 2),
            "cost": cost,
            "deficit": round(cost - balance, 2),
        }
    
    # Deduct from balance
    _user_balances[user_id] = balance - cost
    
    # Log transaction
    tx = {
        "id": str(uuid4()),
        "user_id": user_id,
        "type": "spend",
        "action": perk,
        "amount": cost,
        "description": rule["description"],
        "category": rule["category"],
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _transaction_log.append(tx)
    
    logger.info(f"nest_spent user={user_id} perk={perk} cost={cost}")
    
    result = {
        "spent": cost,
        "perk": perk,
        "description": rule["description"],
        "icon": rule["icon"],
        "new_balance": round(_user_balances[user_id], 2),
    }
    
    # Add discount details if applicable
    if "discount_pct" in rule:
        result["discount_pct"] = rule["discount_pct"]
    
    return result


def stake_tokens(
    user_id: str,
    amount: float,
    lock_days: int,
) -> Dict[str, Any]:
    """
    Stake NEST tokens for APY rewards.
    
    Args:
        user_id: The staker
        amount: Amount of NEST to stake
        lock_days: Lock period (30, 90, 180, 365)
    """
    tier = STAKING_TIERS.get(lock_days)
    if not tier:
        return {"error": f"Invalid lock period. Choose: {list(STAKING_TIERS.keys())}"}
    
    if amount < tier["min_stake"]:
        return {"error": f"Minimum stake for {lock_days} days is {tier['min_stake']} NEST"}
    
    balance = _user_balances.get(user_id, 0)
    if balance < amount:
        return {"error": "Insufficient balance", "balance": round(balance, 2)}
    
    # Lock tokens
    _user_balances[user_id] = balance - amount
    
    position = {
        "id": str(uuid4()),
        "user_id": user_id,
        "amount": amount,
        "lock_days": lock_days,
        "apy": tier["apy"],
        "start_ts": time.time(),
        "unlock_ts": time.time() + (lock_days * 86400),
        "status": "active",
    }
    _staking_positions.append(position)
    
    # Log transaction
    _transaction_log.append({
        "id": str(uuid4()),
        "user_id": user_id,
        "type": "stake",
        "action": f"stake_{lock_days}d",
        "amount": amount,
        "description": f"Staked {amount} NEST for {lock_days} days at {tier['apy']*100}% APY",
        "category": "staking",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    
    projected_reward = round(amount * tier["apy"] * (lock_days / 365), 2)
    
    return {
        "staked": amount,
        "lock_days": lock_days,
        "apy": f"{tier['apy']*100}%",
        "projected_reward": projected_reward,
        "unlock_date": datetime.fromtimestamp(position["unlock_ts"], tz=timezone.utc).isoformat(),
        "new_balance": round(_user_balances[user_id], 2),
    }


def unstake_tokens(user_id: str, position_id: str) -> Dict[str, Any]:
    """Unstake tokens (only if lock period has passed)."""
    position = next(
        (p for p in _staking_positions if p["id"] == position_id and p["user_id"] == user_id),
        None,
    )
    if not position:
        return {"error": "Staking position not found"}
    
    if position["status"] != "active":
        return {"error": "Position already unstaked"}
    
    now = time.time()
    if now < position["unlock_ts"]:
        days_remaining = int((position["unlock_ts"] - now) / 86400)
        return {"error": f"Locked for {days_remaining} more days"}
    
    # Calculate rewards
    days_staked = (now - position["start_ts"]) / 86400
    daily_rate = position["apy"] / 365
    reward = round(position["amount"] * daily_rate * days_staked, 2)
    
    # Return principal + rewards
    total_return = position["amount"] + reward
    _user_balances[user_id] = _user_balances.get(user_id, 0) + total_return
    position["status"] = "completed"
    
    return {
        "unstaked": position["amount"],
        "reward": reward,
        "total_returned": total_return,
        "new_balance": round(_user_balances[user_id], 2),
    }


def get_tokenomics() -> Dict[str, Any]:
    """Get $NEST tokenomics overview."""
    total_circulating = sum(_user_balances.values())
    total_staked = sum(p["amount"] for p in _staking_positions if p["status"] == "active")
    total_distributed = sum(t["amount"] for t in _transaction_log if t["type"] == "earn")
    
    return {
        "token": {
            "name": "NomadNest Token",
            "symbol": "NEST",
            "total_supply": TOTAL_SUPPLY,
            "network": "Base (L2)",
            "contract": "0xNEST...deploy_pending",
        },
        "distribution": {
            "community_pool": COMMUNITY_POOL,
            "community_distributed": round(total_distributed, 2),
            "community_remaining": round(COMMUNITY_POOL - total_distributed, 2),
            "treasury": TREASURY,
            "team": 20_000_000,
            "investors": 15_000_000,
            "liquidity": 10_000_000,
        },
        "metrics": {
            "total_circulating": round(total_circulating, 2),
            "total_staked": round(total_staked, 2),
            "staking_ratio": f"{round(total_staked / max(total_circulating, 1) * 100, 1)}%",
            "unique_holders": len(_user_balances),
            "total_transactions": len(_transaction_log),
        },
        "earn_actions": {
            k: {"amount": v["amount"], "description": v["description"], "icon": v["icon"]}
            for k, v in EARN_RULES.items()
        },
        "spend_perks": {
            k: {"cost": v["cost"], "description": v["description"], "icon": v["icon"]}
            for k, v in SPEND_RULES.items()
        },
        "staking_tiers": {
            str(k): {"apy": f"{v['apy']*100}%", "label": v["label"], "min_stake": v["min_stake"]}
            for k, v in STAKING_TIERS.items()
        },
    }


def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top NEST holders."""
    sorted_holders = sorted(
        _user_balances.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:limit]
    
    return [
        {"rank": i + 1, "user_id": uid, "balance": round(bal, 2)}
        for i, (uid, bal) in enumerate(sorted_holders)
    ]


def get_user_history(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get user's NEST transaction history."""
    txs = [t for t in _transaction_log if t["user_id"] == user_id]
    return sorted(txs, key=lambda t: t["timestamp"], reverse=True)[:limit]
