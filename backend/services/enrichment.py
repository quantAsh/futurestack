import httpx
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger(__name__)

def check_liveness(url: str, timeout: float = 5.0) -> bool:
    """
    Check if a URL is accessible. Return True if status is 200-299.
    """
    if not url:
        return False
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.head(url) # Use HEAD to save bandwidth
            if resp.status_code >= 400:
                # Some servers reject HEAD, retry with GET
                resp = client.get(url) 
            return 200 <= resp.status_code < 300
    except Exception as e:
        logger.warning(f"Liveness check failed for {url}: {e}")
        return False

def generate_vibe_tags(description: str, amenities: List[str]) -> List[str]:
    """
    Generate 'Vibe Tags' based on content analysis.
    In a full version, this would call LiteLLM/GPT-4.
    """
    tags = []
    desc_lower = description.lower()
    
    # Heuristic tagging (Simulating AI)
    if "quiet" in desc_lower or "peaceful" in desc_lower:
        tags.append("Deep Focus")
    if "community" in desc_lower or "social" in desc_lower or "events" in desc_lower:
        tags.append("Social Butterfly")
    if any(a.lower() in ["surf", "yoga", "hike"] for a in amenities):
        tags.append("Active Lifestyle")
    if "luxury" in desc_lower or "villa" in desc_lower:
        tags.append("Nomad Lux")
        
    return list(set(tags))

def calculate_nomad_score(price: Optional[float], internet_speed: Optional[int], amenities: List[str]) -> int:
    """
    Calculate a 0-100 nomad score.
    """
    score = 60 # Base score
    
    if internet_speed and internet_speed > 50:
        score += 10
    
    if "co-working" in [a.lower() for a in amenities] or "desk" in [a.lower() for a in amenities]:
        score += 15
        
    if price:
        if price < 1500: # Affordable
            score += 10
        elif price > 4000: # Expensive
            score -= 10
            
    return min(100, max(0, score))
