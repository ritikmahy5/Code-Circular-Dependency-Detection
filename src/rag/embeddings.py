"""Embedding model wrapper."""
from typing import Optional
import numpy as np


class EmbeddingModel:
    """Wrapper for sentence transformer embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "auto"):
        """
        Initialize embedding model.
        
        Args:
            model_name: Name of the sentence-transformer model
            device: "auto", "cpu", "cuda", or "mps"
                   Note: MPS (Apple Silicon) can have issues with some models,
                   so we default to CPU for stability.
        """
        self.model_name = model_name
        self._model = None
        self.device = self._get_device(device)
    
    def _get_device(self, device: str) -> str:
        """Determine best device for embeddings."""
        if device == "cpu":
            return "cpu"
        
        if device == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
            except ImportError:
                pass
            return "cpu"
        
        if device == "mps":
            # MPS can have issues with meta tensors, so we check carefully
            try:
                import torch
                if torch.backends.mps.is_available():
                    # Test if MPS actually works
                    try:
                        test_tensor = torch.tensor([1.0]).to("mps")
                        del test_tensor
                        return "mps"
                    except Exception:
                        print("⚠️ MPS available but not working, falling back to CPU")
                        return "cpu"
            except ImportError:
                pass
            return "cpu"
        
        # Auto mode - prefer CPU for stability
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"
    
    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                # Load model on target device
                print(f"Loading embedding model: {self.model_name} on {self.device}...")
                try:
                    # Try loading on target device
                    self._model = SentenceTransformer(self.model_name, device=self.device)
                    print(f"✅ Embedding model loaded on {self.device}")
                except Exception as e:
                    # Fallback to CPU if GPU loading fails
                    print(f"⚠️ Could not load on {self.device}, falling back to CPU: {e}")
                    self.device = "cpu"
                    self._model = SentenceTransformer(self.model_name, device="cpu")
                    print(f"✅ Embedding model loaded on CPU")
                    
            except Exception as e:
                raise RuntimeError(f"Failed to load embedding model: {e}")
        
        return self._model
    
    def encode(self, texts: list[str], batch_size: int = None, show_progress: bool = False) -> np.ndarray:
        """
        Encode texts to embeddings.
        
        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding (auto-optimized for GPU if None)
            show_progress: Show progress bar
            
        Returns:
            Numpy array of embeddings
        """
        if not texts:
            return np.array([])
        
        # Optimize batch size for GPU (larger batches = better GPU utilization)
        if batch_size is None:
            if self.device == "cuda":
                batch_size = 128  # Larger batches for GPU
            else:
                batch_size = 32   # Smaller batches for CPU
        
        return self.model.encode(
            texts, 
            convert_to_numpy=True,
            batch_size=batch_size,
            show_progress_bar=show_progress
        )
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single text."""
        return self.encode([text])[0]
