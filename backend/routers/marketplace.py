"""
Solution Marketplace Router — vendor listings, search, reviews, and verification.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4

from backend.database import get_db
from backend.models_civic import SolutionListing, InfraVertical

router = APIRouter()


def get_db_dep():
    yield from get_db()


# --- Schemas ---

class SolutionCreate(BaseModel):
    vendor_id: str
    vertical: str
    name: str
    description: Optional[str] = None
    solution_type: str = "product"  # product, service, consulting, training
    category: Optional[str] = None
    price_usd: Optional[float] = None
    price_model: str = "fixed"  # fixed, per_unit, subscription, quote_required
    specifications: Optional[dict] = {}
    certifications: Optional[list] = []
    regions_available: Optional[list] = []
    image_url: Optional[str] = None
    documentation_url: Optional[str] = None


class SolutionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_usd: Optional[float] = None
    price_model: Optional[str] = None
    specifications: Optional[dict] = None
    certifications: Optional[list] = None
    regions_available: Optional[list] = None
    is_active: Optional[bool] = None


class SolutionReview(BaseModel):
    rating: float  # 1-5
    comment: Optional[str] = None


# --- CRUD ---

@router.post("/solutions")
def create_solution(solution: SolutionCreate, db: Session = Depends(get_db_dep)):
    """List a new infrastructure solution in the marketplace."""
    valid_verticals = [v.value for v in InfraVertical]
    if solution.vertical not in valid_verticals:
        raise HTTPException(status_code=400, detail=f"Invalid vertical. Must be one of: {valid_verticals}")

    listing = SolutionListing(
        id=str(uuid4()),
        vendor_id=solution.vendor_id,
        vertical=solution.vertical,
        name=solution.name,
        description=solution.description,
        solution_type=solution.solution_type,
        category=solution.category,
        price_usd=solution.price_usd,
        price_model=solution.price_model,
        specifications=solution.specifications,
        certifications=solution.certifications,
        regions_available=solution.regions_available,
        image_url=solution.image_url,
        documentation_url=solution.documentation_url,
    )
    db.add(listing)
    db.commit()

    return {
        "id": listing.id,
        "name": listing.name,
        "vertical": listing.vertical,
        "status": "listed",
        "message": f"Solution '{listing.name}' listed in {listing.vertical} marketplace.",
    }


@router.get("/solutions")
def search_solutions(
    vertical: Optional[str] = None,
    solution_type: Optional[str] = None,
    category: Optional[str] = None,
    region: Optional[str] = None,
    max_price: Optional[float] = None,
    verified_only: bool = False,
    q: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db_dep),
):
    """Search the solution marketplace with filters."""
    query = db.query(SolutionListing).filter(SolutionListing.is_active == True)

    if vertical:
        query = query.filter(SolutionListing.vertical == vertical)
    if solution_type:
        query = query.filter(SolutionListing.solution_type == solution_type)
    if category:
        query = query.filter(SolutionListing.category == category)
    if max_price:
        query = query.filter(SolutionListing.price_usd <= max_price)
    if verified_only:
        query = query.filter(SolutionListing.verified == True)
    if q:
        query = query.filter(
            SolutionListing.name.ilike(f"%{q}%") |
            SolutionListing.description.ilike(f"%{q}%")
        )

    total = query.count()
    solutions = query.order_by(SolutionListing.impact_rating.desc().nullslast()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "solutions": [
            {
                "id": s.id,
                "name": s.name,
                "vertical": s.vertical,
                "solution_type": s.solution_type,
                "category": s.category,
                "price_usd": s.price_usd,
                "price_model": s.price_model,
                "impact_rating": s.impact_rating,
                "review_count": s.review_count,
                "verified": s.verified,
                "vendor_id": s.vendor_id,
                "image_url": s.image_url,
                "regions_available": s.regions_available,
            }
            for s in solutions
        ],
    }


@router.get("/solutions/{solution_id}")
def get_solution(solution_id: str, db: Session = Depends(get_db_dep)):
    """Get detailed solution info."""
    solution = db.query(SolutionListing).filter(SolutionListing.id == solution_id).first()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    return {
        "id": solution.id,
        "name": solution.name,
        "description": solution.description,
        "vertical": solution.vertical,
        "solution_type": solution.solution_type,
        "category": solution.category,
        "price_usd": solution.price_usd,
        "price_model": solution.price_model,
        "specifications": solution.specifications,
        "certifications": solution.certifications,
        "regions_available": solution.regions_available,
        "impact_rating": solution.impact_rating,
        "review_count": solution.review_count,
        "verified": solution.verified,
        "vendor_id": solution.vendor_id,
        "image_url": solution.image_url,
        "documentation_url": solution.documentation_url,
        "created_at": solution.created_at.isoformat() if solution.created_at else None,
    }


@router.put("/solutions/{solution_id}")
def update_solution(solution_id: str, update: SolutionUpdate, db: Session = Depends(get_db_dep)):
    """Update a solution listing."""
    solution = db.query(SolutionListing).filter(SolutionListing.id == solution_id).first()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(solution, field, value)

    db.commit()
    return {"status": "updated", "solution_id": solution_id}


# --- Comparison ---

@router.post("/solutions/compare")
def compare_solutions(solution_ids: List[str], db: Session = Depends(get_db_dep)):
    """Side-by-side comparison of multiple solutions."""
    solutions = db.query(SolutionListing).filter(SolutionListing.id.in_(solution_ids)).all()

    if len(solutions) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 solutions to compare")

    return {
        "comparison": [
            {
                "id": s.id,
                "name": s.name,
                "vertical": s.vertical,
                "price_usd": s.price_usd,
                "price_model": s.price_model,
                "specifications": s.specifications,
                "certifications": s.certifications,
                "impact_rating": s.impact_rating,
                "verified": s.verified,
            }
            for s in solutions
        ],
    }


# --- Marketplace Stats ---

@router.get("/marketplace/stats")
def get_marketplace_stats(db: Session = Depends(get_db_dep)):
    """Get marketplace overview stats."""
    from sqlalchemy import func

    total_listings = db.query(SolutionListing).filter(SolutionListing.is_active == True).count()
    verified_count = db.query(SolutionListing).filter(SolutionListing.verified == True, SolutionListing.is_active == True).count()

    by_vertical = (
        db.query(SolutionListing.vertical, func.count(SolutionListing.id))
        .filter(SolutionListing.is_active == True)
        .group_by(SolutionListing.vertical)
        .all()
    )

    by_type = (
        db.query(SolutionListing.solution_type, func.count(SolutionListing.id))
        .filter(SolutionListing.is_active == True)
        .group_by(SolutionListing.solution_type)
        .all()
    )

    return {
        "total_listings": total_listings,
        "verified_vendors": verified_count,
        "by_vertical": {v: c for v, c in by_vertical},
        "by_type": {t: c for t, c in by_type},
    }
