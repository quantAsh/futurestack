"""
Visa Wizard Service - Visa requirements and Schengen calculator.
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from uuid import uuid4

from backend import models

logger = structlog.get_logger(__name__)


# Schengen zone countries
SCHENGEN_COUNTRIES = {
    "AT": "Austria", "BE": "Belgium", "CZ": "Czech Republic", "DK": "Denmark",
    "EE": "Estonia", "FI": "Finland", "FR": "France", "DE": "Germany",
    "GR": "Greece", "HU": "Hungary", "IS": "Iceland", "IT": "Italy",
    "LV": "Latvia", "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg",
    "MT": "Malta", "NL": "Netherlands", "NO": "Norway", "PL": "Poland",
    "PT": "Portugal", "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain",
    "SE": "Sweden", "CH": "Switzerland",
}


class VisaWizardService:
    """
    Service for visa requirements and Schengen zone tracking.
    
    Features:
    - Get visa requirements by passport + destination
    - Calculate Schengen 90/180 day rule
    - Digital nomad visa information
    - Stay logging for Schengen calculator
    """
    
    def get_visa_requirements(
        self,
        db: Session,
        passport_country_code: str,
        destination_country_code: str,
    ) -> Optional[models.VisaRequirement]:
        """Get visa requirements for passport holder visiting destination."""
        return db.query(models.VisaRequirement).filter(
            models.VisaRequirement.passport_country_code == passport_country_code.upper(),
            models.VisaRequirement.destination_country_code == destination_country_code.upper(),
        ).first()
    
    def get_requirements_for_passport(
        self,
        db: Session,
        passport_country_code: str,
        visa_type_filter: Optional[str] = None,
    ) -> List[models.VisaRequirement]:
        """Get all visa requirements for a passport country."""
        query = db.query(models.VisaRequirement).filter(
            models.VisaRequirement.passport_country_code == passport_country_code.upper()
        )
        
        if visa_type_filter:
            query = query.filter(models.VisaRequirement.visa_type == visa_type_filter)
        
        return query.order_by(models.VisaRequirement.destination_country).all()
    
    def get_digital_nomad_visas(
        self,
        db: Session,
        passport_country_code: str,
    ) -> List[models.VisaRequirement]:
        """Get all countries offering digital nomad visas for this passport."""
        return db.query(models.VisaRequirement).filter(
            models.VisaRequirement.passport_country_code == passport_country_code.upper(),
            models.VisaRequirement.dnv_available == True,
        ).order_by(models.VisaRequirement.dnv_cost_usd.asc().nulls_last()).all()
    
    def is_schengen_country(self, country_code: str) -> bool:
        """Check if country is in Schengen zone."""
        return country_code.upper() in SCHENGEN_COUNTRIES
    
    def calculate_schengen_days(
        self,
        db: Session,
        user_id: str,
        reference_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate Schengen 90/180 day rule for user.
        
        Returns days used and remaining in the rolling 180-day window.
        """
        if reference_date is None:
            reference_date = datetime.utcnow()
        
        # Look back 180 days
        window_start = reference_date - timedelta(days=180)
        
        # Get all Schengen stays in window
        stays = db.query(models.SchengenStay).filter(
            models.SchengenStay.user_id == user_id,
            models.SchengenStay.entry_date >= window_start,
        ).order_by(models.SchengenStay.entry_date).all()
        
        total_days = 0
        stay_details = []
        
        for stay in stays:
            entry = max(stay.entry_date, window_start)
            exit_date = stay.exit_date or reference_date
            exit_date = min(exit_date, reference_date)
            
            if exit_date > entry:
                days = (exit_date - entry).days + 1
                total_days += days
                stay_details.append({
                    "country_code": stay.country_code,
                    "entry_date": stay.entry_date.isoformat(),
                    "exit_date": stay.exit_date.isoformat() if stay.exit_date else None,
                    "days_counted": days,
                })
        
        days_remaining = max(0, 90 - total_days)
        
        # Calculate when days will "free up"
        next_available_date = None
        if days_remaining == 0 and stays:
            # Find when first stay exits the 180-day window
            oldest_stay = stays[0]
            if oldest_stay.exit_date:
                next_available_date = oldest_stay.exit_date + timedelta(days=180)
        
        return {
            "days_used": total_days,
            "days_remaining": days_remaining,
            "max_days": 90,
            "window_days": 180,
            "reference_date": reference_date.isoformat(),
            "window_start": window_start.isoformat(),
            "stays": stay_details,
            "next_available_date": next_available_date.isoformat() if next_available_date else None,
            "status": "ok" if days_remaining > 14 else ("warning" if days_remaining > 0 else "exceeded"),
        }
    
    def log_schengen_stay(
        self,
        db: Session,
        user_id: str,
        country_code: str,
        entry_date: datetime,
        exit_date: Optional[datetime] = None,
    ) -> models.SchengenStay:
        """Log a Schengen zone stay for tracking."""
        if not self.is_schengen_country(country_code):
            raise ValueError(f"{country_code} is not a Schengen country")
        
        stay = models.SchengenStay(
            id=str(uuid4()),
            user_id=user_id,
            country_code=country_code.upper(),
            entry_date=entry_date,
            exit_date=exit_date,
        )
        db.add(stay)
        db.commit()
        db.refresh(stay)
        
        logger.info(
            "schengen_stay_logged",
            user_id=user_id,
            country=country_code,
            days=(exit_date - entry_date).days if exit_date else None,
        )
        
        return stay
    
    def update_schengen_stay(
        self,
        db: Session,
        user_id: str,
        stay_id: str,
        exit_date: datetime,
    ) -> Optional[models.SchengenStay]:
        """Update a Schengen stay with exit date."""
        stay = db.query(models.SchengenStay).filter(
            models.SchengenStay.id == stay_id,
            models.SchengenStay.user_id == user_id,
        ).first()
        
        if stay:
            stay.exit_date = exit_date
            db.commit()
            db.refresh(stay)
        
        return stay
    
    def get_user_stays(
        self,
        db: Session,
        user_id: str,
        limit: int = 50,
    ) -> List[models.SchengenStay]:
        """Get user's Schengen stay history."""
        return db.query(models.SchengenStay).filter(
            models.SchengenStay.user_id == user_id
        ).order_by(models.SchengenStay.entry_date.desc()).limit(limit).all()
    
    def can_stay(
        self,
        db: Session,
        user_id: str,
        planned_days: int,
    ) -> Dict[str, Any]:
        """Check if user can stay for planned number of days."""
        calc = self.calculate_schengen_days(db, user_id)
        
        can_stay = calc["days_remaining"] >= planned_days
        
        return {
            "can_stay": can_stay,
            "planned_days": planned_days,
            "days_remaining": calc["days_remaining"],
            "recommendation": (
                f"You can stay up to {calc['days_remaining']} more days in the Schengen zone."
                if can_stay
                else f"You've used {calc['days_used']} of 90 days. Wait until {calc.get('next_available_date', 'unknown')} for more days."
            ),
        }


# Singleton
visa_wizard_service = VisaWizardService()
