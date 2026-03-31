"""
ML Pricing Engine - Dynamic pricing based on historical data.
Replaces static seasonality multipliers with data-driven predictions.
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import structlog
import math

logger = structlog.get_logger(__name__)


@dataclass
class PricingFeatures:
    """Features used for price prediction."""
    base_price: float
    day_of_week: int  # 0-6
    month: int  # 1-12
    days_until_booking: int
    stay_duration: int
    occupancy_rate: float  # 0-1, current hub occupancy
    competitor_avg_price: Optional[float] = None
    local_events: List[str] = None
    is_holiday: bool = False
    is_weekend: bool = False
    demand_score: float = 0.5  # 0-1, based on recent searches


class MLPricingEngine:
    """
    ML-based dynamic pricing engine.
    
    In production, this would use a trained model (XGBoost, LightGBM, or neural net).
    This implementation uses a sophisticated rule-based approach that can be
    replaced with an actual ML model when training data is available.
    """
    
    def __init__(self):
        self.model_path = os.getenv("PRICING_MODEL_PATH")
        self.model = None
        
        # Load model if available
        if self.model_path and os.path.exists(self.model_path):
            self._load_model()
        
        # Learned coefficients (would come from training)
        self.coefficients = {
            "day_of_week": {0: 1.0, 1: 0.95, 2: 0.95, 3: 1.0, 4: 1.1, 5: 1.2, 6: 1.15},
            "month_seasonality": {
                1: 0.8, 2: 0.85, 3: 1.0, 4: 1.1, 5: 1.15, 6: 1.3,
                7: 1.4, 8: 1.35, 9: 1.1, 10: 1.0, 11: 0.9, 12: 1.2,
            },
            "booking_lead_time": {
                (0, 3): 1.3,    # Last minute premium
                (4, 7): 1.2,
                (8, 14): 1.1,
                (15, 30): 1.0,
                (31, 60): 0.95,
                (61, 999): 0.9,
            },
            "stay_duration_discount": {
                (1, 3): 1.0,
                (4, 7): 0.95,
                (8, 14): 0.9,
                (15, 30): 0.85,
                (31, 999): 0.8,
            },
            "occupancy_multiplier": lambda x: 1 + (x - 0.5) * 0.4,  # 0.8 at 0%, 1.2 at 100%
            "demand_multiplier": lambda x: 0.9 + x * 0.2,  # 0.9 at 0 demand, 1.1 at full
        }
    
    def _load_model(self):
        """Load pre-trained model."""
        try:
            import joblib
            self.model = joblib.load(self.model_path)
            logger.info(f"Loaded pricing model from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load model: {e}, using rule-based pricing")
    
    def predict(self, features: PricingFeatures) -> Dict:
        """
        Predict optimal price for given features.
        
        Returns:
            Dict with predicted_price, confidence, and breakdown
        """
        if self.model:
            return self._ml_predict(features)
        else:
            return self._rule_based_predict(features)
    
    def _ml_predict(self, features: PricingFeatures) -> Dict:
        """Use ML model for prediction."""
        try:
            import numpy as np
            
            # Build feature vector
            X = np.array([[
                features.base_price,
                features.day_of_week,
                features.month,
                features.days_until_booking,
                features.stay_duration,
                features.occupancy_rate,
                features.demand_score,
                1 if features.is_weekend else 0,
                1 if features.is_holiday else 0,
            ]])
            
            predicted_price = self.model.predict(X)[0]
            
            return {
                "predicted_price": round(predicted_price, 2),
                "confidence": 0.85,  # Would come from model
                "method": "ml_model",
                "model_version": getattr(self.model, "version", "unknown"),
            }
        
        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return self._rule_based_predict(features)
    
    def _rule_based_predict(self, features: PricingFeatures) -> Dict:
        """Rule-based prediction with transparent multipliers."""
        base = features.base_price
        breakdown = {"base_price": base}
        
        # Day of week adjustment
        dow_mult = self.coefficients["day_of_week"].get(features.day_of_week, 1.0)
        breakdown["day_of_week"] = f"{dow_mult}x"
        
        # Seasonality adjustment
        month_mult = self.coefficients["month_seasonality"].get(features.month, 1.0)
        breakdown["seasonality"] = f"{month_mult}x"
        
        # Lead time adjustment
        lead_mult = 1.0
        for (low, high), mult in self.coefficients["booking_lead_time"].items():
            if low <= features.days_until_booking <= high:
                lead_mult = mult
                break
        breakdown["lead_time"] = f"{lead_mult}x"
        
        # Stay duration discount
        stay_mult = 1.0
        for (low, high), mult in self.coefficients["stay_duration_discount"].items():
            if low <= features.stay_duration <= high:
                stay_mult = mult
                break
        breakdown["duration_discount"] = f"{stay_mult}x"
        
        # Occupancy adjustment
        occ_mult = self.coefficients["occupancy_multiplier"](features.occupancy_rate)
        breakdown["occupancy"] = f"{round(occ_mult, 2)}x"
        
        # Demand adjustment
        demand_mult = self.coefficients["demand_multiplier"](features.demand_score)
        breakdown["demand"] = f"{round(demand_mult, 2)}x"
        
        # Event premium
        event_mult = 1.0
        if features.local_events and len(features.local_events) > 0:
            event_mult = 1.1 + 0.05 * len(features.local_events)
            breakdown["events"] = f"{round(event_mult, 2)}x ({len(features.local_events)} events)"
        
        # Holiday premium
        holiday_mult = 1.25 if features.is_holiday else 1.0
        if features.is_holiday:
            breakdown["holiday"] = "1.25x"
        
        # Calculate final price
        final_mult = dow_mult * month_mult * lead_mult * stay_mult * occ_mult * demand_mult * event_mult * holiday_mult
        predicted_price = base * final_mult
        
        # Apply floor and ceiling
        min_price = base * 0.6
        max_price = base * 2.0
        predicted_price = max(min_price, min(max_price, predicted_price))
        
        breakdown["total_multiplier"] = f"{round(final_mult, 2)}x"
        
        return {
            "predicted_price": round(predicted_price, 2),
            "confidence": 0.7,
            "method": "rule_based",
            "breakdown": breakdown,
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
        }
    
    def get_price_range(
        self,
        base_price: float,
        check_in: datetime,
        check_out: datetime,
        occupancy_rate: float = 0.5,
    ) -> Dict:
        """
        Get price prediction for a date range.
        
        Returns per-night prices and total.
        """
        days = (check_out - check_in).days
        daily_prices = []
        
        for i in range(days):
            date = check_in + timedelta(days=i)
            
            features = PricingFeatures(
                base_price=base_price,
                day_of_week=date.weekday(),
                month=date.month,
                days_until_booking=(date - datetime.now()).days,
                stay_duration=days,
                occupancy_rate=occupancy_rate,
                is_weekend=date.weekday() >= 5,
            )
            
            prediction = self.predict(features)
            daily_prices.append({
                "date": date.strftime("%Y-%m-%d"),
                "price": prediction["predicted_price"],
            })
        
        total = sum(p["price"] for p in daily_prices)
        avg = total / len(daily_prices) if daily_prices else base_price
        
        return {
            "total_price": round(total, 2),
            "average_per_night": round(avg, 2),
            "nights": days,
            "daily_prices": daily_prices,
        }


# Singleton instance
pricing_engine = MLPricingEngine()


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def get_dynamic_price(
    base_price: float,
    check_in_date: datetime,
    stay_nights: int,
    occupancy_rate: float = 0.5,
    demand_score: float = 0.5,
    local_events: List[str] = None,
) -> Dict:
    """Get dynamically priced rate."""
    features = PricingFeatures(
        base_price=base_price,
        day_of_week=check_in_date.weekday(),
        month=check_in_date.month,
        days_until_booking=(check_in_date - datetime.now()).days,
        stay_duration=stay_nights,
        occupancy_rate=occupancy_rate,
        demand_score=demand_score,
        local_events=local_events or [],
        is_weekend=check_in_date.weekday() >= 5,
    )
    
    return pricing_engine.predict(features)


# ============================================
# EVENT-AWARE PRICING (DATABASE INTEGRATION)
# ============================================

def get_events_for_pricing(
    location: str,
    check_in: datetime,
    check_out: datetime,
) -> List[Dict]:
    """
    Fetch events from database that overlap with the stay dates.
    Used for pricing adjustments.
    """
    from backend.database import SessionLocal
    from backend import models
    
    db = SessionLocal()
    try:
        events = db.query(models.Event).filter(
            models.Event.location.ilike(f"%{location}%"),
            models.Event.start_date <= check_out,
            models.Event.is_active == True,
        ).all()
        
        # Filter events that actually overlap
        overlapping = []
        for event in events:
            event_end = event.end_date or event.start_date
            if event.start_date <= check_out and event_end >= check_in:
                overlapping.append({
                    "name": event.name,
                    "type": event.event_type,
                    "impact_percent": event.price_impact_percent,
                    "start_date": event.start_date.isoformat(),
                })
        
        return overlapping
    finally:
        db.close()


def get_enhanced_dynamic_price(
    base_price: float,
    check_in_date: datetime,
    stay_nights: int,
    location: str,
    occupancy_rate: float = 0.5,
    demand_score: float = 0.5,
) -> Dict:
    """
    Get dynamically priced rate with automatic event lookup.
    
    This is the recommended function for production use as it
    automatically fetches relevant events from the database.
    """
    check_out_date = check_in_date + timedelta(days=stay_nights)
    
    # Fetch events from database
    events = get_events_for_pricing(location, check_in_date, check_out_date)
    event_names = [e["name"] for e in events]
    
    # Calculate total event impact
    total_event_impact = sum(e.get("impact_percent", 0) for e in events)
    
    features = PricingFeatures(
        base_price=base_price,
        day_of_week=check_in_date.weekday(),
        month=check_in_date.month,
        days_until_booking=(check_in_date - datetime.now()).days,
        stay_duration=stay_nights,
        occupancy_rate=occupancy_rate,
        demand_score=demand_score,
        local_events=event_names,
        is_weekend=check_in_date.weekday() >= 5,
    )
    
    result = pricing_engine.predict(features)
    
    # Add event details to result
    result["events"] = events
    result["event_impact_percent"] = total_event_impact
    
    return result

