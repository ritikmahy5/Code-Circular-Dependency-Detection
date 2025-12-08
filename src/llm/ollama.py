"""Ollama LLM integration for local deployment."""
import httpx
from .base import BaseLLM, LLMResponse


class OllamaLLM(BaseLLM):
    """Local Ollama LLM integration."""
    
    def __init__(
        self, 
        model: str = "codellama:13b",
        host: str = "http://localhost:11434",
        timeout: float = 120.0,
    ):
        self.model = model
        self.host = host
        self.timeout = timeout
    
    async def generate(self, prompt: str, system: str = "") -> LLMResponse:
        """Generate response using Ollama."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data.get("response", ""),
                model=self.model,
                tokens_used=data.get("eval_count", 0),
            )
    
    async def check_health(self) -> bool:
        """Check if Ollama is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.host}/api/tags")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            # Expected when Ollama is not running
            return False
        except Exception as e:
            # Unexpected error - log it for debugging
            print(f"Error checking Ollama status: {e}")
            return False
    
    async def list_models(self) -> list[str]:
        """List available models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.host}/api/tags")
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except (httpx.ConnectError, httpx.TimeoutException):
            # Expected when Ollama is not running
            return []
        except Exception as e:
            # Unexpected error - log it
            print(f"Error listing Ollama models: {e}")
            return []
