import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv
import google.generativeai as genai

# Load .env
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "AI analysis temporarily unavailable. Showing system assessment."
# Updated to the 2026 stable model default
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_TIMEOUT_SECONDS = 10 

class GeminiClient:
    """
    Client for Google Gemini API. Optimized for 2026 Gemini 2.5/3 models.
    """
    def __init__(self) -> None:
        self._api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        if self._api_key:
            try:
                genai.configure(api_key=self._api_key)
                # We don't pre-set the model here so we can inject 
                # different system prompts per call.
            except Exception as e:
                logger.warning("Gemini config failed: %s", e)
        else:
            logger.error("GEMINI_API_KEY missing from environment!")

    def _generate_sync(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Synchronous call using modern system_instruction parameter."""
        if not self._api_key:
            return None
        try:
            # Initialize model with specific system instructions
            model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                system_instruction=system_prompt
            )
            
            response = model.generate_content(user_prompt)
            
            if response and response.text:
                return response.text.strip()
            return None
        except Exception as e:
            logger.warning("Gemini generation failed: %s", e)
            return None

    def _is_quota_error(self, e: Exception) -> bool:
        msg = str(e).lower()
        return any(x in msg for x in ["quota", "429", "exhausted"])

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Async wrapper with timeout and fallback logic."""
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._generate_sync, system_prompt, user_prompt),
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
            return result if result else FALLBACK_MESSAGE
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("Request failed: %s", e)
            return FALLBACK_MESSAGE

    async def health_check(self) -> Tuple[bool, bool]:
        """Verifies API connectivity and quota."""
        if not self._api_key:
            return False, False
        try:
            # Quick check with minimal tokens
            result = await self.generate("You are a health checker.", "respond with 'ok'")
            return (result != FALLBACK_MESSAGE), False
        except Exception as e:
            return False, self._is_quota_error(e)