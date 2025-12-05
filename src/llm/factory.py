"""LLM factory for environment-based selection."""
import os
from .base import BaseLLM
from .ollama import OllamaLLM


def get_llm(env: str | None = None) -> BaseLLM:
    """Get an LLM instance based on environment.
    
    Args:
        env: Environment name ('local', 'gcp', 'dev'). 
             If None, uses ENVIRONMENT env var.
    
    Returns:
        BaseLLM instance
    """
    if env is None:
        env = os.getenv("ENVIRONMENT", "local")
    
    if env in ("local", "gcp"):
        return OllamaLLM(
            model=os.getenv("OLLAMA_MODEL", "codellama:13b"),
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        )
    elif env == "dev":
        # For development, could use Claude API
        # But since final must be local, we just use Ollama
        return OllamaLLM()
    else:
        raise ValueError(f"Unknown environment: {env}")
