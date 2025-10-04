"""Simple RAG indexing without complex dependencies.
Uses only core RAG components and sentence-transformers.
"""

# Minimal imports
import ast
import time
from pathlib import Path

try:
    import tomli as toml_parser
except ImportError:
    try:
        import tomllib as toml_parser
    except ImportError:
        toml_parser = None

import json

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).parent.parent.parent


def chunk_python(file_path):
    """Simple Python chunking by top-level definitions."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)
        chunks = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                start_line = node.lineno
                end_line = node.end_lineno or (start_line + 1)
                chunk_lines = content.split("\n")[start_line - 1 : end_line]
                chunk_text = "\n".join(chunk_lines)

                chunks.append(
                    {
                        "text": chunk_text,
                        "file": str(file_path),
                        "start_line": start_line,
                        "type": "python",
                        "name": node.name,
                    },
                )

        if not chunks:
            # File has no top-level definitions, chunk as whole
            chunks.append(
                {
                    "text": content[:2000],  # First 2000 chars
                    "file": str(file_path),
                    "start_line": 1,
                    "type": "python",
                    "name": file_path.stem,
                },
            )

        return chunks
    except Exception as e:
        print(f"  Warning: Failed to chunk {file_path.name}: {e}")
        return []


def chunk_markdown(file_path):
    """Simple Markdown chunking by sections."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        chunks = []
        current_section = []
        current_header = None

        for line in content.split("\n"):
            if line.startswith("#"):
                if current_section:
                    chunks.append(
                        {
                            "text": "\n".join(current_section),
                            "file": str(file_path),
                            "type": "markdown",
                            "name": current_header or file_path.stem,
                        },
                    )
                current_section = [line]
                current_header = line.strip("# ")
            else:
                current_section.append(line)

        if current_section:
            chunks.append(
                {
                    "text": "\n".join(current_section),
                    "file": str(file_path),
                    "type": "markdown",
                    "name": current_header or file_path.stem,
                },
            )

        return chunks
    except Exception as e:
        print(f"  Warning: Failed to chunk {file_path.name}: {e}")
        return []


def chunk_yaml(file_path):
    """Simple YAML chunking."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Simple chunking by top-level keys
        chunks = []
        current_chunk = []
        current_key = None

        for line in content.split("\n"):
            if line and not line.startswith(" ") and ":" in line:
                if current_chunk:
                    chunks.append(
                        {
                            "text": "\n".join(current_chunk),
                            "file": str(file_path),
                            "type": "yaml",
                            "name": current_key or file_path.stem,
                        },
                    )
                current_chunk = [line]
                current_key = line.split(":")[0].strip()
            else:
                current_chunk.append(line)

        if current_chunk:
            chunks.append(
                {
                    "text": "\n".join(current_chunk),
                    "file": str(file_path),
                    "type": "yaml",
                    "name": current_key or file_path.stem,
                },
            )

        return chunks
    except Exception as e:
        print(f"  Warning: Failed to chunk {file_path.name}: {e}")
        return []


def chunk_toml(file_path):
    """Simple TOML chunking."""
    if not toml_parser:
        return []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Parse to get sections
        data = toml_parser.loads(content)

        chunks = []
        for section, values in data.items():
            section_text = f"[{section}]\n"
            if isinstance(values, dict):
                for k, v in values.items():
                    section_text += f"{k} = {v!r}\n"
            else:
                section_text += f"{section} = {values!r}\n"

            chunks.append({"text": section_text, "file": str(file_path), "type": "toml", "name": section})

        return chunks
    except Exception as e:
        print(f"  Warning: Failed to chunk {file_path.name}: {e}")
        return []


def main():
    """Run full codebase indexing."""
    print("=" * 80)
    print("HIVE RAG SIMPLE INDEXING")
    print("=" * 80)
    print(f"Project root: {PROJECT_ROOT}")

    start_time = time.time()

    # Initialize embedding model
    print("\n[1/5] Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Define paths to index
    paths_to_index = [
        PROJECT_ROOT / "packages",
        PROJECT_ROOT / "apps",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "claudedocs",
    ]

    print("\n[2/5] Scanning directories...")
    all_files = []
    for path in paths_to_index:
        if path.exists():
            all_files.extend(path.rglob("*.py"))
            all_files.extend(path.rglob("*.md"))
            all_files.extend(path.rglob("*.yml"))
            all_files.extend(path.rglob("*.yaml"))
            all_files.extend(path.rglob("*.toml"))

    print(f"Found {len(all_files)} files")

    # Filter out excluded paths
    excluded_patterns = ["__pycache__", ".pytest_cache", ".git", "node_modules", ".venv", "venv"]
    filtered_files = [f for f in all_files if not any(p in str(f) for p in excluded_patterns)]
    print(f"After filtering: {len(filtered_files)} files")

    # Chunk all files
    print("\n[3/5] Chunking files...")
    all_chunks = []
    file_count = 0

    for file_path in filtered_files:
        suffix = file_path.suffix.lower()

        if suffix == ".py":
            chunks = chunk_python(file_path)
        elif suffix == ".md":
            chunks = chunk_markdown(file_path)
        elif suffix in [".yml", ".yaml"]:
            chunks = chunk_yaml(file_path)
        elif suffix == ".toml":
            chunks = chunk_toml(file_path)
        else:
            continue

        all_chunks.extend(chunks)
        file_count += 1

        if file_count % 100 == 0:
            print(f"  Processed {file_count}/{len(filtered_files)} files, {len(all_chunks)} chunks so far...")

    print(f"Created {len(all_chunks)} total chunks from {file_count} files")

    # Create embeddings in batches
    print("\n[4/5] Creating embeddings...")
    texts = [chunk["text"][:500] for chunk in all_chunks]  # Truncate to 500 chars

    # Process in batches to avoid memory issues
    batch_size = 500
    embeddings_list = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        print(f"  Processing batch {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1} ({len(batch)} texts)...")
        batch_embeddings = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        embeddings_list.append(batch_embeddings)

    embeddings = np.vstack(embeddings_list)

    # Build FAISS index
    print("\n[5/5] Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype("float32"))

    # Save index and metadata
    output_dir = PROJECT_ROOT / "data" / "rag_index"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving to {output_dir}...")
    faiss.write_index(index, str(output_dir / "faiss.index"))

    with open(output_dir / "chunks.json", "w") as f:
        json.dump(all_chunks, f)

    with open(output_dir / "metadata.json", "w") as f:
        json.dump(
            {
                "total_chunks": len(all_chunks),
                "total_files": file_count,
                "embedding_model": "all-MiniLM-L6-v2",
                "dimension": dimension,
                "indexed_at": time.time(),
            },
            f,
            indent=2,
        )

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 80)
    print("INDEXING COMPLETE")
    print("=" * 80)
    print(f"Files processed: {file_count}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Embedding dimension: {dimension}")
    print(f"Index location: {output_dir}")
    print(f"Time elapsed: {elapsed:.1f}s")
    print("=" * 80)


if __name__ == "__main__":
    main()
