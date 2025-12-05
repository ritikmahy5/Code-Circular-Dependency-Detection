"""Base LLM interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from an LLM."""
    content: str
    model: str
    tokens_used: int = 0


class BaseLLM(ABC):
    """Abstract base class for LLM integrations."""
    
    @abstractmethod
    async def generate(self, prompt: str, system: str = "") -> LLMResponse:
        """Generate a response from the LLM."""
        pass
    
    def generate_sync(self, prompt: str, system: str = "") -> LLMResponse:
        """Synchronous wrapper for generate."""
        import asyncio
        return asyncio.run(self.generate(prompt, system))
