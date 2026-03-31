"""
$NEST Token Router — API endpoints for token earn/spend/stake operations.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from backend.services.nest_token import (
    get_balance,
    earn_tokens,
    spend_tokens,
    stake_tokens,
    unstake_tokens,
    get_tokenomics,
    get_leaderboard,
    get_user_history,
)

router = APIRouter()


class EarnRequest(BaseModel):
    user_id: str
    action: str
    metadata: Optional[Dict[str, Any]] = None


class SpendRequest(BaseModel):
    user_id: str
    perk: str
    metadata: Optional[Dict[str, Any]] = None


class StakeRequest(BaseModel):
    user_id: str
    amount: float
    lock_days: int


class UnstakeRequest(BaseModel):
    user_id: str
    position_id: str


@router.get("/tokenomics")
def token_overview() -> Dict[str, Any]:
    """Get $NEST tokenomics overview, earn rules, spend perks, and staking tiers."""
    return get_tokenomics()


@router.get("/balance/{user_id}")
def user_balance(user_id: str) -> Dict[str, Any]:
    """Get user's NEST balance, staked amount, and earnings summary."""
    return get_balance(user_id)


@router.post("/earn")
def earn(req: EarnRequest) -> Dict[str, Any]:
    """Award NEST tokens for a user action."""
    result = earn_tokens(req.user_id, req.action, req.metadata)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/spend")
def spend(req: SpendRequest) -> Dict[str, Any]:
    """Spend NEST tokens on a perk/benefit."""
    result = spend_tokens(req.user_id, req.perk, req.metadata)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/stake")
def stake(req: StakeRequest) -> Dict[str, Any]:
    """Stake NEST tokens for APY rewards."""
    result = stake_tokens(req.user_id, req.amount, req.lock_days)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/unstake")
def unstake(req: UnstakeRequest) -> Dict[str, Any]:
    """Unstake tokens after lock period."""
    result = unstake_tokens(req.user_id, req.position_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/leaderboard")
def leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top NEST token holders."""
    return get_leaderboard(limit)


@router.get("/history/{user_id}")
def history(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get user's NEST transaction history."""
    return get_user_history(user_id, limit)
