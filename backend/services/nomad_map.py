"""
Nomad Map Service - Real-time location sharing for digital nomads.
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from math import radians, sin, cos, sqrt, atan2
from uuid import uuid4

from backend import models

logger = structlog.get_logger(__name__)


# Haversine formula for distance calculation
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km."""
    R = 6371  # Earth's radius in km
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


class NomadMapService:
    """
    Service for managing nomad locations on the live map.
    
    Features:
    - Update user location with privacy controls
    - Find nearby nomads (with visibility filtering)
    - Get nomads in a specific city
    - Real-time location broadcasts via SSE/Socket.IO
    """
    
    def update_location(
        self,
        db: Session,
        user_id: str,
        latitude: float,
        longitude: float,
        city: Optional[str] = None,
        country: Optional[str] = None,
        country_code: Optional[str] = None,
        status: Optional[str] = None,
        available_for_meetup: bool = False,
        visibility: str = "connections",
        blur_radius_km: float = 5.0,
        ghost_mode: bool = False,
        show_city_only: bool = True,
        arrival_date: Optional[datetime] = None,
        planned_departure: Optional[datetime] = None,
    ) -> models.NomadLocation:
        """Update or create user location."""
        
        # Get existing location or create new
        location = db.query(models.NomadLocation).filter(
            models.NomadLocation.user_id == user_id
        ).first()
        
        if location:
            # Update existing
            location.latitude = latitude
            location.longitude = longitude
            location.city = city
            location.country = country
            location.country_code = country_code
            location.status = status
            location.available_for_meetup = available_for_meetup
            location.visibility = visibility
            location.blur_radius_km = blur_radius_km
            location.ghost_mode = ghost_mode
            location.show_city_only = show_city_only
            location.arrival_date = arrival_date
            location.planned_departure = planned_departure
            location.updated_at = datetime.utcnow()
        else:
            # Create new
            location = models.NomadLocation(
                id=str(uuid4()),
                user_id=user_id,
                latitude=latitude,
                longitude=longitude,
                city=city,
                country=country,
                country_code=country_code,
                status=status,
                available_for_meetup=available_for_meetup,
                visibility=visibility,
                blur_radius_km=blur_radius_km,
                ghost_mode=ghost_mode,
                show_city_only=show_city_only,
                arrival_date=arrival_date,
                planned_departure=planned_departure,
            )
            db.add(location)
        
        db.commit()
        db.refresh(location)
        
        logger.info(
            "location_updated",
            user_id=user_id,
            city=city,
            visibility=visibility,
        )
        
        return location
    
    def get_my_location(
        self,
        db: Session,
        user_id: str,
    ) -> Optional[models.NomadLocation]:
        """Get current user's location."""
        return db.query(models.NomadLocation).filter(
            models.NomadLocation.user_id == user_id
        ).first()
    
    def delete_location(
        self,
        db: Session,
        user_id: str,
    ) -> bool:
        """Remove user from the map."""
        location = db.query(models.NomadLocation).filter(
            models.NomadLocation.user_id == user_id
        ).first()
        
        if location:
            db.delete(location)
            db.commit()
            return True
        return False
    
    def get_nearby_nomads(
        self,
        db: Session,
        user_id: str,
        latitude: float,
        longitude: float,
        radius_km: float = 50,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Find nearby nomads within radius.
        Respects privacy settings and connection status.
        """
        # Get user's connections for visibility filtering
        connections = db.query(models.NomadConnection).filter(
            and_(
                or_(
                    models.NomadConnection.user_id == user_id,
                    models.NomadConnection.connected_user_id == user_id,
                ),
                models.NomadConnection.status == "accepted",
            )
        ).all()
        
        connected_user_ids = set()
        for conn in connections:
            if conn.user_id == user_id:
                connected_user_ids.add(conn.connected_user_id)
            else:
                connected_user_ids.add(conn.user_id)
        
        # Get all visible locations (not ghost mode, and visible to this user)
        locations = db.query(models.NomadLocation).filter(
            models.NomadLocation.ghost_mode == False,
            models.NomadLocation.user_id != user_id,
        ).all()
        
        # Filter by visibility and distance
        nearby = []
        for loc in locations:
            # Check visibility
            if loc.visibility == "private":
                continue
            elif loc.visibility == "connections" and loc.user_id not in connected_user_ids:
                continue
            
            # Calculate distance
            distance = haversine_distance(latitude, longitude, loc.latitude, loc.longitude)
            
            if distance <= radius_km:
                # Get user info
                user = db.query(models.User).filter(
                    models.User.id == loc.user_id
                ).first()
                
                # Apply blur if needed
                display_lat = loc.latitude
                display_lon = loc.longitude
                
                if loc.show_city_only:
                    # Round to city level (about 0.1 degree)
                    display_lat = round(loc.latitude, 1)
                    display_lon = round(loc.longitude, 1)
                
                nearby.append({
                    "user_id": loc.user_id,
                    "name": user.name if user else "Anonymous",
                    "avatar": user.avatar if user else None,
                    "latitude": display_lat,
                    "longitude": display_lon,
                    "city": loc.city,
                    "country": loc.country,
                    "country_code": loc.country_code,
                    "status": loc.status,
                    "available_for_meetup": loc.available_for_meetup,
                    "distance_km": round(distance, 1),
                    "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
                    "is_connection": loc.user_id in connected_user_ids,
                })
        
        # Sort by distance
        nearby.sort(key=lambda x: x["distance_km"])
        
        return nearby[:limit]
    
    def get_nomads_in_city(
        self,
        db: Session,
        user_id: str,
        city: str,
        country: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get all visible nomads in a specific city."""
        # Get user's connections
        connections = db.query(models.NomadConnection).filter(
            and_(
                or_(
                    models.NomadConnection.user_id == user_id,
                    models.NomadConnection.connected_user_id == user_id,
                ),
                models.NomadConnection.status == "accepted",
            )
        ).all()
        
        connected_user_ids = {
            conn.connected_user_id if conn.user_id == user_id else conn.user_id
            for conn in connections
        }
        
        # Query locations in city
        query = db.query(models.NomadLocation).filter(
            models.NomadLocation.city.ilike(city),
            models.NomadLocation.ghost_mode == False,
            models.NomadLocation.user_id != user_id,
        )
        
        if country:
            query = query.filter(models.NomadLocation.country.ilike(country))
        
        locations = query.limit(limit * 2).all()  # Get extra to filter
        
        result = []
        for loc in locations:
            # Check visibility
            if loc.visibility == "private":
                continue
            elif loc.visibility == "connections" and loc.user_id not in connected_user_ids:
                continue
            
            user = db.query(models.User).filter(
                models.User.id == loc.user_id
            ).first()
            
            result.append({
                "user_id": loc.user_id,
                "name": user.name if user else "Anonymous",
                "avatar": user.avatar if user else None,
                "city": loc.city,
                "country": loc.country,
                "status": loc.status,
                "available_for_meetup": loc.available_for_meetup,
                "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
                "is_connection": loc.user_id in connected_user_ids,
            })
        
        return result[:limit]
    
    def get_global_heatmap(
        self,
        db: Session,
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated nomad counts by city for heatmap visualization.
        No privacy concerns since this is aggregated.
        """
        # Count nomads per city (only non-ghost mode)
        results = db.query(
            models.NomadLocation.city,
            models.NomadLocation.country,
            models.NomadLocation.country_code,
            func.avg(models.NomadLocation.latitude).label("lat"),
            func.avg(models.NomadLocation.longitude).label("lon"),
            func.count(models.NomadLocation.id).label("count"),
        ).filter(
            models.NomadLocation.ghost_mode == False,
            models.NomadLocation.city != None,
        ).group_by(
            models.NomadLocation.city,
            models.NomadLocation.country,
            models.NomadLocation.country_code,
        ).all()
        
        return [
            {
                "city": r.city,
                "country": r.country,
                "country_code": r.country_code,
                "latitude": round(r.lat, 2),
                "longitude": round(r.lon, 2),
                "nomad_count": r.count,
            }
            for r in results
        ]
    
    # Connection management
    def send_connection_request(
        self,
        db: Session,
        user_id: str,
        target_user_id: str,
    ) -> models.NomadConnection:
        """Send a connection request to another nomad."""
        # Check if connection already exists
        existing = db.query(models.NomadConnection).filter(
            or_(
                and_(
                    models.NomadConnection.user_id == user_id,
                    models.NomadConnection.connected_user_id == target_user_id,
                ),
                and_(
                    models.NomadConnection.user_id == target_user_id,
                    models.NomadConnection.connected_user_id == user_id,
                ),
            )
        ).first()
        
        if existing:
            return existing
        
        connection = models.NomadConnection(
            id=str(uuid4()),
            user_id=user_id,
            connected_user_id=target_user_id,
            status="pending",
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        
        return connection
    
    def accept_connection(
        self,
        db: Session,
        user_id: str,
        connection_id: str,
    ) -> Optional[models.NomadConnection]:
        """Accept a connection request."""
        connection = db.query(models.NomadConnection).filter(
            models.NomadConnection.id == connection_id,
            models.NomadConnection.connected_user_id == user_id,
            models.NomadConnection.status == "pending",
        ).first()
        
        if connection:
            connection.status = "accepted"
            db.commit()
            db.refresh(connection)
        
        return connection


# Singleton
nomad_map_service = NomadMapService()
