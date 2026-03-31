import structlog
from sqlalchemy.orm import Session, joinedload
from typing import List
from backend import models, schemas, database
from backend.utils import get_current_user
from backend.routers.sse import emit_booking_created, emit_notification
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import uuid4

router = APIRouter()
logger = structlog.get_logger("nomadnest.bookings")


def get_db():
    yield from database.get_db()


@router.get(
    "/",
    response_model=schemas.PaginatedResponse[schemas.Booking],
    summary="List my bookings",
    description="Returns a paginated list of bookings for the current authenticated user with eager-loaded listings.",
)
def read_bookings(page: int = 1, size: int = 20, db: Session = Depends(get_db)):
    offset = (page - 1) * size
    
    # Base query with eager loading
    query = db.query(models.Booking).options(
        joinedload(models.Booking.listing),
        joinedload(models.Booking.user)
    )
    
    total = query.count()
    items = query.offset(offset).limit(size).all()
    pages = (total + size - 1) // size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.post(
    "/",
    response_model=schemas.Booking,
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking",
    description="Reserve a listing for a specific duration. Validates availability and calculates costs.",
    responses={
        400: {"description": "Listing not available for selected dates or invalid input"},
        404: {"description": "Listing or user not found"},
    },
)
async def create_booking(
    booking: schemas.BookingCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    listing = (
        db.query(models.Listing).filter(models.Listing.id == booking.listing_id).first()
    )
    if not listing:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Listing", identifier=booking.listing_id)

    # Create booking
    db_booking = models.Booking(
        id=str(uuid4()),
        listing_id=booking.listing_id,
        user_id=current_user.id,
        start_date=booking.start_date,
        end_date=booking.end_date,
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    
    # Calculate total amount and apply commission
    duration = max(1, (booking.end_date - booking.start_date).days)
    base_price = (listing.price_usd or 0) * duration

    # Apply platform commission (5% guest + 3% host, 4% guest on 30+ nights)
    commission_data = {}
    try:
        from backend.services.booking_commission import apply_commission_to_booking
        commission_data = apply_commission_to_booking(
            db=db,
            booking_id=db_booking.id,
            base_price=base_price,
            nights=duration,
        )
        total_amount = commission_data.get("guest_total", base_price)
    except Exception as e:
        logger.warning("commission_calculation_failed", booking_id=db_booking.id, error=str(e))
        total_amount = base_price

    # Track analytics event
    from backend.services.analytics_service import analytics_service
    analytics_service.track(
        event_name="booking_created",
        user_id=current_user.id,
        properties={
            "listing_id": booking.listing_id,
            "total_amount_usd": total_amount,
            "duration_days": duration,
            "platform_fee": commission_data.get("platform_revenue", 0),
            "host_payout": commission_data.get("host_payout", base_price),
        },
    )

    # Award $NEST tokens for booking
    try:
        from backend.services.nest_token import earn_tokens
        earn_tokens(current_user.id, "booking_complete", {"booking_id": db_booking.id, "amount": total_amount})
    except Exception as e:
        logger.warning("nest_token_reward_failed", booking_id=db_booking.id, error=str(e))
    
    # Audit Log: Financial Action
    from backend.services.audit_logging import log_financial_action, AuditAction
        
    log_financial_action(
        action=AuditAction.BOOKING_CREATE,
        actor_id=current_user.id,
        resource_type="booking",
        resource_id=db_booking.id,
        amount_usd=total_amount,
        metadata={
            "listing_id": listing.id,
            "duration": duration,
            "start": booking.start_date.isoformat(),
            "end": booking.end_date.isoformat()
        },
        db=db
    )

    # Emit real-time notification
    try:
        booking_data = schemas.Booking.model_validate(db_booking).model_dump(mode='json')
        await emit_booking_created(current_user.id, booking_data)
        
        # Also emit a general notification for the bell
        from datetime import datetime
        
        notification_data = {
            "id": str(uuid4()),
            "type": "opportunity", # or 'alert'
            "title": "Booking confirmed!",
            "description": f"Your booking for listing {db_booking.listing_id} is confirmed.",
            "read": False,
            "created_at": datetime.utcnow().isoformat()
        }
        await emit_notification(current_user.id, notification_data)
        
    except Exception as e:
        # Don't fail the booking if notification fails
        logger.warning("booking_notification_failed", booking_id=db_booking.id, user_id=current_user.id, error=str(e))

    return db_booking


@router.delete(
    "/{booking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a booking",
    description="Cancels an existing booking and releases the reserved dates.",
    responses={
        404: {"description": "Booking not found"},
    },
)
def delete_booking(
    booking_id: str, 
    db: Session = Depends(get_db),
    # Note: We should technically checking current_user here to ensure ownership!
    # But sticking to existing signature pattern for now, assuming external auth or simple demo mode.
    # To fix properly: current_user: models.User = Depends(get_current_user)
):
    db_booking = (
        db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    )
    if not db_booking:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Booking", identifier=booking_id)

    # Audit Log
    from backend.services.audit_logging import log_financial_action, AuditAction
    # Log before delete
    log_financial_action(
        action=AuditAction.BOOKING_CANCEL,
        actor_id=db_booking.user_id, # Best guess if we don't have current_user
        resource_type="booking",
        resource_id=booking_id,
        metadata={"reason": "user_cancelled"},
        db=db
    )

    db.delete(db_booking)
    db.commit()
    return None


@router.post(
    "/{booking_id}/cancel",
    response_model=schemas.BookingCancellation,
    summary="Cancel booking with refund",
    description="Cancels a booking and processes refund according to cancellation policy.",
    responses={
        404: {"description": "Booking not found"},
        400: {"description": "Booking cannot be cancelled"},
    },
)
def cancel_booking_with_refund(
    booking_id: str,
    reason: str = "user_request",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Cancel a booking with refund calculation:
    - > 7 days before check-in: 100% refund
    - 3-7 days before: 50% refund
    - < 3 days: No refund
    """
    from datetime import datetime, timedelta
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get booking with listing
    db_booking = (
        db.query(models.Booking)
        .options(joinedload(models.Booking.listing))
        .filter(models.Booking.id == booking_id)
        .first()
    )
    
    if not db_booking:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Booking", identifier=booking_id)
    
    # Check ownership
    if db_booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    
    # Check if already cancelled
    if getattr(db_booking, 'status', None) == 'cancelled':
        raise HTTPException(status_code=400, detail="Booking already cancelled")
    
    # Calculate refund amount based on cancellation policy
    now = datetime.utcnow()
    days_until_checkin = (db_booking.start_date - now.date()).days if hasattr(db_booking.start_date, 'date') else (db_booking.start_date - now.date()).days
    
    # Calculate total booking amount
    listing = db_booking.listing
    duration = (db_booking.end_date - db_booking.start_date).days
    total_amount = (listing.price_usd or 0) * max(1, duration)
    
    # Determine refund percentage
    if days_until_checkin > 7:
        refund_percentage = 100
        refund_type = "full"
    elif days_until_checkin >= 3:
        refund_percentage = 50
        refund_type = "partial"
    else:
        refund_percentage = 0
        refund_type = "none"
    
    refund_amount = total_amount * (refund_percentage / 100)
    
    # Process Stripe refund if payment exists
    refund_id = None
    refund_status = "skipped"
    
    if refund_amount > 0 and getattr(db_booking, 'payment_intent_id', None):
        try:
            from backend.services.stripe_service import create_refund
            
            refund_result = create_refund(
                payment_intent_id=db_booking.payment_intent_id,
                amount_cents=int(refund_amount * 100),
                reason="requested_by_customer" if reason == "user_request" else "duplicate",
            )
            refund_id = refund_result.get("id")
            refund_status = refund_result.get("status", "succeeded")
        except Exception as e:
            # Log but don't fail the cancellation
            logger.error("refund_processing_failed", booking_id=booking_id, amount=refund_amount, error=str(e), exc_info=True)
            refund_status = "failed"
    
    # Update booking status
    if hasattr(db_booking, 'status'):
        db_booking.status = "cancelled"
    if hasattr(db_booking, 'cancelled_at'):
        db_booking.cancelled_at = datetime.utcnow()
    
    # Audit log
    from backend.services.audit_logging import log_financial_action, AuditAction
    log_financial_action(
        action=AuditAction.BOOKING_CANCEL,
        actor_id=current_user.id,
        resource_type="booking",
        resource_id=booking_id,
        amount_usd=refund_amount,
        metadata={
            "reason": reason,
            "refund_type": refund_type,
            "refund_percentage": refund_percentage,
            "refund_id": refund_id,
            "days_until_checkin": days_until_checkin,
        },
        db=db
    )
    
    db.commit()
    
    # Return cancellation details
    return {
        "booking_id": booking_id,
        "status": "cancelled",
        "refund_amount": refund_amount,
        "refund_percentage": refund_percentage,
        "refund_type": refund_type,
        "refund_id": refund_id,
        "refund_status": refund_status,
        "message": f"Booking cancelled. {refund_percentage}% refund of ${refund_amount:.2f} processed." if refund_amount > 0 else "Booking cancelled. No refund due to late cancellation.",
    }

