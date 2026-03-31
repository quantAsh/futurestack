"""
DAO Router - Community governance, token staking, treasury, and profit sharing.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from uuid import uuid4

from backend import models
from backend.database import get_db
from sqlalchemy import func

router = APIRouter()


def get_db_dep():
    yield from get_db()


# --- Schemas ---

class ProposalCreate(BaseModel):
    author_id: str
    title: str
    description: str
    duration_days: int = 7


class VoteRequest(BaseModel):
    user_id: str
    proposal_id: str
    vote: str  # yes, no


class StakeRequest(BaseModel):
    user_id: str
    amount: float  # NEST tokens to stake


class UnstakeRequest(BaseModel):
    user_id: str
    stake_id: str


class ProfitShareRequest(BaseModel):
    total_amount_usd: float
    proposal_id: Optional[str] = None
    description: Optional[str] = "Quarterly profit distribution"


# --- Proposals ---

@router.post("/proposals")
def create_proposal(proposal: ProposalCreate, db: Session = Depends(get_db_dep)):
    """Create a new governance proposal."""
    user = db.query(models.User).filter(models.User.id == proposal.author_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Minimum reputation to propose
    if (user.reputation_score or 0) < 50:
        raise HTTPException(status_code=403, detail="Need 50+ reputation to propose")

    new_proposal = models.Proposal(
        id=str(uuid4()),
        author_id=user.id,
        title=proposal.title,
        description=proposal.description,
        end_date=datetime.now() + timedelta(days=proposal.duration_days),
        status="active",
    )
    db.add(new_proposal)
    db.commit()

    return {
        "id": new_proposal.id,
        "status": "created",
        "end_date": new_proposal.end_date.isoformat(),
    }


@router.get("/proposals")
def get_proposals(status: str = "active", db: Session = Depends(get_db_dep)):
    """List active proposals."""
    proposals = db.query(models.Proposal).filter(models.Proposal.status == status).all()

    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "author_id": p.author_id,
            "yes_votes": round(p.yes_votes, 2),
            "no_votes": round(p.no_votes, 2),
            "status": p.status,
            "end_date": p.end_date.isoformat(),
        }
        for p in proposals
    ]


@router.post("/proposals/tally")
def tally_proposals(db: Session = Depends(get_db_dep)):
    """Check for expired proposals and tally results."""
    now = datetime.now()
    expired = (
        db.query(models.Proposal)
        .filter(models.Proposal.status == "active")
        .filter(models.Proposal.end_date <= now)
        .all()
    )

    tallied_count = 0
    for prop in expired:
        if prop.yes_votes > prop.no_votes:
            prop.status = "passed"
        else:
            prop.status = "rejected"
        tallied_count += 1

    db.commit()
    return {"status": "success", "tallied": tallied_count}


# --- Voting (reputation + stake weighted) ---

@router.post("/vote")
def vote_on_proposal(req: VoteRequest, db: Session = Depends(get_db_dep)):
    """Vote on a proposal. Weight = reputation + staked tokens."""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prop = (
        db.query(models.Proposal).filter(models.Proposal.id == req.proposal_id).first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if prop.status != "active":
        raise HTTPException(status_code=400, detail="Proposal is not active")

    # Check if already voted
    existing = (
        db.query(models.Vote)
        .filter(models.Vote.user_id == req.user_id)
        .filter(models.Vote.proposal_id == req.proposal_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already voted")

    # Calculate weight: base (1) + reputation bonus + staking bonus
    reputation_bonus = (user.reputation_score or 0) / 100.0
    
    # Staking bonus: 1 NEST staked = 0.01 extra vote weight
    total_staked = (
        db.query(func.sum(models.TokenStake.amount))
        .filter(models.TokenStake.user_id == req.user_id)
        .filter(models.TokenStake.is_active == True)
        .scalar() or 0
    )
    stake_bonus = total_staked * 0.01

    weight = 1.0 + reputation_bonus + stake_bonus

    vote = models.Vote(
        id=str(uuid4()),
        proposal_id=req.proposal_id,
        user_id=req.user_id,
        vote_type=req.vote,
        weight=weight,
    )

    if req.vote == "yes":
        prop.yes_votes += weight
    else:
        prop.no_votes += weight

    db.add(vote)
    db.commit()

    return {
        "status": "voted",
        "weight": round(weight, 4),
        "weight_breakdown": {
            "base": 1.0,
            "reputation_bonus": round(reputation_bonus, 4),
            "stake_bonus": round(stake_bonus, 4),
            "total_staked_nest": round(total_staked, 2),
        },
        "current_tally": {"yes": prop.yes_votes, "no": prop.no_votes},
    }


# --- Token Staking ---

@router.post("/stake")
def stake_tokens(req: StakeRequest, db: Session = Depends(get_db_dep)):
    """Stake NEST tokens for governance power and profit sharing eligibility."""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Stake amount must be positive")

    stake = models.TokenStake(
        id=str(uuid4()),
        user_id=req.user_id,
        amount=req.amount,
        is_active=True,
    )
    db.add(stake)

    # Reputation boost for staking
    user.reputation_score = (user.reputation_score or 0) + int(req.amount * 0.5)
    db.commit()

    # Get total staked
    total = (
        db.query(func.sum(models.TokenStake.amount))
        .filter(models.TokenStake.user_id == req.user_id)
        .filter(models.TokenStake.is_active == True)
        .scalar() or 0
    )

    return {
        "status": "staked",
        "stake_id": stake.id,
        "amount_staked": req.amount,
        "total_staked_nest": round(total, 2),
        "governance_weight_bonus": round(total * 0.01, 4),
        "message": f"Staked {req.amount} NEST tokens. Your governance weight increased.",
    }


@router.post("/unstake")
def unstake_tokens(req: UnstakeRequest, db: Session = Depends(get_db_dep)):
    """Unstake NEST tokens (7-day cooldown)."""
    stake = (
        db.query(models.TokenStake)
        .filter(models.TokenStake.id == req.stake_id)
        .filter(models.TokenStake.user_id == req.user_id)
        .filter(models.TokenStake.is_active == True)
        .first()
    )
    if not stake:
        raise HTTPException(status_code=404, detail="Active stake not found")

    stake.is_active = False
    stake.unstaked_at = datetime.now()
    db.commit()

    return {
        "status": "unstaked",
        "stake_id": stake.id,
        "amount_returned": stake.amount,
        "cooldown": "7 days",
        "message": f"Unstaked {stake.amount} NEST. Tokens available after 7-day cooldown.",
    }


@router.get("/stakes/{user_id}")
def get_user_stakes(user_id: str, db: Session = Depends(get_db_dep)):
    """Get all stakes for a user."""
    stakes = (
        db.query(models.TokenStake)
        .filter(models.TokenStake.user_id == user_id)
        .order_by(models.TokenStake.staked_at.desc())
        .all()
    )

    active = [s for s in stakes if s.is_active]
    total_active = sum(s.amount for s in active)

    return {
        "user_id": user_id,
        "total_staked_nest": round(total_active, 2),
        "governance_weight_bonus": round(total_active * 0.01, 4),
        "active_stakes": [
            {
                "stake_id": s.id,
                "amount": s.amount,
                "staked_at": s.staked_at.isoformat() if s.staked_at else None,
            }
            for s in active
        ],
        "history": [
            {
                "stake_id": s.id,
                "amount": s.amount,
                "is_active": s.is_active,
                "staked_at": s.staked_at.isoformat() if s.staked_at else None,
                "unstaked_at": s.unstaked_at.isoformat() if s.unstaked_at else None,
            }
            for s in stakes
        ],
    }


# --- Treasury ---

@router.get("/treasury")
def get_treasury(db: Session = Depends(get_db_dep)):
    """Get community treasury status — live balance from revenue + allocations."""
    # Revenue: 1% of all bookings
    total_listing_bookings = (
        db.query(func.sum(models.Booking.total_price_usd)).scalar() or 0
    )
    total_exp_bookings = (
        db.query(func.sum(models.ExperienceBooking.total_price_usd)).scalar() or 0
    )
    total_revenue = total_listing_bookings + total_exp_bookings
    treasury_inflow = total_revenue * 0.01

    # Outflow: sum of all treasury allocations
    treasury_outflow = (
        db.query(func.sum(models.TreasuryAllocation.amount_usd)).scalar() or 0
    )

    balance = treasury_inflow - treasury_outflow

    # Total staked NEST
    total_staked = (
        db.query(func.sum(models.TokenStake.amount))
        .filter(models.TokenStake.is_active == True)
        .scalar() or 0
    )

    # Recent allocations
    recent = (
        db.query(models.TreasuryAllocation)
        .order_by(models.TreasuryAllocation.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "balance_usd": round(balance, 2),
        "total_inflow_usd": round(treasury_inflow, 2),
        "total_outflow_usd": round(treasury_outflow, 2),
        "total_platform_revenue_usd": round(total_revenue, 2),
        "token_symbol": "NEST",
        "total_staked_nest": round(total_staked, 2),
        "staker_count": db.query(models.TokenStake).filter(models.TokenStake.is_active == True).distinct(models.TokenStake.user_id).count(),
        "recent_allocations": [
            {
                "id": a.id,
                "type": a.allocation_type,
                "amount_usd": a.amount_usd,
                "description": a.description,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in recent
        ],
    }


# --- Profit Sharing ---

@router.post("/treasury/distribute")
def distribute_profits(req: ProfitShareRequest, db: Session = Depends(get_db_dep)):
    """
    Distribute treasury funds proportionally to all active stakers.
    Each staker receives share = (their_stake / total_staked) * distribution_amount.
    """
    if req.total_amount_usd <= 0:
        raise HTTPException(status_code=400, detail="Distribution amount must be positive")

    # Get all active stakers with their totals
    staker_totals = (
        db.query(
            models.TokenStake.user_id,
            func.sum(models.TokenStake.amount).label("total_staked"),
        )
        .filter(models.TokenStake.is_active == True)
        .group_by(models.TokenStake.user_id)
        .all()
    )

    if not staker_totals:
        raise HTTPException(status_code=400, detail="No active stakers to distribute to")

    total_staked = sum(s.total_staked for s in staker_totals)
    if total_staked <= 0:
        raise HTTPException(status_code=400, detail="Total staked is zero")

    # Distribute proportionally
    distributions = []
    for staker in staker_totals:
        share_pct = staker.total_staked / total_staked
        share_usd = req.total_amount_usd * share_pct

        allocation = models.TreasuryAllocation(
            id=str(uuid4()),
            allocation_type="profit_share",
            amount_usd=share_usd,
            recipient_id=staker.user_id,
            proposal_id=req.proposal_id,
            description=req.description,
        )
        db.add(allocation)

        distributions.append({
            "user_id": staker.user_id,
            "staked_nest": round(staker.total_staked, 2),
            "share_pct": round(share_pct * 100, 2),
            "payout_usd": round(share_usd, 2),
        })

    db.commit()

    return {
        "status": "distributed",
        "total_distributed_usd": round(req.total_amount_usd, 2),
        "stakers_paid": len(distributions),
        "distributions": distributions,
    }


@router.get("/treasury/allocations")
def get_treasury_allocations(
    allocation_type: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db_dep),
):
    """Get treasury allocation history."""
    query = db.query(models.TreasuryAllocation)
    if allocation_type:
        query = query.filter(models.TreasuryAllocation.allocation_type == allocation_type)

    allocations = (
        query.order_by(models.TreasuryAllocation.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": a.id,
            "type": a.allocation_type,
            "amount_usd": a.amount_usd,
            "recipient_id": a.recipient_id,
            "proposal_id": a.proposal_id,
            "description": a.description,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in allocations
    ]
