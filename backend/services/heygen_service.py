"""
HeyGen Avatar Service.
Handles token generation for the Interactive Avatar Streaming SDK.
"""
import requests
import time
import structlog
from backend.config import settings

HEYGEN_API_URL = "https://api.heygen.com"

class HeyGenService:
    def __init__(self):
        self.api_key = settings.HEYGEN_API_KEY
        self.enabled = bool(self.api_key)

    def get_access_token(self) -> dict:
        """
        Generate a temporary access token for the client SDK.
        """
        if not self.enabled:
            return {
                "token": "mock_heygen_token",
                "is_mock": True,
                "expires_in": 3600
            }

        try:
            response = requests.post(
                f"{HEYGEN_API_URL}/v1/streaming.create_token",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "token": data["data"]["token"],
                "is_mock": False,
                # Default expiration usually short (token is for starting session)
                "expires_in": 3600
            }
            
        except Exception as e:
            structlog.get_logger("nomadnest.heygen").error("heygen_token_error", error=str(e))
            return {"error": str(e), "is_mock": True}

heygen_service = HeyGenService()
