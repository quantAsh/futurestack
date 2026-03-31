"""
Reviews Router - CRUD for listing reviews.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from backend import models, schemas
from backend.database import get_db

router = APIRouter()


def get_db_dep():
    yield from get_db()


@router.get("/listing/{listing_id}", response_model=schemas.PaginatedResponse[schemas.Review])
def get_listing_reviews(
    listing_id: str, page: int = 1, size: int = 20, db: Session = Depends(get_db_dep)
):
    """Get all reviews for a listing with pagination."""
    query = (
        db.query(models.Review)
        .filter(models.Review.listing_id == listing_id)
    )
    
    offset = (page - 1) * size
    total = query.count()
    items = query.offset(offset).limit(size).all()
    pages = (total + size - 1) // size

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.get("/user/{user_id}", response_model=schemas.PaginatedResponse[schemas.Review])
def get_user_reviews(
    user_id: str, page: int = 1, size: int = 20, db: Session = Depends(get_db_dep)
):
    """Get all reviews by a user with pagination."""
    query = db.query(models.Review).filter(models.Review.author_id == user_id)
    
    offset = (page - 1) * size
    total = query.count()
    items = query.offset(offset).limit(size).all()
    pages = (total + size - 1) // size

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.post("/", response_model=schemas.Review, status_code=201)
def create_review(review: schemas.ReviewCreate, db: Session = Depends(get_db_dep)):
    """Create a new review."""
    from uuid import uuid4

    # Verify listing exists
    listing = (
        db.query(models.Listing).filter(models.Listing.id == review.listing_id).first()
    )
    if not listing:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Listing", identifier=review.listing_id)

    # Check for duplicate review
    existing = (
        db.query(models.Review)
        .filter(models.Review.listing_id == review.listing_id)
        .filter(models.Review.author_id == review.author_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="User already reviewed this listing"
        )

    db_review = models.Review(
        id=str(uuid4()),
        listing_id=review.listing_id,
        author_id=review.author_id,
        rating=review.rating,
        comment=review.comment,
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review


@router.get("/stats/{listing_id}")
def get_review_stats(listing_id: str, db: Session = Depends(get_db_dep)):
    """Get review statistics for a listing."""
    reviews = (
        db.query(models.Review).filter(models.Review.listing_id == listing_id).all()
    )

    if not reviews:
        return {"listing_id": listing_id, "count": 0, "average": 0}

    total = sum(r.rating for r in reviews)
    return {
        "listing_id": listing_id,
        "count": len(reviews),
        "average": round(total / len(reviews), 1),
    }
