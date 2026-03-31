"""
Services Router - Marketplace services offered by community members.
Includes skills, consulting, and local services.
"""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models
from backend.middleware.auth import get_current_user

router = APIRouter()


# ============================================
# SCHEMAS
# ============================================

class ServiceCreate(BaseModel):
    title: str
    description: str
    category: str = "consulting"  # consulting, design, development, local, wellness
    price_usd: float
    price_type: str = "hourly"  # hourly, fixed, negotiable
    availability: Optional[str] = None
    location: Optional[str] = None
    remote: bool = True
    tags: Optional[List[str]] = None


class ServiceResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    category: str
    price_usd: float
    price_type: str
    availability: Optional[str]
    location: Optional[str]
    remote: bool
    tags: List[str]
    rating: float
    review_count: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================
# ENDPOINTS
# ============================================

@router.get("/services", response_model=List[ServiceResponse])
def list_services(
    category: Optional[str] = None,
    remote_only: bool = False,
    min_rating: float = Query(default=0, ge=0, le=5),
    location: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """List available services with filters."""
    query = db.query(models.MarketplaceService).filter(models.MarketplaceService.is_active == True)
    
    if category:
        query = query.filter(models.MarketplaceService.category == category)
    if remote_only:
        query = query.filter(models.MarketplaceService.remote == True)
    if min_rating > 0:
        query = query.filter(models.MarketplaceService.rating >= min_rating)
    if location:
        query = query.filter(models.MarketplaceService.location.ilike(f"%{location}%"))
    
    services = query.order_by(models.MarketplaceService.rating.desc()).limit(limit).all()
    return services


@router.get("/services/categories")
def get_service_categories(db: Session = Depends(get_db)):
    """Get available service categories with counts."""
    categories = db.query(
        models.MarketplaceService.category,
    ).filter(models.MarketplaceService.is_active == True).distinct().all()
    
    result = []
    for (cat,) in categories:
        count = db.query(models.MarketplaceService).filter(
            models.MarketplaceService.category == cat,
            models.MarketplaceService.is_active == True,
        ).count()
        result.append({"category": cat, "count": count})
    
    return result


@router.get("/services/{service_id}", response_model=ServiceResponse)
def get_service(service_id: str, db: Session = Depends(get_db)):
    """Get a specific service by ID."""
    service = db.query(models.MarketplaceService).filter(models.MarketplaceService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.post("/services", response_model=ServiceResponse)
def create_service(
    service: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new service listing."""
    db_service = models.MarketplaceService(
        id=str(uuid4()),
        user_id=current_user.id,
        title=service.title,
        description=service.description,
        category=service.category,
        price_usd=service.price_usd,
        price_type=service.price_type,
        availability=service.availability,
        location=service.location,
        remote=service.remote,
        tags=service.tags or [],
        rating=0.0,
        review_count=0,
        is_active=True,
    )
    
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    
    return db_service


@router.get("/services/my")
def get_my_services(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get services created by the current user."""
    services = db.query(models.MarketplaceService).filter(
        models.MarketplaceService.user_id == current_user.id
    ).all()
    return services


@router.put("/services/{service_id}")
def update_service(
    service_id: str,
    updates: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update a service listing."""
    service = db.query(models.MarketplaceService).filter(models.MarketplaceService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if service.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(service, field, value)
    
    db.commit()
    db.refresh(service)
    return service


@router.delete("/services/{service_id}")
def delete_service(
    service_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a service listing."""
    service = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if service.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(service)
    db.commit()
    return {"status": "deleted"}
