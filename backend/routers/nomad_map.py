"""
Nomad Map API Router.

Live map showing nomad locations with privacy controls.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.services.nomad_map import nomad_map_service

router = APIRouter(prefix="/api/nomad-map", tags=["nomad-map"])


# ============================================================================
# Schemas
# ============================================================================

class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = Field(None, max_length=3)
    status: Optional[str] = Field(None, max_length=100, example="Working from a beach cafe ☕")
    available_for_meetup: bool = False
    visibility: str = Field(default="connections", pattern="^(public|connections|private)$")
    blur_radius_km: float = Field(default=5.0, ge=0, le=50)
    ghost_mode: bool = False
    show_city_only: bool = True
    arrival_date: Optional[datetime] = None
    planned_departure: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 38.7223,
                "longitude": -9.1393,
                "city": "Lisbon",
                "country": "Portugal",
                "country_code": "PT",
                "status": "Living the dream ☀️",
                "available_for_meetup": True,
                "visibility": "connections",
                "show_city_only": True,
            }
        }


class LocationResponse(BaseModel):
    id: str
    user_id: str
    latitude: float
    longitude: float
    city: Optional[str]
    country: Optional[str]
    country_code: Optional[str]
    status: Optional[str]
    available_for_meetup: bool
    visibility: str
    ghost_mode: bool
    arrival_date: Optional[datetime]
    planned_departure: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class NearbyNomad(BaseModel):
    user_id: str
    name: str
    avatar: Optional[str]
    latitude: float
    longitude: float
    city: Optional[str]
    country: Optional[str]
    country_code: Optional[str]
    status: Optional[str]
    available_for_meetup: bool
    distance_km: float
    is_connection: bool
    updated_at: Optional[str]


class HeatmapPoint(BaseModel):
    city: str
    country: Optional[str]
    country_code: Optional[str]
    latitude: float
    longitude: float
    nomad_count: int


class ConnectionRequest(BaseModel):
    target_user_id: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/location", response_model=LocationResponse)
async def update_my_location(
    data: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Update your location on the nomad map.
    
    **Privacy Options:**
    - `visibility`: Who can see you
      - `public`: Anyone on the platform
      - `connections`: Only your connections
      - `private`: Only you (for cost calculator, etc.)
    - `ghost_mode`: Completely hide from map
    - `show_city_only`: Only show city, not exact location
    - `blur_radius_km`: Add random offset to exact location
    """
    location = nomad_map_service.update_location(
        db=db,
        user_id=current_user.id,
        latitude=data.latitude,
        longitude=data.longitude,
        city=data.city,
        country=data.country,
        country_code=data.country_code,
        status=data.status,
        available_for_meetup=data.available_for_meetup,
        visibility=data.visibility,
        blur_radius_km=data.blur_radius_km,
        ghost_mode=data.ghost_mode,
        show_city_only=data.show_city_only,
        arrival_date=data.arrival_date,
        planned_departure=data.planned_departure,
    )
    
    return location


@router.get("/location", response_model=Optional[LocationResponse])
async def get_my_location(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get your current location settings."""
    return nomad_map_service.get_my_location(db, current_user.id)


@router.delete("/location")
async def delete_my_location(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Remove yourself from the map completely."""
    success = nomad_map_service.delete_location(db, current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Location not found")
    
    return {"message": "Location deleted", "visible_on_map": False}


@router.get("/nearby", response_model=List[NearbyNomad])
async def get_nearby_nomads(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(default=50, ge=1, le=500),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Find nomads near a location.
    
    Results are filtered based on each nomad's visibility settings
    and your connection status with them.
    """
    nomads = nomad_map_service.get_nearby_nomads(
        db=db,
        user_id=current_user.id,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
    )
    
    return nomads


@router.get("/city/{city_name}")
async def get_nomads_in_city(
    city_name: str,
    country: Optional[str] = None,
    limit: int = Query(default=100, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all visible nomads in a specific city."""
    nomads = nomad_map_service.get_nomads_in_city(
        db=db,
        user_id=current_user.id,
        city=city_name,
        country=country,
        limit=limit,
    )
    
    return {"city": city_name, "country": country, "nomads": nomads, "count": len(nomads)}


@router.get("/heatmap", response_model=List[HeatmapPoint])
async def get_global_heatmap(
    db: Session = Depends(get_db),
):
    """
    Get aggregated nomad counts by city for heatmap visualization.
    
    This is public data (no auth required) as it's aggregated.
    """
    return nomad_map_service.get_global_heatmap(db)


# ============================================================================
# Connection Management
# ============================================================================

@router.post("/connections")
async def send_connection_request(
    data: ConnectionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Send a connection request to another nomad."""
    if data.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot connect with yourself")
    
    connection = nomad_map_service.send_connection_request(
        db=db,
        user_id=current_user.id,
        target_user_id=data.target_user_id,
    )
    
    return {
        "id": connection.id,
        "status": connection.status,
        "message": "Connection request sent" if connection.status == "pending" else "Already connected",
    }


@router.post("/connections/{connection_id}/accept")
async def accept_connection_request(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Accept a connection request."""
    connection = nomad_map_service.accept_connection(
        db=db,
        user_id=current_user.id,
        connection_id=connection_id,
    )
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection request not found")
    
    return {"id": connection.id, "status": "accepted", "message": "Connection accepted"}


@router.get("/connections")
def get_my_connections(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all your connections."""
    connections = db.query(models.NomadConnection).filter(
        models.NomadConnection.status == "accepted",
        (models.NomadConnection.user_id == current_user.id) |
        (models.NomadConnection.connected_user_id == current_user.id),
    ).all()
    
    result = []
    for conn in connections:
        other_user_id = conn.connected_user_id if conn.user_id == current_user.id else conn.user_id
        other_user = db.query(models.User).filter(models.User.id == other_user_id).first()
        
        result.append({
            "id": conn.id,
            "user_id": other_user_id,
            "name": other_user.name if other_user else "Unknown",
            "avatar": other_user.avatar if other_user else None,
            "connected_at": conn.created_at.isoformat() if conn.created_at else None,
        })
    
    return {"connections": result, "count": len(result)}


@router.get("/connections/pending")
def get_pending_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get pending connection requests for you to accept/decline."""
    pending = db.query(models.NomadConnection).filter(
        models.NomadConnection.connected_user_id == current_user.id,
        models.NomadConnection.status == "pending",
    ).all()
    
    result = []
    for conn in pending:
        requester = db.query(models.User).filter(models.User.id == conn.user_id).first()
        
        result.append({
            "id": conn.id,
            "user_id": conn.user_id,
            "name": requester.name if requester else "Unknown",
            "avatar": requester.avatar if requester else None,
            "requested_at": conn.created_at.isoformat() if conn.created_at else None,
        })
    
    return {"pending_requests": result, "count": len(result)}
