import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
import httpx

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for communicating with Ollama API"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:latest"):
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=120)

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a complete response from Ollama"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Lower temperature for more consistent JSON
                    "top_p": 0.9
                }
            }

            if system_prompt:
                payload["system"] = system_prompt

            logger.info(f"Sending request to Ollama at {self.base_url}")
            response = await self.client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()

            result = response.json()
            response_text = result.get("response", "")

            if not response_text:
                logger.warning("Ollama returned empty response")
                return "Error: Empty response from Ollama"

            return response_text

        except httpx.ConnectError as e:
            logger.error(f"Connection error to Ollama: {e}")
            return "Error: Cannot connect to Ollama. Please ensure Ollama is running on localhost:11434"
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error from Ollama: {e}")
            return "Error: Ollama request timed out"
        except Exception as e:
            logger.error(f"Error generating response from Ollama: {e}")
            return f"Error: Unable to generate response - {str(e)}"

    async def generate_streaming_response(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming response from Ollama"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": True
            }

            if system_prompt:
                payload["system"] = system_prompt

            async with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Error streaming response from Ollama: {e}")
            yield f"Error: Unable to stream response - {str(e)}"

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Create a singleton instance
ollama_client = OllamaClient()