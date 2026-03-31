import json
import structlog
from typing import Any, Dict

from litellm import completion

from backend.errors import DependencyError
from backend.utils.resilience import CircuitBreaker, with_retry

logger = structlog.get_logger("nomadnest.ai_proxy")

ai_circuit_breaker = CircuitBreaker(
    name="AI_Proxy_LLM", failure_threshold=3, recovery_timeout=30
)


class AIProxyService:
    def __init__(self):
        self.model = "gemini/gemini-2.0-flash-exp"

    def process_request(self, endpoint: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches the request to the appropriate handler or generic prompt.
        """
        logger.info("ai_proxy_processing", endpoint=endpoint)

        # Dispatcher
        if endpoint == "ping":
            return {"text": "pong"}

        # Text generation handlers
        if endpoint in [
            "generateListingVibe",
            "generateItinerary",
            "answerListingQuestion",
            "generateListingDescription",
            "generateHealthSummary",
            "generateNeighborhoodVibe",
            "generateExoReport",
            "generateProposalSummary",
            "generateOperationalInsight",
            "recommendNetworkLocation",
            "generatePlatformHealthSummary",
            "draftReviewResponse",
            "summarizeApplication",
            "generateAutonomousAction",
        ]:
            return self._handle_text_generation(endpoint, body)

        # JSON-based structured outputs
        if endpoint in [
            "generateCommunityPosts",
            "generateCommunityEvents",
            "optimizeListing",
            "generateStagedImagePrompts",
            "generateMatchReport",
            "getLogisticsInfo",
            "suggestDynamicPrice",
            "checkPromotionReadiness",
            "generateWellnessPlan",
            "generateSerendipityFeed",
            "generateSerendipitySuggestions",
        ]:
            return self._handle_structured_generation(endpoint, body)

        return {
            "text": f"AI functionality for {endpoint} is cached/placeholder on server."
        }

    @ai_circuit_breaker
    @with_retry(retries=2, backoff_factor=1.0)
    def _call_llm(self, messages: list, system_instruction: str) -> str:
        # === INJECTION GUARD — scan user content before LLM processing ===
        try:
            from backend.services.injection_guard import injection_guard
            for msg in messages:
                if msg.get("role") == "user":
                    scan = injection_guard.scan(msg.get("content", ""), context="ai_proxy")
                    if scan.blocked:
                        logger.error("ai_proxy_injection_blocked", reason=scan.reason, score=scan.score)
                        return f"⚠️ Request blocked by security layer: {scan.reason}"
        except ImportError:
            pass  # Guard not installed, continue

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "system", "content": system_instruction}, *messages],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("litellm_error", error=str(e))
            raise DependencyError(service="Gemini", message=str(e))

    def _handle_text_generation(
        self, endpoint: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        prompts = {
            "generateListingVibe": "Write a short, 1-2 sentence 'vibe check' for this listing.",
            "generateItinerary": "Create a 3-day itinerary for this location.",
            "answerListingQuestion": "Answer this question about the listing.",
        }

        system_instruction = "You are a helpful AI assistant for NomadNest."
        user_content = f"Task: {prompts.get(endpoint, 'Help with this request')}\nContext: {json.dumps(body, default=str)}"

        try:
            content = self._call_llm(
                messages=[{"role": "user", "content": user_content}],
                system_instruction=system_instruction,
            )
            return {"text": content}
        except Exception as e:
            logger.error("llm_text_generation_error", endpoint=endpoint, error=str(e))
            # Fallback to avoid breaking frontend completely
            return {"text": "AI Service unavailable currently. Please try again later."}

    def _handle_structured_generation(
        self, endpoint: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Fallback for complex structured data to prevent UI crash
        if endpoint == "generateCommunityPosts":
            return {"posts": []}
        if endpoint == "generateSerendipityFeed":
            return {"feed": []}

        return {}


ai_proxy_service = AIProxyService()
