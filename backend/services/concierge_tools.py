"""
Concierge Tools.
Functions available to the AI Concierge for booking and data retrieval.
"""
import asyncio
import structlog
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend import models


def get_db() -> Session:
    """Get database session."""
    return SessionLocal()


def get_booking_url(listing_id: str) -> Dict[str, Any]:
    """
    Get the external booking URL for a listing.
    Returns booking_url and relevant metadata.
    """
    db = get_db()
    try:
        listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
        if not listing:
            return {"success": False, "error": f"Listing {listing_id} not found"}
        
        if not listing.booking_url:
            return {
                "success": False, 
                "error": f"No booking URL available for {listing.name}. Try contacting the host directly."
            }
        
        return {
            "success": True,
            "listing_id": listing.id,
            "listing_name": listing.name,
            "booking_url": listing.booking_url,
            "price_range": listing.price_range,
            "upcoming_dates": listing.upcoming_dates or [],
            "amenities": listing.scraped_amenities or [],
        }
    finally:
        db.close()


def search_bookable_listings(location: str = None, keyword: str = None) -> List[Dict]:
    """
    Search for listings that have booking URLs available.
    These are listings that can be booked through the agent.
    """
    db = get_db()
    try:
        query = db.query(models.Listing).filter(models.Listing.booking_url.isnot(None))
        
        if location:
            query = query.filter(
                (models.Listing.city.ilike(f"%{location}%")) |
                (models.Listing.country.ilike(f"%{location}%")) |
                (models.Listing.name.ilike(f"%{location}%"))
            )
        
        if keyword:
            query = query.filter(
                (models.Listing.name.ilike(f"%{keyword}%")) |
                (models.Listing.description.ilike(f"%{keyword}%"))
            )
        
        listings = query.limit(10).all()
        
        return [
            {
                "id": l.id,
                "name": l.name,
                "city": l.city,
                "country": l.country,
                "booking_url": l.booking_url,
                "price_range": l.price_range,
                "upcoming_dates": (l.upcoming_dates or [])[:3],
                "has_booking": True,
            }
            for l in listings
        ]
    finally:
        db.close()


async def initiate_booking(
    listing_id: str,
    check_in_date: str,
    check_out_date: str,
    guests: int = 2,
    user_id: str = "user-1",
    job_id: str = None,
) -> Dict[str, Any]:
    """
    Initiate a live booking through the booking agent.
    
    This triggers the AgentWorker to navigate to the booking URL
    and attempt to fill out booking forms.
    
    Returns immediately with a job_id that can be used to track progress.
    """
    # Get booking URL
    booking_info = get_booking_url(listing_id)
    if not booking_info.get("success"):
        return booking_info
    
    booking_url = booking_info["booking_url"]
    listing_name = booking_info["listing_name"]
    
    # Create a booking job in the database
    db = get_db()
    try:
        from uuid import uuid4
        job_id = job_id or f"booking-{uuid4().hex[:8]}"
        
        # Check if AgentJob model exists and create job
        try:
            job = models.AgentJob(
                id=job_id,
                type="booking",
                status="pending",
                url=booking_url,
                goal=f"Book a stay at {listing_name} from {check_in_date} to {check_out_date} for {guests} guests.",
                user_id=user_id,
            )
            db.add(job)
            db.commit()
        except Exception as e:
            # AgentJob model may not exist, continue without persistence
            structlog.get_logger("nomadnest.concierge").warning("job_persist_failed", error=str(e))
        
        # Start the booking agent asynchronously
        goal = f"Book a stay at {listing_name} from {check_in_date} to {check_out_date} for {guests} guests."
        
        # Import and run the real LLM-powered agent worker
        try:
            import sys, os
            _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if _project_root not in sys.path:
                sys.path.insert(0, _project_root)
            from core.agent_engine import AgentWorker
            
            worker = AgentWorker()
            
            # Run in background (don't await - return immediately)
            asyncio.create_task(
                worker.execute_task(
                    url=booking_url,
                    goal=goal,
                    job_id=job_id,
                    db=db,
                )
            )
            
            return {
                "success": True,
                "job_id": job_id,
                "status": "started",
                "message": f"🤖 Booking agent started for {listing_name}. I'll navigate to {booking_url} and attempt to book.",
                "booking_url": booking_url,
                "details": {
                    "listing": listing_name,
                    "dates": f"{check_in_date} to {check_out_date}",
                    "guests": guests,
                },
            }
        except ImportError as e:
            return {
                "success": False,
                "error": f"Booking agent not available: {e}. Please book manually at: {booking_url}",
                "booking_url": booking_url,
            }
    finally:
        db.close()


def get_booking_status(job_id: str) -> Dict[str, Any]:
    """
    Check the status of a booking job.
    """
    db = get_db()
    try:
        try:
            job = db.query(models.AgentJob).filter(models.AgentJob.id == job_id).first()
            if not job:
                return {"success": False, "error": f"Job {job_id} not found"}
            
            return {
                "success": True,
                "job_id": job.id,
                "status": job.status,
                "result": job.result,
                "steps_completed": len(job.steps) if hasattr(job, 'steps') and job.steps else 0,
            }
        except:
            return {"success": False, "error": "Job tracking not available"}
    finally:
        db.close()


# Tool definitions for LLM function calling
BOOKING_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_booking_url",
            "description": "Get the external booking URL and availability info for a listing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_id": {
                        "type": "string",
                        "description": "The ID of the listing to get booking info for"
                    }
                },
                "required": ["listing_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_bookable_listings",
            "description": "Search for listings that have online booking available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City, country, or location to search in"
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to search for (e.g., 'wellness', 'yoga')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_booking",
            "description": "Start an automated booking process for a listing. The AI agent will navigate to the booking site and attempt to complete the reservation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_id": {
                        "type": "string",
                        "description": "The ID of the listing to book"
                    },
                    "check_in_date": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "check_out_date": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format"
                    },
                    "guests": {
                        "type": "integer",
                        "description": "Number of guests",
                        "default": 2
                    }
                },
                "required": ["listing_id", "check_in_date", "check_out_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_booking_status",
            "description": "Check the status of an in-progress booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job ID returned when booking was initiated"
                    }
                },
                "required": ["job_id"]
            }
        }
    }
]
