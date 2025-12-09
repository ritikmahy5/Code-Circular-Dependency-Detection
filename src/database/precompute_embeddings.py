#!/usr/bin/env python3
"""
Pre-compute embeddings for the persistent database.
This makes RAG initialization much faster by avoiding runtime embedding computation.

Run this once after building the database:
    python -m src.database.precompute_embeddings
"""
import pickle
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def precompute_embeddings(db_path: Path = None, batch_size: int = None):
    """Pre-compute embeddings for all code chunks in the persistent database.
    
    Args:
        db_path: Path to persistent database directory
        batch_size: Batch size for encoding (auto-optimized for GPU if None)
    """
    
    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "persistent_db"
    
    chunks_file = db_path / "code_chunks.pkl"
    embeddings_file = db_path / "code_embeddings.pkl"
    
    if not chunks_file.exists():
        logger.error(f"Code chunks file not found: {chunks_file}")
        return False
    
    # Load chunks
    logger.info(f"Loading code chunks from {chunks_file}...")
    with open(chunks_file, 'rb') as f:
        chunks = pickle.load(f)
    
    logger.info(f"Loaded {len(chunks):,} chunks")
    
    # Initialize embedding model (auto-detect GPU if available)
    logger.info("Initializing embedding model (GPU will be used if available)...")
    from src.rag.embeddings import EmbeddingModel
    encoder = EmbeddingModel(device="auto")
    
    # Auto-optimize batch size based on device
    if batch_size is None:
        if encoder.device == "cuda":
            batch_size = 2000  # Very large batches for T4 GPU (was 1000)
            logger.info("🚀 Using T4 GPU acceleration with batch size 2000")
        else:
            batch_size = 500   # Moderate batches for CPU
            logger.info("💻 Using CPU with batch size 500")
    
    # Compute embeddings in batches
    logger.info(f"Computing embeddings (batch size: {batch_size})...")
    all_embeddings = []
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c.to_embedding_text() for c in batch]
        
        # Use optimized batch size (None = auto-optimize)
        batch_embeddings = encoder.encode(texts, batch_size=None, show_progress=True)
        all_embeddings.extend(batch_embeddings.tolist())
        
        progress = min(i + batch_size, len(chunks))
        logger.info(f"  Processed {progress:,} / {len(chunks):,} chunks ({100*progress/len(chunks):.1f}%)")
    
    # Save embeddings
    logger.info(f"Saving embeddings to {embeddings_file}...")
    with open(embeddings_file, 'wb') as f:
        pickle.dump(all_embeddings, f)
    
    logger.info(f"✅ Successfully pre-computed {len(all_embeddings):,} embeddings")
    logger.info(f"   File size: {embeddings_file.stat().st_size / (1024*1024):.1f} MB")
    
    return True


if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 60)
    print("Pre-computing Embeddings for Persistent Database")
    print("=" * 60 + "\n")
    
    success = precompute_embeddings()
    
    if success:
        print("\n✅ Embeddings pre-computed successfully!")
        print("   RAG will now load much faster.")
    else:
        print("\n❌ Failed to pre-compute embeddings")
        sys.exit(1)
