"""Demo script for Hive RAG system.

Demonstrates end-to-end RAG functionality:
1. Chunk code files
2. Generate embeddings
3. Index for retrieval
4. Perform hybrid search
5. Generate structured context
"""

import sys
from pathlib import Path

# Add hive-ai to path for demo
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hive_ai.rag import EnhancedRAGRetriever, HierarchicalChunker, RetrievalQuery


def main():
    """Run RAG demo."""
    print("=" * 80)
    print("Hive RAG Demo - Phase 1 Implementation")
    print("=" * 80)

    # Step 1: Chunk code files
    print("\n[1/5] Chunking code files...")
    chunker = HierarchicalChunker()

    # Chunk a few files from hive-ai as demo
    rag_dir = Path(__file__).parent.parent / "src" / "hive_ai" / "rag",
    chunks = chunker.chunk_directory(rag_dir, recursive=False)

    print(f"  ✅ Chunked {len(chunks)} code units")
    print(f"  📊 Chunk types: { {c.chunk_type.value for c in chunks} }")

    # Step 2: Initialize retriever and index
    print("\n[2/5] Initializing RAG retriever...")
    retriever = EnhancedRAGRetriever()

    print("  ⏳ Generating embeddings and indexing (this may take a moment)...")
    retriever.index_chunks(chunks)

    stats = retriever.get_stats()
    print(f"  ✅ Indexed {stats['vector_store']['total_chunks']} chunks")
    print(f"  📐 Embedding dimension: {stats['embedding_generator']['embedding_dim']}")

    # Step 3: Perform simple search
    print("\n[3/5] Testing semantic search...")
    query = "code chunking and AST parsing",

    results = retriever.retrieve(query)

    print(f"  Query: '{query}'")
    print(f"  Results: {len(results)} chunks")

    for i, result in enumerate(results[:3], 1):
        print(f"\n  [{i}] Score: {result.score:.3f} | Method: {result.retrieval_method}")
        print(f"      {result.chunk.file_path}:{result.chunk.signature}")
        print(f"      Type: {result.chunk.chunk_type.value}")

    # Step 4: Test hybrid search with filters
    print("\n[4/5] Testing hybrid search with filters...")

    hybrid_query = RetrievalQuery(
        query="vector search and embeddings",
        k=5,
        use_hybrid=True,
        semantic_weight=0.7,
        keyword_weight=0.3,
    )

    hybrid_results = retriever.retrieve(hybrid_query)

    print(f"  Query: '{hybrid_query.query}'")
    print(f"  Hybrid weights: semantic={hybrid_query.semantic_weight}, keyword={hybrid_query.keyword_weight}")
    print(f"  Results: {len(hybrid_results)} chunks")

    for i, result in enumerate(hybrid_results[:3], 1):
        print(f"\n  [{i}] Score: {result.score:.3f} | Method: {result.retrieval_method}")
        print(f"      {result.chunk.signature}")

    # Step 5: Generate structured context for LLM
    print("\n[5/5] Generating structured context for LLM prompt...")

    context = retriever.retrieve_with_context(
        query="How to implement semantic search with embeddings?",
        include_golden_rules=True,
    )

    print("  ✅ Generated context:")
    print(f"     - {len(context.code_patterns)} code patterns")
    print(f"     - {len(context.golden_rules)} golden rules")
    print(f"     - Retrieval time: {context.retrieval_time_ms:.1f}ms")

    print("\n  📝 Sample prompt section:")
    print("  " + "-" * 76)

    # Show first 500 chars of prompt section
    prompt_section = context.to_prompt_section()
    print("  " + "\n  ".join(prompt_section[:500].split("\n")))
    print("  ...")

    # Summary
    print("\n" + "=" * 80)
    print("✅ RAG Demo Complete!")
    print("=" * 80)
    print("\nKey Capabilities Demonstrated:")
    print("  ✓ AST-aware code chunking")
    print("  ✓ Embedding generation with caching")
    print("  ✓ Hybrid search (semantic + keyword)")
    print("  ✓ Metadata-rich indexing")
    print("  ✓ Structured context generation for LLMs")

    print("\nNext Steps:")
    print("  1. Index full Hive codebase (all packages + apps)")
    print("  2. Integrate with Guardian Agent")
    print("  3. Create golden set evaluation")
    print("  4. Implement incremental indexing")

    print("\nFor more information, see:")
    print("  packages/hive-ai/src/hive_ai/rag/README.md")
    print("=" * 80)


if __name__ == "__main__":
    main()
