"""
Neighborhoods Router - CRUD for neighborhoods.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from backend import models, schemas
from backend.database import get_db

router = APIRouter()


def get_db_dep():
    yield from get_db()


@router.get("/", response_model=schemas.PaginatedResponse[schemas.Neighborhood])
def get_neighborhoods(
    page: int = 1, size: int = 20, db: Session = Depends(get_db_dep)
):
    """Get all neighborhoods with pagination."""
    offset = (page - 1) * size
    total = db.query(models.Neighborhood).count()
    items = db.query(models.Neighborhood).offset(offset).limit(size).all()
    pages = (total + size - 1) // size

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.get("/{neighborhood_id}", response_model=schemas.Neighborhood)
def get_neighborhood(neighborhood_id: str, db: Session = Depends(get_db_dep)):
    """Get a specific neighborhood."""
    neighborhood = (
        db.query(models.Neighborhood)
        .filter(models.Neighborhood.id == neighborhood_id)
        .first()
    )
    if not neighborhood:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Neighborhood", identifier=neighborhood_id)
    return neighborhood


@router.post("/", response_model=schemas.Neighborhood, status_code=201)
def create_neighborhood(
    neighborhood: schemas.NeighborhoodCreate, db: Session = Depends(get_db_dep)
):
    """Create a new neighborhood."""
    from uuid import uuid4

    db_neighborhood = models.Neighborhood(id=str(uuid4()), **neighborhood.model_dump())
    db.add(db_neighborhood)
    db.commit()
    db.refresh(db_neighborhood)
    return db_neighborhood
