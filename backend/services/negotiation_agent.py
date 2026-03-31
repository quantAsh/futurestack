import json
import time
import structlog
from typing import Dict, Any, List, Optional
from backend.config import settings
from backend import models
from backend.services.ai_metering import log_ai_usage

logger = structlog.get_logger(__name__)

try:
    import openai
except ImportError:
    openai = None

class NegotiationAgent:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = "gpt-4o"  # Use capable model for reasoning
        if self.api_key and openai:
            self.client = openai.OpenAI(api_key=self.api_key)
            self.mode = "live"
        else:
            self.mode = "mock"
            logger.warning("NegotiationAgent: No API Key or openai lib. Falling back to MOCK mode.")

    def negotiate_price(
        self, 
        listing: models.Listing, 
        user_offer: float, 
        stay_duration: int,
        history: List[Dict[str, Any]] = [],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Decide on a negotiation action: accept, counter, or reject.
        """
        if self.mode == "mock":
            return self._mock_logic(listing.price_usd, user_offer)

        system_prompt = f"""
        You are the Property Manager for '{listing.name}'.
        Your Goal: Maximize revenue while maintaining high occupancy. You prefer longer stays.
        
        Listing Details:
        - Base Price: ${listing.price_usd}/month
        - Minimum Stay: 30 days
        
        Negotiation Policy:
        1. If offer is > 90% of price, ACCEPT.
        2. If offer is < 70% of price, REJECT (be polite but firm).
        3. If between 70-90%, COUNTER. Use the stay duration to justify flexibility.
           - If duration > 60 days, be more flexible.
           - If duration < 30 days, be less flexible.
        
        Output JSON ONLY:
        {{
            "action": "accept" | "counter" | "reject",
            "price": float (final price or counter offer),
            "message": "A persuasive, professional message to the tenant."
        }}
        """

        user_message = f"""
        Tenant Offer: ${user_offer}
        Stay Duration: {stay_duration} days
        
        History:
        {json.dumps(history, indent=2)}
        """

        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Log AI usage
            try:
                log_ai_usage(
                    endpoint="negotiations",
                    model=self.model,
                    provider="openai",
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    latency_ms=latency_ms,
                    user_id=user_id,
                    success=True,
                )
            except Exception as e:
                logger.warning(f"AI metering failed: {e}")
            
            return json.loads(content)
        except Exception as e:
            logger.error(f"Negotiation Agent Error: {e}")
            # Log failed request
            try:
                log_ai_usage(
                    endpoint="negotiations",
                    model=self.model,
                    provider="openai",
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=int((time.time() - start_time) * 1000),
                    user_id=user_id,
                    success=False,
                    error_message=str(e),
                )
            except Exception:
                pass
            # Fallback to safe logic
            return self._mock_logic(listing.price_usd, user_offer)

    def _mock_logic(self, original_price: float, offered_price: float) -> Dict[str, Any]:
        """Fallback deterministic logic if AI fails."""
        ratio = offered_price / original_price
        if ratio >= 0.9:
            return {"action": "accept", "price": offered_price, "message": "Offer accepted via fallback logic."}
        elif ratio < 0.7:
             return {"action": "reject", "price": original_price * 0.8, "message": "Offer too low (fallback)."}
        else:
             counter = (original_price + offered_price) / 2
             return {"action": "counter", "price": counter, "message": f"Counter offer: ${counter} (fallback)."}

# Singleton instance
negotiation_agent = NegotiationAgent()
