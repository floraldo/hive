"""
Simple wrapper to run full Hive codebase indexing using installed hive-ai package.
"""

import importlib.util
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def import_rag_module(module_name):
    """Import RAG module directly from file."""
    rag_src = PROJECT_ROOT / "packages" / "hive-ai" / "src" / "hive_ai" / "rag"
    spec = importlib.util.spec_from_file_location(f"hive_ai.rag.{module_name}", rag_src / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Load required modules
models = import_rag_module("models")
chunker_mod = import_rag_module("chunker")
embeddings_mod = import_rag_module("embeddings")
vector_store_mod = import_rag_module("vector_store")
keyword_search_mod = import_rag_module("keyword_search")
retriever_mod = import_rag_module("retriever")
metadata_loader_mod = import_rag_module("metadata_loader")

HierarchicalChunker = chunker_mod.HierarchicalChunker
EmbeddingGenerator = embeddings_mod.EmbeddingGenerator
EnhancedRAGRetriever = retriever_mod.EnhancedRAGRetriever


def main():
    """Run full codebase indexing."""
    print("=" * 80)
    print("HIVE RAG FULL INDEXING")
    print("=" * 80)
    print(f"Project root: {PROJECT_ROOT}")

    start_time = time.time()

    # Initialize components
    print("\n[1/4] Initializing components...")
    chunker = HierarchicalChunker()
    embedder = EmbeddingGenerator()
    retriever = EnhancedRAGRetriever(chunker=chunker, embedding_generator=embedder)

    # Define paths to index
    paths_to_index = [
        PROJECT_ROOT / "packages",
        PROJECT_ROOT / "apps",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "claudedocs",
    ]

    print("\n[2/4] Scanning directories...")
    all_files = []
    for path in paths_to_index:
        if path.exists():
            # Python files
            all_files.extend(path.rglob("*.py"))
            # Markdown files
            all_files.extend(path.rglob("*.md"))
            # YAML files
            all_files.extend(path.rglob("*.yml"))
            all_files.extend(path.rglob("*.yaml"))
            # TOML files
            all_files.extend(path.rglob("*.toml"))

    print(f"Found {len(all_files)} files to index")

    # Filter out excluded paths
    excluded_patterns = [
        "__pycache__",
        ".pytest_cache",
        ".git",
        "node_modules",
        ".venv",
        "venv",
    ]

    filtered_files = [f for f in all_files if not any(pattern in str(f) for pattern in excluded_patterns)]

    print(f"After filtering: {len(filtered_files)} files")

    # Chunk all files
    print("\n[3/4] Chunking files...")
    all_chunks = []
    file_count = 0

    for file_path in filtered_files:
        try:
            chunks = chunker.chunk_file(file_path)
            all_chunks.extend(chunks)
            file_count += 1

            if file_count % 100 == 0:
                print(f"  Processed {file_count}/{len(filtered_files)} files, {len(all_chunks)} chunks so far...")
        except Exception as e:
            print(f"  Warning: Failed to chunk {file_path.name}: {e}")
            continue

    print(f"Created {len(all_chunks)} total chunks from {file_count} files")

    # Index chunks
    print("\n[4/4] Creating embeddings and building index...")
    retriever.index_chunks(all_chunks)

    # Save index
    output_dir = PROJECT_ROOT / "data" / "rag_index"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving index to {output_dir}...")
    retriever.save(output_dir)

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 80)
    print("INDEXING COMPLETE")
    print("=" * 80)
    print(f"Files processed: {file_count}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Index location: {output_dir}")
    print(f"Time elapsed: {elapsed:.1f}s")
    print("=" * 80)


if __name__ == "__main__":
    main()
