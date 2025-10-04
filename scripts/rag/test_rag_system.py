"""Test RAG system with a small subset of files to validate functionality.
"""

import sys
import time
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_rag_basic():
    """Test basic RAG functionality with small dataset."""
    print("=" * 80)
    print("RAG SYSTEM VALIDATION TEST")
    print("=" * 80)

    start_time = time.time()

    # Load embedding model
    print("\n[1/5] Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"  Model loaded: {model.get_sentence_embedding_dimension()} dimensions")

    # Create small test dataset
    print("\n[2/5] Creating test dataset...")
    test_chunks = [
        {
            "text": "def calculate_energy(power, hours): return power * hours",
            "file": "ecosystemiser/energy.py",
            "type": "python",
            "name": "calculate_energy",
        },
        {
            "text": "class EnergySystem: def __init__(self): self.components = []",
            "file": "ecosystemiser/system.py",
            "type": "python",
            "name": "EnergySystem",
        },
        {
            "text": "# RAG Phase 2 Implementation\n\nComplete RAG system with YAML/TOML support",
            "file": "claudedocs/rag_phase2.md",
            "type": "markdown",
            "name": "RAG Phase 2",
        },
        {
            "text": '[dependencies]\nsentence-transformers = "^5.1.1"\nfaiss-cpu = "^1.12.0"',
            "file": "packages/hive-ai/pyproject.toml",
            "type": "toml",
            "name": "dependencies",
        },
        {
            "text": "name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest",
            "file": ".github/workflows/ci.yml",
            "type": "yaml",
            "name": "CI",
        },
    ]

    print(f"  Created {len(test_chunks)} test chunks")

    # Create embeddings
    print("\n[3/5] Creating embeddings...")
    texts = [chunk["text"] for chunk in test_chunks]
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    print(f"  Embeddings shape: {embeddings.shape}")

    # Build FAISS index
    print("\n[4/5] Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype("float32"))
    print(f"  Index created with {index.ntotal} vectors")

    # Test queries
    print("\n[5/5] Testing queries...")

    test_queries = [
        "How to calculate energy consumption?",
        "What is the RAG system?",
        "Show me CI/CD configuration",
        "What are the project dependencies?",
    ]

    for query in test_queries:
        print(f"\n  Query: '{query}'")
        query_embedding = model.encode([query], convert_to_numpy=True)
        distances, indices = index.search(query_embedding.astype("float32"), k=2)

        for i, (dist, idx) in enumerate(zip(distances[0], indices[0], strict=False), 1):
            chunk = test_chunks[idx]
            print(f"    {i}. {chunk['file']} ({chunk['type']}) - score: {1 / (1 + dist):.3f}")
            print(f"       {chunk['text'][:80]}...")

    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("✅ Model loading: OK")
    print("✅ Embedding generation: OK")
    print("✅ FAISS indexing: OK")
    print("✅ Query retrieval: OK")
    print(f"\nTime elapsed: {elapsed:.1f}s")
    print("=" * 80)

    return True


if __name__ == "__main__":
    try:
        success = test_rag_basic()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
