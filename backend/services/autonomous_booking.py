"""
Autonomous "Do It For Me" Booking Service.

Handles end-to-end automated booking with intelligent search, negotiation, and booking.
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from uuid import uuid4
import asyncio

from backend import models

logger = structlog.get_logger(__name__)


# Typical booking workflow steps
BOOKING_WORKFLOW = [
    {"action": "analyze_request", "description": "Analyzing your preferences"},
    {"action": "search_listings", "description": "Searching for matching listings"},
    {"action": "check_availability", "description": "Checking availability"},
    {"action": "compare_options", "description": "Comparing best options"},
    {"action": "verify_details", "description": "Verifying listing details"},
    {"action": "await_approval", "description": "Waiting for your approval"},
    {"action": "initiate_booking", "description": "Initiating booking"},
    {"action": "confirm_payment", "description": "Confirming payment"},
    {"action": "finalize", "description": "Finalizing reservation"},
]


class AutonomousBookingService:
    """
    Autonomous booking agent service.
    
    Features:
    - End-to-end automated search and booking
    - Smart option comparison
    - Progress tracking
    - Pre-authorization support
    """
    
    def create_request(
        self,
        db: Session,
        user_id: str,
        request_type: str,
        preferences: Dict[str, Any],
        max_budget_usd: float,
        authorized_payment_usd: Optional[float] = None,
    ) -> models.AutonomousBookingRequest:
        """Create a new autonomous booking request."""
        request_id = str(uuid4())
        
        request = models.AutonomousBookingRequest(
            id=request_id,
            user_id=user_id,
            request_type=request_type,
            preferences=preferences,
            max_budget_usd=max_budget_usd,
            authorized_payment_usd=authorized_payment_usd,
            status="pending",
            current_step="Initializing...",
            progress_percent=0,
        )
        db.add(request)
        
        # Create workflow steps
        for i, step in enumerate(BOOKING_WORKFLOW):
            step_record = models.AutonomousBookingStep(
                id=str(uuid4()),
                request_id=request_id,
                step_number=i,
                action=step["action"],
                description=step["description"],
                status="pending",
            )
            db.add(step_record)
        
        db.commit()
        db.refresh(request)
        
        logger.info("autonomous_booking_created", request_id=request_id, user_id=user_id, type=request_type)
        return request
    
    def get_request(
        self,
        db: Session,
        request_id: str,
        user_id: str,
    ) -> Optional[models.AutonomousBookingRequest]:
        """Get a booking request."""
        return db.query(models.AutonomousBookingRequest).filter(
            models.AutonomousBookingRequest.id == request_id,
            models.AutonomousBookingRequest.user_id == user_id,
        ).first()
    
    def get_request_with_steps(
        self,
        db: Session,
        request_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get request with all steps."""
        request = self.get_request(db, request_id, user_id)
        if not request:
            return None
        
        steps = db.query(models.AutonomousBookingStep).filter(
            models.AutonomousBookingStep.request_id == request_id
        ).order_by(models.AutonomousBookingStep.step_number).all()
        
        return {
            "id": request.id,
            "request_type": request.request_type,
            "preferences": request.preferences,
            "max_budget_usd": request.max_budget_usd,
            "authorized_payment_usd": request.authorized_payment_usd,
            "status": request.status,
            "current_step": request.current_step,
            "progress_percent": request.progress_percent,
            "found_options": request.found_options,
            "selected_option": request.selected_option,
            "booking_confirmation": request.booking_confirmation,
            "error_message": request.error_message,
            "created_at": request.created_at.isoformat() if request.created_at else None,
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            "steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "description": s.description,
                    "status": s.status,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "duration_seconds": s.duration_seconds,
                    "error_message": s.error_message,
                }
                for s in steps
            ],
        }
    
    def list_user_requests(
        self,
        db: Session,
        user_id: str,
        status: Optional[str] = None,
    ) -> List[models.AutonomousBookingRequest]:
        """List user's booking requests."""
        query = db.query(models.AutonomousBookingRequest).filter(
            models.AutonomousBookingRequest.user_id == user_id
        )
        
        if status:
            query = query.filter(models.AutonomousBookingRequest.status == status)
        
        return query.order_by(models.AutonomousBookingRequest.created_at.desc()).all()
    
    def update_step(
        self,
        db: Session,
        request_id: str,
        step_number: int,
        status: str,
        output_data: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ):
        """Update a step's status."""
        step = db.query(models.AutonomousBookingStep).filter(
            models.AutonomousBookingStep.request_id == request_id,
            models.AutonomousBookingStep.step_number == step_number,
        ).first()
        
        if not step:
            return
        
        if status == "running" and not step.started_at:
            step.started_at = datetime.utcnow()
        
        if status in ["completed", "failed"]:
            step.completed_at = datetime.utcnow()
            if step.started_at:
                step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        
        step.status = status
        if output_data:
            step.output_data = output_data
        if error_message:
            step.error_message = error_message
        
        db.commit()
    
    def update_request_progress(
        self,
        db: Session,
        request_id: str,
        status: str,
        current_step: str,
        progress_percent: int,
        found_options: Optional[List] = None,
        selected_option: Optional[Dict] = None,
        booking_confirmation: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ):
        """Update request progress."""
        request = db.query(models.AutonomousBookingRequest).filter(
            models.AutonomousBookingRequest.id == request_id
        ).first()
        
        if not request:
            return
        
        request.status = status
        request.current_step = current_step
        request.progress_percent = progress_percent
        
        if found_options is not None:
            request.found_options = found_options
        if selected_option is not None:
            request.selected_option = selected_option
        if booking_confirmation is not None:
            request.booking_confirmation = booking_confirmation
            request.completed_at = datetime.utcnow()
        if error_message:
            request.error_message = error_message
        
        db.commit()
    
    def simulate_booking_process(
        self,
        db: Session,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Simulate the autonomous booking process (for demo).
        In production, this would involve real API calls to booking platforms.
        """
        request = db.query(models.AutonomousBookingRequest).filter(
            models.AutonomousBookingRequest.id == request_id
        ).first()
        
        if not request:
            return {"error": "Request not found"}
        
        prefs = request.preferences
        
        # Step 0: Analyze request
        self.update_step(db, request_id, 0, "running")
        self.update_request_progress(db, request_id, "searching", "Analyzing preferences...", 5)
        self.update_step(db, request_id, 0, "completed", {"analyzed": True})
        
        # Step 1: Search listings (simulated)
        self.update_step(db, request_id, 1, "running")
        self.update_request_progress(db, request_id, "searching", "Searching listings...", 15)
        
        # Generate mock results based on preferences
        destination = prefs.get("destination", "Unknown")
        budget = request.max_budget_usd
        
        mock_options = [
            {
                "id": "opt_1",
                "title": f"Sunny Studio in {destination} Center",
                "type": "apartment",
                "price_per_night": min(50, budget / 20),
                "total_price": min(50, budget / 20) * 14,
                "rating": 4.8,
                "reviews": 127,
                "amenities": ["wifi", "kitchen", "air_conditioning"],
                "image": "https://example.com/listing1.jpg",
                "match_score": 95,
            },
            {
                "id": "opt_2",
                "title": f"Cozy Loft Near Coworking Hub",
                "type": "loft",
                "price_per_night": min(65, budget / 15),
                "total_price": min(65, budget / 15) * 14,
                "rating": 4.9,
                "reviews": 89,
                "amenities": ["wifi", "kitchen", "workspace", "gym"],
                "image": "https://example.com/listing2.jpg",
                "match_score": 92,
            },
            {
                "id": "opt_3",
                "title": f"Modern Apartment with Sea View",
                "type": "apartment",
                "price_per_night": min(80, budget / 12),
                "total_price": min(80, budget / 12) * 14,
                "rating": 4.7,
                "reviews": 203,
                "amenities": ["wifi", "kitchen", "balcony", "parking"],
                "image": "https://example.com/listing3.jpg",
                "match_score": 88,
            },
        ]
        
        self.update_step(db, request_id, 1, "completed", {"options_found": len(mock_options)})
        self.update_request_progress(db, request_id, "searching", "Found matching listings", 25, found_options=mock_options)
        
        # Step 2: Check availability
        self.update_step(db, request_id, 2, "running")
        self.update_request_progress(db, request_id, "searching", "Checking availability...", 35)
        
        # Mark 2 as available
        for opt in mock_options[:2]:
            opt["available"] = True
        mock_options[2]["available"] = False
        
        self.update_step(db, request_id, 2, "completed", {"available_count": 2})
        self.update_request_progress(db, request_id, "searching", "Availability confirmed", 45, found_options=mock_options)
        
        # Step 3: Compare options
        self.update_step(db, request_id, 3, "running")
        self.update_request_progress(db, request_id, "comparing", "Comparing options...", 55)
        
        # Select best option
        available_opts = [o for o in mock_options if o.get("available")]
        best_option = max(available_opts, key=lambda x: x["match_score"]) if available_opts else None
        
        self.update_step(db, request_id, 3, "completed", {"best_match": best_option["id"] if best_option else None})
        
        # Step 4: Verify details
        self.update_step(db, request_id, 4, "running")
        self.update_request_progress(db, request_id, "verifying", "Verifying listing details...", 65)
        
        if best_option:
            best_option["verified"] = True
            best_option["verification_details"] = {
                "host_response_rate": "98%",
                "superhost": True,
                "cancellation_policy": "flexible",
            }
        
        self.update_step(db, request_id, 4, "completed")
        self.update_request_progress(db, request_id, "awaiting_approval", "Ready for your approval", 70, 
                                     found_options=mock_options, selected_option=best_option)
        
        return {
            "status": "awaiting_approval",
            "found_options": mock_options,
            "recommended_option": best_option,
            "message": "We found great options! Please review and approve to continue.",
            "demo_mode": True,
            "demo_notice": "Results are simulated. Live booking integration coming soon.",
        }
    
    def approve_and_book(
        self,
        db: Session,
        request_id: str,
        user_id: str,
        option_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve the selected option and proceed with booking."""
        request = self.get_request(db, request_id, user_id)
        if not request:
            return {"error": "Request not found"}
        
        if request.status != "awaiting_approval":
            return {"error": "Request is not awaiting approval"}
        
        # Find selected option
        selected = None
        if option_id:
            for opt in request.found_options:
                if opt.get("id") == option_id:
                    selected = opt
                    break
        else:
            selected = request.selected_option
        
        if not selected:
            return {"error": "No option selected"}
        
        # Step 6: Initiate booking
        self.update_step(db, request_id, 6, "running")
        self.update_request_progress(db, request_id, "booking", "Initiating booking...", 80, selected_option=selected)
        
        # Simulate booking
        self.update_step(db, request_id, 6, "completed")
        
        # Step 7: Confirm payment
        self.update_step(db, request_id, 7, "running")
        self.update_request_progress(db, request_id, "booking", "Processing payment...", 90)
        self.update_step(db, request_id, 7, "completed")
        
        # Step 8: Finalize
        self.update_step(db, request_id, 8, "running")
        self.update_request_progress(db, request_id, "booking", "Finalizing reservation...", 95)
        
        confirmation = {
            "confirmation_code": f"NN{uuid4().hex[:8].upper()}",
            "listing": selected,
            "check_in": request.preferences.get("check_in"),
            "check_out": request.preferences.get("check_out"),
            "total_paid": selected.get("total_price"),
            "host_contact": "Contact info will be provided 24h before check-in",
            "booked_at": datetime.utcnow().isoformat(),
        }
        
        self.update_step(db, request_id, 8, "completed", confirmation)
        self.update_request_progress(db, request_id, "completed", "Booking confirmed!", 100,
                                     booking_confirmation=confirmation)
        
        logger.info("autonomous_booking_completed", request_id=request_id, confirmation_code=confirmation["confirmation_code"])
        
        return {
            "status": "completed",
            "confirmation": confirmation,
            "message": "Your booking is confirmed! 🎉",
            "demo_mode": True,
            "demo_notice": "This is a simulated confirmation. No real booking was made.",
        }
    
    def cancel_request(
        self,
        db: Session,
        request_id: str,
        user_id: str,
    ) -> bool:
        """Cancel a booking request."""
        request = self.get_request(db, request_id, user_id)
        if not request:
            return False
        
        if request.status in ["completed", "cancelled"]:
            return False
        
        request.status = "cancelled"
        request.current_step = "Cancelled by user"
        db.commit()
        
        logger.info("autonomous_booking_cancelled", request_id=request_id)
        return True


# Singleton
autonomous_booking_service = AutonomousBookingService()
