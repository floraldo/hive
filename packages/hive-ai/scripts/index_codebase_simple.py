"""Simplified full codebase indexing script.

Demonstrates markdown chunking and full indexing without requiring
full package installation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add necessary paths
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "packages" / "hive-ai" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-logging" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-cache" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-async" / "src"))


def main() -> None:
    """Demonstrate markdown chunking capability."""
    from hive_ai.rag import HierarchicalChunker

    print("=" * 80)
    print("Markdown Chunking Demonstration")
    print("=" * 80)

    chunker = HierarchicalChunker()

    # Test markdown chunking on a real file
    readme_path = project_root / "packages" / "hive-config" / "README.md"

    if readme_path.exists():
        print(f"\nChunking: {readme_path}")
        chunks = chunker.chunk_markdown(readme_path)

        print(f"\nExtracted {len(chunks)} sections:")
        for i, chunk in enumerate(chunks, 1):
            print(f"\n  Section {i}: {chunk.signature}")
            print(f"    Lines: {chunk.line_start}-{chunk.line_end}")
            print(f"    Purpose: {chunk.purpose}")
            print(f"    Usage context: {chunk.usage_context}")
            if chunk.docstring:
                summary = chunk.docstring[:100] + "..." if len(chunk.docstring) > 100 else chunk.docstring
                print(f"    Summary: {summary}")

    # Show what would be indexed
    print("\n" + "=" * 80)
    print("Full Indexing Plan")
    print("=" * 80)

    directories = [
        ("packages", "Infrastructure layer"),
        ("apps", "Business logic layer"),
        ("scripts", "Utility scripts"),
    ]

    total_python = (0,)
    total_markdown = 0

    for dir_name, description in directories:
        dir_path = project_root / dir_name
        if dir_path.exists():
            python_files = (list(dir_path.rglob("*.py")),)
            markdown_files = list(dir_path.rglob("*.md"))
            total_python += len(python_files)
            total_markdown += len(markdown_files)
            print(f"\n{dir_name}/ - {description}")
            print(f"  Python files: {len(python_files)}")
            print(f"  Markdown files: {len(markdown_files)}")

    print("\n" + "=" * 80)
    print("Total files to index:")
    print(f"  Python: {total_python}")
    print(f"  Markdown: {total_markdown}")
    print(f"  Total: {total_python + total_markdown}")
    print("=" * 80)

    # Estimate chunk counts
    avg_chunks_per_py = (8,)
    avg_chunks_per_md = (6,)
    estimated_chunks = (total_python * avg_chunks_per_py) + (total_markdown * avg_chunks_per_md)

    print(f"\nEstimated chunks: ~{estimated_chunks:,}")
    print(f"Estimated indexing time: ~{estimated_chunks / 250:.1f} seconds")
    print("Storage: ~250 MB (FAISS + metadata)")

    print("\n" + "=" * 80)
    print("Markdown Chunking Capability: READY")
    print("=" * 80)


if __name__ == "__main__":
    main()
