from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from backend import models, schemas, database
from uuid import uuid4

router = APIRouter()


def get_db():
    yield from database.get_db()


@router.get("/", response_model=schemas.PaginatedResponse[schemas.Hub])
def read_hubs(page: int = 1, size: int = 20, db: Session = Depends(get_db)):
    offset = (page - 1) * size
    total = db.query(models.Hub).count()
    items = db.query(models.Hub).offset(offset).limit(size).all()
    pages = (total + size - 1) // size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.post("/", response_model=schemas.Hub, status_code=201)
def create_hub(hub: schemas.HubCreate, db: Session = Depends(get_db)):
    db_hub = models.Hub(
        id=str(uuid4()),
        name=hub.name,
        mission=hub.mission,
        type=hub.type,
        logo=hub.logo,
        charter=hub.charter,
        lat=hub.lat,
        lng=hub.lng,
        sustainability_score=hub.sustainability_score,
        member_ids=hub.member_ids,
        amenity_ids=hub.amenity_ids,
        listing_ids=hub.listing_ids,
        tags=hub.tags,
    )
    db.add(db_hub)
    db.commit()
    db.refresh(db_hub)
    return db_hub


@router.get("/{hub_id}", response_model=schemas.Hub)
def read_hub(hub_id: str, db: Session = Depends(get_db)):
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if hub is None:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Hub", identifier=hub_id)
    return hub


@router.put("/{hub_id}", response_model=schemas.Hub)
def update_hub(hub_id: str, hub: schemas.HubCreate, db: Session = Depends(get_db)):
    db_hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if db_hub is None:
        raise HTTPException(status_code=404, detail="Hub not found")

    # Update all fields
    db_hub.name = hub.name
    db_hub.mission = hub.mission
    db_hub.type = hub.type
    db_hub.logo = hub.logo
    db_hub.charter = hub.charter
    db_hub.lat = hub.lat
    db_hub.lng = hub.lng
    db_hub.sustainability_score = hub.sustainability_score
    db_hub.member_ids = hub.member_ids
    db_hub.amenity_ids = hub.amenity_ids
    db_hub.listing_ids = hub.listing_ids
    db_hub.tags = hub.tags

    db.commit()
    db.refresh(db_hub)
    return db_hub

# --- Sub-resources Stubs (Proposals & Resources) ---

class ProposalCreate(BaseModel):
    title: str
    description: str
    proposerId: str

class VoteCreate(BaseModel):
    voteType: str

class ResourceBookingCreate(BaseModel):
    hubId: str
    resourceId: str
    userId: str
    startTime: str
    endTime: str
    cost: float

from pydantic import BaseModel

@router.post("/{hub_id}/proposals", status_code=201)
def create_proposal(hub_id: str, proposal: ProposalCreate, db: Session = Depends(get_db)):
    # Stub: In real imp, would save to specific table
    # For now, just return valid Hub to satisfy frontend
    db_hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not db_hub:
        raise HTTPException(status_code=404, detail="Hub not found")
    
    # We don't actually modify DB here in this stub phase, but return the hub
    return db_hub

@router.post("/{hub_id}/proposals/{proposal_id}/vote")
def vote_proposal(hub_id: str, proposal_id: str, vote: VoteCreate, db: Session = Depends(get_db)):
    db_hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not db_hub:
        raise HTTPException(status_code=404, detail="Hub not found")
    return db_hub

@router.post("/{hub_id}/resources/{resource_id}/book")
def book_resource(hub_id: str, resource_id: str, booking: dict, db: Session = Depends(get_db)):
    # booking: dict because the frontend sends a complex object
    # Return structure matching frontend expectation: { updatedUser, updatedHub }
    db_hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not db_hub:
        raise HTTPException(status_code=404, detail="Hub not found")
    
    # We need to return user too. 
    # Frontend expects: { updatedUser: User, updatedHub: Hub }
    # To avoid circular imports or complexity, we just mock the response structure with real data
    # THIS IS A PARTIAL STUB.
    
    from backend.routers.users import get_current_user # simplistic usage
    # We probably shouldn't rely on auth dep inside function, but for stub it's fine.
    
    # Just return the hub as "updatedHub" and an empty/mock user as "updatedUser" is risky.
    # But since frontend mostly refreshes, we might get away with returning the hub.
    # Actually, frontend apiService.ts says: return { updatedUser: normalizeUser(data.updatedUser), updatedHub: ... }
    # So we MUST return that structure.
    
    return {
        "updatedHub": db_hub,
        "updatedUser": {
            "id": booking.get("userId", "stub"),
            "name": "Stub User",
            "email": "stub@example.com",
            # Add minimal fields to satisfy frontend User type
            "reputationXP": {},
            "resourceCredits": 0
        }
    }
