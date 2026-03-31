"""
Wallet Router - Web3 wallet transactions and balance.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/wallet", tags=["wallet"])


# --- Schemas ---

class TransactionOut(BaseModel):
    id: str
    type: str  # payment, reward, stake, unstake, refund
    amount: float
    currency: str
    status: str
    tx_hash: Optional[str] = None
    booking_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    type: str
    amount: float
    currency: str = "ETH"
    tx_hash: Optional[str] = None
    booking_id: Optional[str] = None
    description: Optional[str] = None


class WalletBalance(BaseModel):
    eth_balance: float = 0
    usdc_balance: float = 0
    nomad_balance: float = 0  # Platform tokens
    pending_rewards: float = 0


# --- Endpoints ---

@router.get("/transactions", response_model=List[TransactionOut])
def list_transactions(
    limit: int = Query(50, le=100),
    type: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List user's wallet transactions."""
    query = db.query(models.WalletTransaction).filter(
        models.WalletTransaction.user_id == current_user.id
    )

    if type:
        query = query.filter(models.WalletTransaction.type == type)

    transactions = query.order_by(
        models.WalletTransaction.created_at.desc()
    ).limit(limit).all()

    return [TransactionOut.model_validate(t) for t in transactions]


@router.get("/balance", response_model=WalletBalance)
def get_balance(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get user's wallet balance summary."""
    # Calculate balance from transactions
    balances = {"ETH": 0, "USDC": 0, "NOMAD": 0}

    transactions = db.query(models.WalletTransaction).filter(
        models.WalletTransaction.user_id == current_user.id,
        models.WalletTransaction.status == "confirmed"
    ).all()

    for tx in transactions:
        currency = tx.currency or "ETH"
        if tx.type in ["reward", "refund", "unstake"]:
            balances[currency] = balances.get(currency, 0) + tx.amount
        elif tx.type in ["payment", "stake"]:
            balances[currency] = balances.get(currency, 0) - tx.amount

    # Calculate pending rewards
    pending = db.query(func.sum(models.WalletTransaction.amount)).filter(
        models.WalletTransaction.user_id == current_user.id,
        models.WalletTransaction.type == "reward",
        models.WalletTransaction.status == "pending"
    ).scalar() or 0

    return WalletBalance(
        eth_balance=max(0, balances.get("ETH", 0)),
        usdc_balance=max(0, balances.get("USDC", 0)),
        nomad_balance=max(0, balances.get("NOMAD", 0)),
        pending_rewards=pending
    )


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def record_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Record a new wallet transaction."""
    transaction = models.WalletTransaction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        type=data.type,
        amount=data.amount,
        currency=data.currency,
        tx_hash=data.tx_hash,
        booking_id=data.booking_id,
        description=data.description,
        status="pending" if data.tx_hash else "confirmed",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return TransactionOut.model_validate(transaction)


@router.post("/transactions/{tx_id}/confirm", response_model=TransactionOut)
def confirm_transaction(
    tx_id: str,
    tx_hash: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Confirm a pending transaction."""
    transaction = db.query(models.WalletTransaction).filter(
        models.WalletTransaction.id == tx_id,
        models.WalletTransaction.user_id == current_user.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status == "confirmed":
        return TransactionOut.model_validate(transaction)

    transaction.status = "confirmed"
    transaction.confirmed_at = datetime.now(timezone.utc)
    if tx_hash:
        transaction.tx_hash = tx_hash

    db.commit()
    db.refresh(transaction)

    return TransactionOut.model_validate(transaction)
