"""Services router - API endpoints for hub services."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend import models, schemas

router = APIRouter(prefix="/api/v1/services", tags=["Services"])


@router.get("/", response_model=List[schemas.ServiceResponse])
def get_services(
    hub_id: str = None,
    db: Session = Depends(get_db)
):
    """Get all services, optionally filtered by hub."""
    query = db.query(models.Service)
    if hub_id:
        query = query.filter(models.Service.hub_id == hub_id)
    return query.all()


@router.get("/{service_id}", response_model=schemas.ServiceResponse)
def get_service(service_id: str, db: Session = Depends(get_db)):
    """Get a specific service by ID."""
    service = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not service:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Service", identifier=service_id)
    return service
