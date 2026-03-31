"""
Micro-Investments Router - Fractional ownership, booking discounts, and buyback pool.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
from datetime import datetime

from backend import models
from backend.database import get_db
from sqlalchemy import func

router = APIRouter()


def get_db_dep():
    yield from get_db()


# --- Schemas ---

class InvestmentRequest(BaseModel):
    user_id: str
    hub_id: str
    amount_usd: float


class InvestmentResponse(BaseModel):
    investment_id: str
    hub_name: str
    shares: float
    amount_usd: float
    status: str


class BuybackRequest(BaseModel):
    user_id: str
    hub_id: str
    shares: float


class HubFinancialsUpdate(BaseModel):
    total_valuation_usd: Optional[float] = None
    total_shares: Optional[float] = None
    available_shares: Optional[float] = None
    annual_yield_pct: Optional[float] = None
    investor_discount_pct: Optional[float] = None


# --- Investment Opportunities (real valuations from HubFinancials) ---

@router.get("/opportunities")
def get_investment_opportunities(db: Session = Depends(get_db_dep)):
    """List hubs available for fractional investment with real Financial data."""
    hubs = db.query(models.Hub).all()
    opportunities = []

    for hub in hubs:
        # Try to get real financials, fall back to defaults
        fin = (
            db.query(models.HubFinancials)
            .filter(models.HubFinancials.hub_id == hub.id)
            .first()
        )

        if fin:
            price_per_share = fin.total_valuation_usd / fin.total_shares if fin.total_shares > 0 else 1000
            opportunities.append({
                "hub_id": hub.id,
                "hub_name": hub.name,
                "total_valuation_usd": fin.total_valuation_usd,
                "total_shares": fin.total_shares,
                "available_shares": fin.available_shares,
                "price_per_share_usd": round(price_per_share, 2),
                "annual_yield_pct": fin.annual_yield_pct,
                "investor_discount_pct": fin.investor_discount_pct,
                "last_appraisal": fin.last_appraisal.isoformat() if fin.last_appraisal else None,
            })
        else:
            # Default for hubs without financials configured
            opportunities.append({
                "hub_id": hub.id,
                "hub_name": hub.name,
                "total_valuation_usd": 1000000,
                "total_shares": 1000,
                "available_shares": 500,
                "price_per_share_usd": 1000.0,
                "annual_yield_pct": 10.0,
                "investor_discount_pct": 5.0,
                "last_appraisal": None,
            })

    return opportunities


# --- Invest in Hub ---

@router.post("/invest", response_model=InvestmentResponse)
def invest_in_hub(request: InvestmentRequest, db: Session = Depends(get_db_dep)):
    """Purchase fractional shares in a hub."""
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hub = db.query(models.Hub).filter(models.Hub.id == request.hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")

    if request.amount_usd <= 0:
        raise HTTPException(status_code=400, detail="Investment amount must be positive")

    # Get real financials or defaults
    fin = (
        db.query(models.HubFinancials)
        .filter(models.HubFinancials.hub_id == request.hub_id)
        .first()
    )

    price_per_share = 1000.0  # default
    if fin and fin.total_shares > 0:
        price_per_share = fin.total_valuation_usd / fin.total_shares

    shares = request.amount_usd / price_per_share

    # Check available shares
    if fin and shares > fin.available_shares:
        raise HTTPException(
            status_code=400,
            detail=f"Only {fin.available_shares:.2f} shares available. Requested {shares:.2f}.",
        )

    # Create investment record
    investment = models.HubInvestment(
        id=str(uuid4()),
        hub_id=request.hub_id,
        user_id=request.user_id,
        shares=shares,
        amount_usd=request.amount_usd,
    )
    db.add(investment)

    # Deduct available shares
    if fin:
        fin.available_shares -= shares

    # Reputation boost for investing
    user.reputation_score = (user.reputation_score or 0) + int(shares * 10)

    db.commit()

    return {
        "investment_id": investment.id,
        "hub_name": hub.name,
        "shares": round(shares, 4),
        "amount_usd": request.amount_usd,
        "status": "confirmed",
    }


# --- Portfolio ---

@router.get("/portfolio/{user_id}")
def get_user_portfolio(user_id: str, db: Session = Depends(get_db_dep)):
    """Get all fractional investments for a user with current valuations."""
    investments = (
        db.query(models.HubInvestment)
        .filter(models.HubInvestment.user_id == user_id)
        .all()
    )

    portfolio = []
    total_invested = 0
    total_current_value = 0

    for inv in investments:
        hub = db.query(models.Hub).filter(models.Hub.id == inv.hub_id).first()
        fin = (
            db.query(models.HubFinancials)
            .filter(models.HubFinancials.hub_id == inv.hub_id)
            .first()
        )

        current_pps = 1000.0
        if fin and fin.total_shares > 0:
            current_pps = fin.total_valuation_usd / fin.total_shares

        current_value = inv.shares * current_pps
        gain_loss = current_value - inv.amount_usd

        portfolio.append({
            "hub_name": hub.name if hub else "Unknown Hub",
            "hub_id": inv.hub_id,
            "shares": round(inv.shares, 4),
            "purchase_amount_usd": inv.amount_usd,
            "current_value_usd": round(current_value, 2),
            "gain_loss_usd": round(gain_loss, 2),
            "date": inv.created_at.isoformat() if inv.created_at else None,
        })
        total_invested += inv.amount_usd
        total_current_value += current_value

    return {
        "user_id": user_id,
        "total_invested_usd": round(total_invested, 2),
        "total_current_value_usd": round(total_current_value, 2),
        "total_gain_loss_usd": round(total_current_value - total_invested, 2),
        "investments": portfolio,
    }


# --- Investor Booking Discount ---

@router.get("/discount/{user_id}/{hub_id}")
def get_investor_discount(user_id: str, hub_id: str, db: Session = Depends(get_db_dep)):
    """
    Check if a user qualifies for an investor booking discount at a hub.
    Token holders get a percentage off bookings at hubs they've invested in.
    """
    # Check if user has invested in this hub
    user_shares = (
        db.query(func.sum(models.HubInvestment.shares))
        .filter(models.HubInvestment.user_id == user_id)
        .filter(models.HubInvestment.hub_id == hub_id)
        .scalar() or 0
    )

    if user_shares <= 0:
        return {
            "eligible": False,
            "discount_pct": 0,
            "message": "Invest in this hub to unlock booking discounts.",
        }

    # Get discount rate from hub financials
    fin = (
        db.query(models.HubFinancials)
        .filter(models.HubFinancials.hub_id == hub_id)
        .first()
    )

    base_discount = fin.investor_discount_pct if fin else 5.0

    # Tiered discount: more shares = higher discount (capped at 2x base)
    tier_multiplier = min(2.0, 1.0 + (user_shares / 10.0))
    final_discount = base_discount * tier_multiplier

    return {
        "eligible": True,
        "shares_held": round(user_shares, 4),
        "base_discount_pct": base_discount,
        "tier_multiplier": round(tier_multiplier, 2),
        "final_discount_pct": round(final_discount, 2),
        "message": f"You get {final_discount:.1f}% off bookings at this hub!",
    }


# --- Buyback Pool (Exit Liquidity) ---

@router.post("/buyback/request")
def request_buyback(req: BuybackRequest, db: Session = Depends(get_db_dep)):
    """
    Request to sell shares back to the DAO-managed buyback pool.
    Shares are bought at 90% of current market price (10% spread).
    """
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check user actually owns enough shares
    user_shares = (
        db.query(func.sum(models.HubInvestment.shares))
        .filter(models.HubInvestment.user_id == req.user_id)
        .filter(models.HubInvestment.hub_id == req.hub_id)
        .scalar() or 0
    )

    if req.shares > user_shares:
        raise HTTPException(
            status_code=400,
            detail=f"You only own {user_shares:.4f} shares. Cannot sell {req.shares:.4f}.",
        )

    # Get current price
    fin = (
        db.query(models.HubFinancials)
        .filter(models.HubFinancials.hub_id == req.hub_id)
        .first()
    )

    price_per_share = 1000.0
    if fin and fin.total_shares > 0:
        price_per_share = fin.total_valuation_usd / fin.total_shares

    # Buyback at 90% of market (10% spread for the pool)
    buyback_price = price_per_share * 0.90
    total_payout = buyback_price * req.shares

    # Create buyback order
    order = models.BuybackOrder(
        id=str(uuid4()),
        user_id=req.user_id,
        hub_id=req.hub_id,
        shares=req.shares,
        price_per_share_usd=buyback_price,
        total_usd=total_payout,
        status="completed",
        completed_at=datetime.now(),
    )
    db.add(order)

    # Return shares to available pool
    if fin:
        fin.available_shares += req.shares

    # Create treasury allocation for the buyback expense
    allocation = models.TreasuryAllocation(
        id=str(uuid4()),
        allocation_type="buyback",
        amount_usd=total_payout,
        recipient_id=req.user_id,
        description=f"Buyback of {req.shares:.4f} shares in hub {req.hub_id}",
    )
    db.add(allocation)

    db.commit()

    return {
        "status": "completed",
        "order_id": order.id,
        "shares_sold": round(req.shares, 4),
        "market_price_usd": round(price_per_share, 2),
        "buyback_price_usd": round(buyback_price, 2),
        "total_payout_usd": round(total_payout, 2),
        "spread": "10%",
        "message": f"Sold {req.shares:.4f} shares for ${total_payout:.2f}. Funds will arrive in 2-3 business days.",
    }


@router.get("/buyback/history/{user_id}")
def get_buyback_history(user_id: str, db: Session = Depends(get_db_dep)):
    """Get buyback order history for a user."""
    orders = (
        db.query(models.BuybackOrder)
        .filter(models.BuybackOrder.user_id == user_id)
        .order_by(models.BuybackOrder.created_at.desc())
        .all()
    )

    return [
        {
            "order_id": o.id,
            "hub_id": o.hub_id,
            "shares": round(o.shares, 4),
            "price_per_share_usd": round(o.price_per_share_usd, 2),
            "total_usd": round(o.total_usd, 2),
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


# --- Admin: Hub Financials Management ---

@router.post("/hub-financials/{hub_id}")
def upsert_hub_financials(
    hub_id: str,
    update: HubFinancialsUpdate,
    db: Session = Depends(get_db_dep),
):
    """Create or update hub financial data (admin use)."""
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")

    fin = (
        db.query(models.HubFinancials)
        .filter(models.HubFinancials.hub_id == hub_id)
        .first()
    )

    if not fin:
        fin = models.HubFinancials(
            id=str(uuid4()),
            hub_id=hub_id,
        )
        db.add(fin)

    if update.total_valuation_usd is not None:
        fin.total_valuation_usd = update.total_valuation_usd
    if update.total_shares is not None:
        fin.total_shares = update.total_shares
    if update.available_shares is not None:
        fin.available_shares = update.available_shares
    if update.annual_yield_pct is not None:
        fin.annual_yield_pct = update.annual_yield_pct
    if update.investor_discount_pct is not None:
        fin.investor_discount_pct = update.investor_discount_pct

    fin.last_appraisal = datetime.now()
    db.commit()

    return {
        "status": "updated",
        "hub_id": hub_id,
        "hub_name": hub.name,
        "valuation_usd": fin.total_valuation_usd,
        "price_per_share_usd": round(fin.total_valuation_usd / fin.total_shares, 2) if fin.total_shares > 0 else 0,
        "available_shares": fin.available_shares,
    }
