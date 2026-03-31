import structlog
import time
from typing import Dict, Any
from litellm import completion
from backend.config import settings
from backend.services.monitoring import AIMonitor

logger = structlog.get_logger("nomadnest.experience_gen")
ai_monitor = AIMonitor()


class ExperienceGenerator:
    """
    AI Service to generate promotional content for experiences.
    """

    def __init__(self, model: str = "gemini/gemini-pro"):
        self.model = model

    async def generate_promo_block(
        self, experience_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generates an SEO-optimized promotional block for an experience.
        """
        prompt = f"""
        Generate an SEO-optimized promotional block for the following experience:
        Name: {experience_data.get('name')}
        Type: {experience_data.get('type')}
        Theme: {experience_data.get('theme')}
        Mission: {experience_data.get('mission')}
        City: {experience_data.get('city')}
        
        The block should include:
        1. A catchy headline.
        2. A short engaging description (max 150 words).
        3. 3-5 key highlights/bullet points.
        4. Target keywords for SEO.
        
        Return the result as a JSON-compatible dictionary with keys: 'headline', 'description', 'highlights', 'keywords'.
        """

        start_time = time.time()
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

            duration = time.time() - start_time
            content = response.choices[0].message.content

            # Log metrics
            usage = getattr(response, "usage", None)
            total_tokens = usage.total_tokens if usage else 0

            ai_monitor.log_completion(
                model=self.model, tokens=total_tokens, duration=duration, success=True
            )

            # Parse response (assuming it returned valid JSON as requested)
            import json

            return json.loads(content)

        except Exception as e:
            duration = time.time() - start_time
            logger.error("promo_generation_failed", error=str(e))
            ai_monitor.log_completion(
                model=self.model,
                tokens=0,
                duration=duration,
                success=False,
                error=str(e),
            )
            return {
                "headline": f"Experience: {experience_data.get('name')}",
                "description": experience_data.get("mission")
                or "A unique NomadNest experience.",
                "highlights": [],
                "keywords": [],
            }


experience_generator = ExperienceGenerator()
