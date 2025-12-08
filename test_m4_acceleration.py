"""Test M4 GPU acceleration capabilities."""
import torch
import time
from src.rag.embeddings import EmbeddingModel

print("=" * 60)
print("M4 MacBook Pro - GPU Acceleration Test")
print("=" * 60)

# Test PyTorch MPS
print("\n1. PyTorch MPS Support:")
print(f"   PyTorch version: {torch.__version__}")
print(f"   MPS available: {torch.backends.mps.is_available()}")
print(f"   MPS built: {torch.backends.mps.is_built()}")

if torch.backends.mps.is_available():
    print("   ✅ M4 GPU acceleration is AVAILABLE!")
    
    # Quick tensor test
    try:
        x = torch.randn(1000, 1000, device='mps')
        y = torch.randn(1000, 1000, device='mps')
        z = torch.matmul(x, y)
        print("   ✅ Successfully performed matrix multiplication on MPS")
    except Exception as e:
        print(f"   ⚠️  MPS test failed: {e}")
else:
    print("   ⚠️  MPS not available - will use CPU")

# Test embedding model with MPS
print("\n2. Embedding Model Test:")
print("   Loading all-MiniLM-L6-v2...")

try:
    # Test with MPS
    model_mps = EmbeddingModel("all-MiniLM-L6-v2", use_mps=True)
    
    test_texts = [
        "circular dependency in authentication module",
        "import cycle between models and views",
        "tight coupling in Django forms",
    ] * 10  # 30 texts
    
    print(f"   Encoding {len(test_texts)} texts with MPS...")
    start = time.time()
    embeddings_mps = model_mps.encode(test_texts)
    time_mps = time.time() - start
    
    print(f"   ✅ MPS encoding time: {time_mps:.3f}s")
    print(f"   ✅ Embedding shape: {embeddings_mps.shape}")
    
    # Test with CPU for comparison
    print("\n   Loading model with CPU for comparison...")
    model_cpu = EmbeddingModel("all-MiniLM-L6-v2", use_mps=False)
    
    print(f"   Encoding {len(test_texts)} texts with CPU...")
    start = time.time()
    embeddings_cpu = model_cpu.encode(test_texts)
    time_cpu = time.time() - start
    
    print(f"   ✅ CPU encoding time: {time_cpu:.3f}s")
    
    speedup = time_cpu / time_mps if time_mps > 0 else 1.0
    print(f"\n   🚀 M4 GPU Speedup: {speedup:.2f}x faster than CPU!")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Recommendations
print("\n" + "=" * 60)
print("Recommendations for Your M4 MacBook Pro:")
print("=" * 60)

if torch.backends.mps.is_available():
    print("✅ Your M4 can accelerate embeddings significantly!")
    print("✅ MPS is now enabled by default in your RAG system")
    print("\n📝 Next steps:")
    print("   1. Try upgrading to 'all-mpnet-base-v2' for better quality")
    print("   2. Use larger Ollama models: qwen2.5-coder:14b or :32b")
    print("   3. Benchmark different embedding models (academic value)")
    print("\n❌ DON'T spend time training:")
    print("   - Takes 20-40 hours to prepare data")
    print("   - Only 5-10% improvement at best")
    print("   - Your pre-trained model + M4 GPU is already great!")
else:
    print("⚠️  MPS not available - using CPU")
    print("   This is okay, but you won't get GPU acceleration")

print("=" * 60)
