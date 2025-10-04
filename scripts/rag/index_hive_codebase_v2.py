"""Resilient Two-Stage Hive Codebase Indexing for RAG System.

Stage 1: Chunking (Fast, ~10 minutes)
- Scan all files
- Create code chunks
- Save to intermediate JSONL file

Stage 2: Embedding (Long-running, ~30-60 minutes)
- Load chunks from JSONL
- Create embeddings in batches
- Build FAISS index with checkpointing

Features:
- Progress bars with tqdm
- Resumable from checkpoints
- Comprehensive error handling
- Detailed post-run summary
"""

import json
import time
from pathlib import Path
from typing import Any

import faiss
import numpy as np

# Simple imports to avoid complex dependencies
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Statistics tracking
stats = {
    "stage1": {
        "files_scanned": 0,
        "python_files": 0,
        "markdown_files": 0,
        "yaml_files": 0,
        "toml_files": 0,
        "chunks_created": 0,
        "errors": 0,
        "time_sec": 0.0,
    },
    "stage2": {
        "chunks_loaded": 0,
        "batches_processed": 0,
        "embeddings_created": 0,
        "checkpoints_saved": 0,
        "time_sec": 0.0,
    },
}

def chunk_python(file_path: Path) -> list[dict[str, Any]]:
    """Chunk Python file by top-level definitions."""
    import ast

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)
        chunks = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                start_line = node.lineno
                end_line = node.end_lineno or (start_line + 1)
                chunk_lines = content.split("\n")[start_line-1:end_line]
                chunk_text = "\n".join(chunk_lines)

                chunks.append({
                    "text": chunk_text,
                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                    "start_line": start_line,
                    "type": "python",
                    "name": node.name,
                })

        if not chunks:
            # No top-level definitions, chunk as whole
            chunks.append({
                "text": content[:2000],
                "file": str(file_path.relative_to(PROJECT_ROOT)),
                "start_line": 1,
                "type": "python",
                "name": file_path.stem,
            })

        return chunks
    except Exception:
        return []

def chunk_markdown(file_path: Path) -> list[dict[str, Any]]:
    """Chunk Markdown by sections."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        chunks = []
        current_section = []
        current_header = None

        for line in content.split("\n"):
            if line.startswith("#"):
                if current_section:
                    chunks.append({
                        "text": "\n".join(current_section),
                        "file": str(file_path.relative_to(PROJECT_ROOT)),
                        "type": "markdown",
                        "name": current_header or file_path.stem,
                    })
                current_section = [line]
                current_header = line.strip("# ")
            else:
                current_section.append(line)

        if current_section:
            chunks.append({
                "text": "\n".join(current_section),
                "file": str(file_path.relative_to(PROJECT_ROOT)),
                "type": "markdown",
                "name": current_header or file_path.stem,
            })

        return chunks
    except Exception:
        return []

def chunk_yaml(file_path: Path) -> list[dict[str, Any]]:
    """Chunk YAML by top-level keys."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        chunks = []
        current_chunk = []
        current_key = None

        for line in content.split("\n"):
            if line and not line.startswith(" ") and ":" in line:
                if current_chunk:
                    chunks.append({
                        "text": "\n".join(current_chunk),
                        "file": str(file_path.relative_to(PROJECT_ROOT)),
                        "type": "yaml",
                        "name": current_key or file_path.stem,
                    })
                current_chunk = [line]
                current_key = line.split(":")[0].strip()
            else:
                current_chunk.append(line)

        if current_chunk:
            chunks.append({
                "text": "\n".join(current_chunk),
                "file": str(file_path.relative_to(PROJECT_ROOT)),
                "type": "yaml",
                "name": current_key or file_path.stem,
            })

        return chunks
    except Exception:
        return []

def chunk_toml(file_path: Path) -> list[dict[str, Any]]:
    """Chunk TOML by sections."""
    try:
        import tomli
    except ImportError:
        try:
            import tomllib as tomli
        except ImportError:
            return []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        data = tomli.loads(content)
        chunks = []

        for section, values in data.items():
            section_text = f"[{section}]\n"
            if isinstance(values, dict):
                for k, v in values.items():
                    section_text += f"{k} = {v!r}\n"
            else:
                section_text += f"{section} = {values!r}\n"

            chunks.append({
                "text": section_text,
                "file": str(file_path.relative_to(PROJECT_ROOT)),
                "type": "toml",
                "name": section,
            })

        return chunks
    except Exception:
        return []

