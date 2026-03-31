"""
Networks Router - Co-living Networks and Partnership Management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter()


def get_db_dep():
    yield from get_db()


# ============================================
# SCHEMAS
# ============================================

class NetworkCreate(BaseModel):
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    partnership_type: str = "affiliate"  # affiliate, partner, premium
    regions: Optional[List[str]] = None
    benefits: Optional[List[str]] = None


class NetworkResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    logo_url: Optional[str]
    website: Optional[str]
    partnership_type: str
    regions: Optional[List[str]]
    benefits: Optional[List[str]]
    hub_count: int
    is_active: bool


class NetworkMembershipCreate(BaseModel):
    network_id: str


# ============================================
# ENDPOINTS
# ============================================

@router.get("/", response_model=List[NetworkResponse])
def list_networks(
    partnership_type: Optional[str] = None,
    region: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db_dep)
):
    """List all co-living networks/partnerships."""
    query = db.query(models.CoLivingNetwork).filter(
        models.CoLivingNetwork.is_active == True
    )
    
    if partnership_type:
        query = query.filter(models.CoLivingNetwork.partnership_type == partnership_type)
    
    networks = query.offset(skip).limit(limit).all()
    
    result = []
    for n in networks:
        # Count hubs in this network
        hub_count = db.query(models.Hub).filter(
            models.Hub.network_id == n.id
        ).count() if hasattr(models.Hub, 'network_id') else 0
        
        result.append({
            "id": n.id,
            "name": n.name,
            "description": n.description,
            "logo_url": n.logo_url,
            "website": n.website,
            "partnership_type": n.partnership_type,
            "regions": n.regions,
            "benefits": n.benefits,
            "hub_count": hub_count,
            "is_active": n.is_active,
        })
    
    return result


@router.get("/{network_id}")
def get_network(network_id: str, db: Session = Depends(get_db_dep)):
    """Get a network's details with associated hubs."""
    network = db.query(models.CoLivingNetwork).filter(
        models.CoLivingNetwork.id == network_id
    ).first()
    
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Get hubs in this network
    hubs = []
    if hasattr(models.Hub, 'network_id'):
        hubs = db.query(models.Hub).filter(
            models.Hub.network_id == network_id
        ).all()
    
    return {
        "id": network.id,
        "name": network.name,
        "description": network.description,
        "logo_url": network.logo_url,
        "website": network.website,
        "partnership_type": network.partnership_type,
        "regions": network.regions,
        "benefits": network.benefits,
        "is_active": network.is_active,
        "hubs": [
            {
                "id": h.id,
                "name": h.name,
                "type": h.type,
                "mission": h.mission[:100] if h.mission else None,
            }
            for h in hubs
        ],
    }


@router.post("/", response_model=NetworkResponse)
def create_network(
    data: NetworkCreate,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new co-living network (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    network = models.CoLivingNetwork(
        id=str(uuid4()),
        name=data.name,
        description=data.description,
        logo_url=data.logo_url,
        website=data.website,
        partnership_type=data.partnership_type,
        regions=data.regions,
        benefits=data.benefits,
        is_active=True,
    )
    
    db.add(network)
    db.commit()
    db.refresh(network)
    
    return {
        **{c.name: getattr(network, c.name) for c in network.__table__.columns},
        "hub_count": 0,
    }


@router.put("/{network_id}", response_model=NetworkResponse)
def update_network(
    network_id: str,
    data: NetworkCreate,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Update a co-living network (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    network = db.query(models.CoLivingNetwork).filter(
        models.CoLivingNetwork.id == network_id
    ).first()
    
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
        
    network.name = data.name
    network.description = data.description
    network.logo_url = data.logo_url
    network.website = data.website
    network.partnership_type = data.partnership_type
    network.regions = data.regions
    network.benefits = data.benefits
    
    db.commit()
    db.refresh(network)
    
    # Recalculate hub count
    hub_count = db.query(models.Hub).filter(
        models.Hub.network_id == network.id
    ).count() if hasattr(models.Hub, 'network_id') else 0
    
    return {
        **{c.name: getattr(network, c.name) for c in network.__table__.columns},
        "hub_count": hub_count,
    }


@router.get("/my/memberships")
def get_my_network_memberships(
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Get networks the current user is a member of."""
    memberships = db.query(models.NetworkMembership).filter(
        models.NetworkMembership.user_id == current_user.id
    ).all()
    
    result = []
    for m in memberships:
        network = db.query(models.CoLivingNetwork).filter(
            models.CoLivingNetwork.id == m.network_id
        ).first()
        
        if network:
            result.append({
                "membership_id": m.id,
                "network_id": network.id,
                "network_name": network.name,
                "partnership_type": network.partnership_type,
                "joined_at": m.created_at.isoformat() if m.created_at else None,
                "benefits": network.benefits,
            })
    
    return {"memberships": result, "count": len(result)}


@router.post("/join/{network_id}")
def join_network(
    network_id: str,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Join a co-living network."""
    network = db.query(models.CoLivingNetwork).filter(
        models.CoLivingNetwork.id == network_id
    ).first()
    
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Check if already a member
    existing = db.query(models.NetworkMembership).filter(
        models.NetworkMembership.user_id == current_user.id,
        models.NetworkMembership.network_id == network_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already a member of this network")
    
    membership = models.NetworkMembership(
        id=str(uuid4()),
        user_id=current_user.id,
        network_id=network_id,
    )
    
    db.add(membership)
    db.commit()
    
    return {
        "status": "joined",
        "network_id": network_id,
        "network_name": network.name,
        "benefits": network.benefits,
    }
