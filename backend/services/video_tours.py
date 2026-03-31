"""
Host Video Tours Service.

Manage video tours of listings with live/recorded options and AI summaries.
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from uuid import uuid4

from backend import models

logger = structlog.get_logger(__name__)


class VideoTourService:
    """
    Video tour management service.
    
    Features:
    - Upload/schedule video tours
    - Generate AI summaries
    - Handle live tour registrations
    - Track views
    """
    
    def create_recorded_tour(
        self,
        db: Session,
        host_id: str,
        listing_id: str,
        title: str,
        video_url: str,
        thumbnail_url: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        description: Optional[str] = None,
    ) -> models.VideoTour:
        """Create a recorded video tour."""
        tour = models.VideoTour(
            id=str(uuid4()),
            listing_id=listing_id,
            host_id=host_id,
            title=title,
            description=description,
            tour_type="recorded",
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            duration_seconds=duration_seconds,
            status="ready",
        )
        db.add(tour)
        db.commit()
        db.refresh(tour)
        
        logger.info("video_tour_created", tour_id=tour.id, listing_id=listing_id, type="recorded")
        return tour
    
    def schedule_live_tour(
        self,
        db: Session,
        host_id: str,
        listing_id: str,
        title: str,
        scheduled_at: datetime,
        meeting_url: str,
        max_attendees: int = 10,
        description: Optional[str] = None,
    ) -> models.VideoTour:
        """Schedule a live video tour."""
        tour = models.VideoTour(
            id=str(uuid4()),
            listing_id=listing_id,
            host_id=host_id,
            title=title,
            description=description,
            tour_type="scheduled",
            scheduled_at=scheduled_at,
            meeting_url=meeting_url,
            max_attendees=max_attendees,
            status="scheduled",
        )
        db.add(tour)
        db.commit()
        db.refresh(tour)
        
        logger.info("live_tour_scheduled", tour_id=tour.id, listing_id=listing_id, scheduled=scheduled_at.isoformat())
        return tour
    
    def get_tour(
        self,
        db: Session,
        tour_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get tour details."""
        tour = db.query(models.VideoTour).filter(
            models.VideoTour.id == tour_id
        ).first()
        
        if not tour:
            return None
        
        # Get listing and host info
        listing = db.query(models.Listing).filter(
            models.Listing.id == tour.listing_id
        ).first()
        
        host = db.query(models.User).filter(
            models.User.id == tour.host_id
        ).first()
        
        # Count registrations for live tours
        registrations = 0
        if tour.tour_type in ["scheduled", "live"]:
            registrations = db.query(models.TourRegistration).filter(
                models.TourRegistration.tour_id == tour_id
            ).count()
        
        return {
            "id": tour.id,
            "title": tour.title,
            "description": tour.description,
            "tour_type": tour.tour_type,
            "status": tour.status,
            "video_url": tour.video_url,
            "thumbnail_url": tour.thumbnail_url,
            "duration_seconds": tour.duration_seconds,
            "scheduled_at": tour.scheduled_at.isoformat() if tour.scheduled_at else None,
            "meeting_url": tour.meeting_url if tour.tour_type in ["scheduled", "live"] else None,
            "max_attendees": tour.max_attendees,
            "registrations": registrations,
            "spots_left": max(0, tour.max_attendees - registrations) if tour.max_attendees else None,
            "ai_summary": tour.ai_summary,
            "ai_highlights": tour.ai_highlights,
            "views_count": tour.views_count,
            "listing": {
                "id": listing.id,
                "title": listing.title,
                "city": listing.city,
            } if listing else None,
            "host": {
                "id": host.id,
                "name": host.name,
            } if host else None,
            "created_at": tour.created_at.isoformat() if tour.created_at else None,
        }
    
    def list_tours_for_listing(
        self,
        db: Session,
        listing_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all tours for a listing."""
        tours = db.query(models.VideoTour).filter(
            models.VideoTour.listing_id == listing_id,
            models.VideoTour.status.in_(["ready", "scheduled", "live"]),
        ).order_by(models.VideoTour.created_at.desc()).all()
        
        return [
            {
                "id": t.id,
                "title": t.title,
                "tour_type": t.tour_type,
                "status": t.status,
                "thumbnail_url": t.thumbnail_url,
                "duration_seconds": t.duration_seconds,
                "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
                "views_count": t.views_count,
            }
            for t in tours
        ]
    
    def get_upcoming_live_tours(
        self,
        db: Session,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get upcoming live tours across all listings."""
        now = datetime.utcnow()
        
        tours = db.query(models.VideoTour).filter(
            models.VideoTour.tour_type == "scheduled",
            models.VideoTour.scheduled_at > now,
            models.VideoTour.status == "scheduled",
        ).order_by(models.VideoTour.scheduled_at).limit(limit).all()
        
        result = []
        for tour in tours:
            listing = db.query(models.Listing).filter(
                models.Listing.id == tour.listing_id
            ).first()
            
            host = db.query(models.User).filter(
                models.User.id == tour.host_id
            ).first()
            
            registrations = db.query(models.TourRegistration).filter(
                models.TourRegistration.tour_id == tour.id
            ).count()
            
            result.append({
                "id": tour.id,
                "title": tour.title,
                "scheduled_at": tour.scheduled_at.isoformat(),
                "max_attendees": tour.max_attendees,
                "registrations": registrations,
                "spots_left": max(0, tour.max_attendees - registrations),
                "listing": {
                    "id": listing.id,
                    "title": listing.title,
                    "city": listing.city,
                    "image": listing.images[0] if listing and listing.images else None,
                } if listing else None,
                "host": {"name": host.name} if host else None,
            })
        
        return result
    
    def register_for_tour(
        self,
        db: Session,
        tour_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Register a user for a live tour."""
        tour = db.query(models.VideoTour).filter(
            models.VideoTour.id == tour_id
        ).first()
        
        if not tour:
            raise ValueError("Tour not found")
        
        if tour.tour_type != "scheduled":
            raise ValueError("Can only register for scheduled tours")
        
        # Check if already registered
        existing = db.query(models.TourRegistration).filter(
            models.TourRegistration.tour_id == tour_id,
            models.TourRegistration.user_id == user_id,
        ).first()
        
        if existing:
            return {"already_registered": True, "registration_id": existing.id}
        
        # Check capacity
        count = db.query(models.TourRegistration).filter(
            models.TourRegistration.tour_id == tour_id
        ).count()
        
        if count >= tour.max_attendees:
            raise ValueError("Tour is full")
        
        registration = models.TourRegistration(
            id=str(uuid4()),
            tour_id=tour_id,
            user_id=user_id,
        )
        db.add(registration)
        db.commit()
        
        logger.info("tour_registration", tour_id=tour_id, user_id=user_id)
        
        return {
            "registration_id": registration.id,
            "meeting_url": tour.meeting_url,
            "scheduled_at": tour.scheduled_at.isoformat(),
        }
    
    def cancel_registration(
        self,
        db: Session,
        tour_id: str,
        user_id: str,
    ) -> bool:
        """Cancel a tour registration."""
        registration = db.query(models.TourRegistration).filter(
            models.TourRegistration.tour_id == tour_id,
            models.TourRegistration.user_id == user_id,
        ).first()
        
        if not registration:
            return False
        
        db.delete(registration)
        db.commit()
        return True
    
    def record_view(
        self,
        db: Session,
        tour_id: str,
    ):
        """Record a view for a tour."""
        tour = db.query(models.VideoTour).filter(
            models.VideoTour.id == tour_id
        ).first()
        
        if tour:
            tour.views_count += 1
            db.commit()
    
    def set_ai_summary(
        self,
        db: Session,
        tour_id: str,
        summary: str,
        highlights: Optional[List[str]] = None,
    ):
        """Set AI-generated summary for a tour."""
        tour = db.query(models.VideoTour).filter(
            models.VideoTour.id == tour_id
        ).first()
        
        if tour:
            tour.ai_summary = summary
            tour.ai_highlights = highlights
            db.commit()
    
    def get_user_registrations(
        self,
        db: Session,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all tour registrations for a user."""
        registrations = db.query(models.TourRegistration).filter(
            models.TourRegistration.user_id == user_id,
        ).all()
        
        result = []
        for reg in registrations:
            tour = db.query(models.VideoTour).filter(
                models.VideoTour.id == reg.tour_id
            ).first()
            
            if tour:
                listing = db.query(models.Listing).filter(
                    models.Listing.id == tour.listing_id
                ).first()
                
                result.append({
                    "registration_id": reg.id,
                    "tour": {
                        "id": tour.id,
                        "title": tour.title,
                        "scheduled_at": tour.scheduled_at.isoformat() if tour.scheduled_at else None,
                        "meeting_url": tour.meeting_url,
                        "status": tour.status,
                    },
                    "listing": {
                        "id": listing.id,
                        "title": listing.title,
                        "city": listing.city,
                    } if listing else None,
                    "attended": reg.attended,
                })
        
        return result


# Singleton
video_tour_service = VideoTourService()
