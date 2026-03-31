"""
ElevenLabs Voice Service.
Handles Text-to-Speech (TTS) using ElevenLabs API.
Includes fallback/mock mode for development.
"""
import requests
import os
import structlog
from backend.config import settings
from typing import Generator, Iterator

logger = structlog.get_logger("nomadnest.voice")

# Default NomadNest "Concierge" Voice ID (ElevenLabs default 'Adam' or similar)
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" voice (classic choice)
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"

class VoiceService:
    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.enabled = bool(self.api_key)

    def generate_audio_stream(self, text: str, voice_id: str = DEFAULT_VOICE_ID) -> Iterator[bytes]:
        """
        Generate audio stream from text using ElevenLabs.
        Returns a generator of bytes (mp3 chunks).
        """
        if not self.enabled:
            logger.debug("voice_mock_mode", text_preview=text[:50])
            return iter([b"mock_audio_data"])

        url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}/stream"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        try:
            response = requests.post(url, json=data, headers=headers, stream=True)
            response.raise_for_status()
            
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
                    
        except Exception as e:
            logger.error("voice_generation_failed", error=str(e))
            yield b""

voice_service = VoiceService()