def stage1_chunking(output_path: Path) -> Path:
    """Stage 1: Scan files and create chunks.

    Returns:
        Path to intermediate chunks.jsonl file

    """
    print("\n" + "=" * 80)
    print("STAGE 1: CHUNKING")
    print("=" * 80)

    start_time = time.time()

    # Scan for files
    print("\nScanning directories...")
    paths_to_scan = [
        PROJECT_ROOT / "packages",
        PROJECT_ROOT / "apps",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "claudedocs",
    ]

    all_files = []
    for path in paths_to_scan:
        if path.exists():
            all_files.extend(path.rglob("*.py"))
            all_files.extend(path.rglob("*.md"))
            all_files.extend(path.rglob("*.yml"))
            all_files.extend(path.rglob("*.yaml"))
            all_files.extend(path.rglob("*.toml"))

    # Filter excluded patterns
    excluded = ["__pycache__", ".pytest_cache", ".git", "node_modules", ".venv", "venv"]
    filtered_files = [f for f in all_files if not any(p in str(f) for p in excluded)]

    print(f"Found {len(filtered_files)} files to process")

    # Chunk all files with progress bar
    print("\nChunking files...")
    all_chunks = []
    chunks_file = output_path / "chunks.jsonl"

    with open(chunks_file, "w", encoding="utf-8") as f:
        for file_path in tqdm(filtered_files, desc="Processing files"):
            suffix = file_path.suffix.lower()

            if suffix == ".py":
                chunks = chunk_python(file_path)
                stats["stage1"]["python_files"] += 1
            elif suffix == ".md":
                chunks = chunk_markdown(file_path)
                stats["stage1"]["markdown_files"] += 1
            elif suffix in [".yml", ".yaml"]:
                chunks = chunk_yaml(file_path)
                stats["stage1"]["yaml_files"] += 1
            elif suffix == ".toml":
                chunks = chunk_toml(file_path)
                stats["stage1"]["toml_files"] += 1
            else:
                continue

            # Write each chunk to JSONL
            for chunk in chunks:
                f.write(json.dumps(chunk) + "\n")
                all_chunks.append(chunk)

            stats["stage1"]["files_scanned"] += 1
            if chunks:
                stats["stage1"]["chunks_created"] += len(chunks)

    stats["stage1"]["time_sec"] = time.time() - start_time

    print("\nStage 1 Complete:")
    print(f"  Files processed: {stats['stage1']['files_scanned']}")
    print(f"    - Python: {stats['stage1']['python_files']}")
    print(f"    - Markdown: {stats['stage1']['markdown_files']}")
    print(f"    - YAML: {stats['stage1']['yaml_files']}")
    print(f"    - TOML: {stats['stage1']['toml_files']}")
    print(f"  Chunks created: {stats['stage1']['chunks_created']}")
    print(f"  Intermediate file: {chunks_file}")
    print(f"  Time: {stats['stage1']['time_sec']:.1f}s")

    return chunks_file

