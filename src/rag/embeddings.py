"""Embedding model wrapper."""
from typing import Optional
import numpy as np


class EmbeddingModel:
    """Wrapper for sentence transformer embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", use_mps: bool = True):
        self.model_name = model_name
        self._model = None
        self.device = self._get_device(use_mps)
    
    def _get_device(self, use_mps: bool) -> str:
        """Determine best device (MPS for Apple Silicon, CPU otherwise)."""
        if use_mps:
            try:
                import torch
                if torch.backends.mps.is_available():
                    return "mps"  # Apple Silicon GPU acceleration
            except ImportError:
                pass
        return "cpu"
    
    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)
            if self.device == "mps":
                print(f"✅ Using Apple Silicon GPU acceleration for {self.model_name}")
        return self._model
    
    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode texts to embeddings."""
        return self.model.encode(texts, convert_to_numpy=True)
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single text."""
        return self.encode([text])[0]
