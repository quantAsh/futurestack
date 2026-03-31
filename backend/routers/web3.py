"""
Web3 Router - Trust Graph and Decentralized Identity.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4

from backend import models
from backend.database import get_db

router = APIRouter()


def get_db_dep():
    yield from get_db()


class WalletConnectRequest(BaseModel):
    user_id: str
    wallet_address: str
    signature: str  # For verification (mocked)


@router.post("/connect-wallet")
def connect_wallet(req: WalletConnectRequest, db: Session = Depends(get_db_dep)):
    """Connect a crypto wallet to a user profile."""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mock signature verification
    if not req.signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    user.wallet_address = req.wallet_address
    user.is_verified_on_chain = True

    # Bonus reputation for connecting wallet
    if user.reputation_score == 0:
        user.reputation_score = 100

    db.commit()

    return {
        "status": "connected",
        "user_id": user.id,
        "wallet": user.wallet_address,
        "reputation": user.reputation_score,
        "verified": True,
    }


@router.get("/reputation/{user_id}")
def get_reputation(user_id: str, db: Session = Depends(get_db_dep)):
    """Get user trust score and badges."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate level based on score
    score = user.reputation_score or 0
    level = "Newbie"
    if score > 1000:
        level = "Legend"
    elif score > 500:
        level = "Guardian"
    elif score > 100:
        level = "Member"

    return {
        "user_id": user.id,
        "score": score,
        "wallet": user.wallet_address,
        "level": level,
        "is_verified": user.is_verified_on_chain,
        "badges": [
            "Early Adopter",
            "Verified ID" if user.is_verified_on_chain else None,
        ],
    }


@router.post("/mint-badge")
def mint_badge(user_id: str, badge_type: str, db: Session = Depends(get_db_dep)):
    """Mint a reputation badge as an NFT (Mock)."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Connect wallet first")

    # Mock transaction hash
    tx_hash = "0x" + uuid4().hex

    return {
        "status": "minted",
        "badge": badge_type,
        "recipient": user.wallet_address,
        "tx_hash": tx_hash,
        "network": "Polygon",
    }