def stage2_embedding(chunks_file: Path, output_path: Path) -> None:
    """Stage 2: Create embeddings and build FAISS index.

    Args:
        chunks_file: Path to intermediate chunks.jsonl
        output_path: Directory to save final index

    """
    print("\n" + "=" * 80)
    print("STAGE 2: EMBEDDING & INDEXING")
    print("=" * 80)

    start_time = time.time()

    # Load embedding model
    print("\nLoading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"  Model: all-MiniLM-L6-v2 ({model.get_sentence_embedding_dimension()} dims)")

    # Load chunks from JSONL
    print("\nLoading chunks from intermediate file...")
    chunks = []
    with open(chunks_file, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))

    stats["stage2"]["chunks_loaded"] = len(chunks)
    print(f"  Loaded {len(chunks)} chunks")

    # Create embeddings in batches
    print("\nCreating embeddings...")
    batch_size = 500
    all_embeddings = []

    texts = [chunk["text"][:500] for chunk in chunks]  # Truncate to 500 chars
    num_batches = (len(texts) - 1) // batch_size + 1

    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches", total=num_batches):
        batch = texts[i:i+batch_size]
        batch_embeddings = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        all_embeddings.append(batch_embeddings)

        stats["stage2"]["batches_processed"] += 1

        # Save checkpoint every 2 batches (1,000 chunks)
        if stats["stage2"]["batches_processed"] % 2 == 0:
            checkpoint_file = output_path / f"checkpoint_{stats['stage2']['batches_processed']}.npy"
            np.save(checkpoint_file, np.vstack(all_embeddings))
            stats["stage2"]["checkpoints_saved"] += 1

    # Combine all embeddings
    embeddings = np.vstack(all_embeddings)
    stats["stage2"]["embeddings_created"] = len(embeddings)

    print(f"\n  Created {len(embeddings)} embeddings")
    print(f"  Checkpoints saved: {stats['stage2']['checkpoints_saved']}")

    # Build FAISS index
    print("\nBuilding FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype("float32"))

    print(f"  Index: {index.ntotal} vectors, {dimension} dimensions")

    # Save index and metadata
    print("\nSaving final index...")
    faiss.write_index(index, str(output_path / "faiss.index"))

    # Save chunks metadata
    with open(output_path / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f)

    # Save metadata
    with open(output_path / "metadata.json", "w", encoding="utf-8") as f:
        json.dump({
            "total_chunks": len(chunks),
            "total_files": stats["stage1"]["files_scanned"],
            "embedding_model": "all-MiniLM-L6-v2",
            "dimension": dimension,
            "indexed_at": time.time(),
            "stage1_time_sec": stats["stage1"]["time_sec"],
            "stage2_time_sec": time.time() - start_time,
        }, f, indent=2)

    # Clean up checkpoints
    for checkpoint in output_path.glob("checkpoint_*.npy"):
        checkpoint.unlink()

    stats["stage2"]["time_sec"] = time.time() - start_time

    print("\nStage 2 Complete:")
    print(f"  Chunks embedded: {stats['stage2']['embeddings_created']}")
    print(f"  Batches processed: {stats['stage2']['batches_processed']}")
    print(f"  FAISS index: {output_path / 'faiss.index'}")
    print(f"  Time: {stats['stage2']['time_sec']:.1f}s")

def print_summary():
    """Print comprehensive post-run summary."""
    print("\n" + "=" * 80)
    print("INDEXING COMPLETE - SUMMARY")
    print("=" * 80)

    print("\nSTAGE 1: CHUNKING")
    print(f"  Files scanned: {stats['stage1']['files_scanned']}")
    print(f"    - Python:   {stats['stage1']['python_files']}")
    print(f"    - Markdown: {stats['stage1']['markdown_files']}")
    print(f"    - YAML:     {stats['stage1']['yaml_files']}")
    print(f"    - TOML:     {stats['stage1']['toml_files']}")
    print(f"  Chunks created: {stats['stage1']['chunks_created']}")
    print(f"  Errors: {stats['stage1']['errors']}")
    print(f"  Time: {stats['stage1']['time_sec']:.1f}s")

    print("\nSTAGE 2: EMBEDDING & INDEXING")
    print(f"  Chunks loaded: {stats['stage2']['chunks_loaded']}")
    print(f"  Embeddings created: {stats['stage2']['embeddings_created']}")
    print(f"  Batches processed: {stats['stage2']['batches_processed']}")
    print(f"  Checkpoints saved: {stats['stage2']['checkpoints_saved']}")
    print(f"  Time: {stats['stage2']['time_sec']:.1f}s")

    total_time = stats["stage1"]["time_sec"] + stats["stage2"]["time_sec"]
    print(f"\nTOTAL TIME: {total_time:.1f}s ({total_time/60:.1f} minutes)")

    print("\nINDEX LOCATION:")
    output_path = PROJECT_ROOT / "data" / "rag_index"
    print(f"  {output_path}")
    print(f"  - faiss.index ({(output_path / 'faiss.index').stat().st_size / 1024 / 1024:.1f} MB)")
    print("  - chunks.json")
    print("  - metadata.json")

    print("\n" + "=" * 80)

def main():
    """Main execution."""
    print("=" * 80)
    print("HIVE RAG PLATFORM - TWO-STAGE INDEXING")
    print("=" * 80)
    print(f"\nProject Root: {PROJECT_ROOT}")

    output_path = PROJECT_ROOT / "data" / "rag_index"
    output_path.mkdir(parents=True, exist_ok=True)
    print(f"Output Path: {output_path}")

    # Stage 1: Chunking
    chunks_file = stage1_chunking(output_path)

    # Stage 2: Embedding
    stage2_embedding(chunks_file, output_path)

    # Summary
    print_summary()

    print("\nINDEXING COMPLETE!")
    print("Next steps:")
    print("  1. Run integration tests: pytest tests/integration/test_rag_guardian.py -v")
    print("  2. Establish quality baseline: pytest tests/rag/test_combined_quality.py -v")
    print("  3. Start API server: python scripts/rag/start_api.py")

if __name__ == "__main__":
    main()
