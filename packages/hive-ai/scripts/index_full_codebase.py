"""
Full Hive codebase indexing with markdown architectural memory.

Indexes all Python and markdown files across packages/, apps/, scripts/
for comprehensive RAG-powered code intelligence.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add hive-ai to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hive_ai.rag import EnhancedRAGRetriever, HierarchicalChunker
from hive_logging import get_logger

logger = get_logger(__name__)


def index_full_codebase() -> None:
    """Index all Python and markdown files in Hive platform."""
    project_root = Path(__file__).parent.parent.parent.parent
    logger.info(f"Indexing Hive codebase from: {project_root}")

    # Initialize components
    chunker = (HierarchicalChunker(),)
    retriever = EnhancedRAGRetriever()

    # Track statistics
    stats = {
        "python_files": 0,
        "python_chunks": 0,
        "markdown_files": 0,
        "markdown_chunks": 0,
        "total_time": 0.0,
    }

    start_time = time.time()

    # 1. Index Python files from packages/
    logger.info("Indexing packages/ directory...")
    packages_dir = project_root / "packages"
    if packages_dir.exists():
        python_chunks = chunker.chunk_directory(packages_dir, recursive=True)
        stats["python_chunks"] += len(python_chunks)
        retriever.index_chunks(python_chunks)
        logger.info(f"  Indexed {len(python_chunks)} chunks from packages/")

    # 2. Index Python files from apps/
    logger.info("Indexing apps/ directory...")
    apps_dir = project_root / "apps"
    if apps_dir.exists():
        python_chunks = chunker.chunk_directory(apps_dir, recursive=True)
        stats["python_chunks"] += len(python_chunks)
        retriever.index_chunks(python_chunks)
        logger.info(f"  Indexed {len(python_chunks)} chunks from apps/")

    # 3. Index Python files from scripts/
    logger.info("Indexing scripts/ directory...")
    scripts_dir = project_root / "scripts"
    if scripts_dir.exists():
        python_chunks = chunker.chunk_directory(scripts_dir, recursive=True)
        stats["python_chunks"] += len(python_chunks)
        retriever.index_chunks(python_chunks)
        logger.info(f"  Indexed {len(python_chunks)} chunks from scripts/")

    # 4. Index markdown files - architectural memory
    logger.info("Indexing markdown files for architectural memory...")

    # Integration reports
    cleanup_reports = project_root / "scripts" / "archive" / "cleanup_project" / "cleanup"
    if cleanup_reports.exists():
        for md_file in cleanup_reports.glob("*.md"):
            md_chunks = chunker.chunk_markdown(md_file)
            stats["markdown_chunks"] += len(md_chunks)
            stats["markdown_files"] += 1
            retriever.index_chunks(md_chunks)
        logger.info(f"  Indexed {stats['markdown_files']} integration reports")

    # Migration guides
    claudedocs_dir = project_root / "claudedocs"
    if claudedocs_dir.exists():
        migration_files = 0
        for md_file in claudedocs_dir.glob("*migration*.md"):
            md_chunks = chunker.chunk_markdown(md_file)
            stats["markdown_chunks"] += len(md_chunks)
            migration_files += 1
            retriever.index_chunks(md_chunks)
        stats["markdown_files"] += migration_files
        logger.info(f"  Indexed {migration_files} migration guides")

    # Archive READMEs
    archive_dir = project_root / "scripts" / "archive"
    if archive_dir.exists():
        archive_readmes = 0
        for readme in archive_dir.rglob("README.md"):
            md_chunks = chunker.chunk_markdown(readme)
            stats["markdown_chunks"] += len(md_chunks)
            archive_readmes += 1
            retriever.index_chunks(md_chunks)
        stats["markdown_files"] += archive_readmes
        logger.info(f"  Indexed {archive_readmes} archive READMEs")

    # Package READMEs
    if packages_dir.exists():
        package_readmes = 0
        for readme in packages_dir.glob("*/README.md"):
            md_chunks = chunker.chunk_markdown(readme)
            stats["markdown_chunks"] += len(md_chunks)
            package_readmes += 1
            retriever.index_chunks(md_chunks)
        stats["markdown_files"] += package_readmes
        logger.info(f"  Indexed {package_readmes} package READMEs")

    # App READMEs
    if apps_dir.exists():
        app_readmes = 0
        for readme in apps_dir.glob("*/README.md"):
            md_chunks = chunker.chunk_markdown(readme)
            stats["markdown_chunks"] += len(md_chunks)
            app_readmes += 1
            retriever.index_chunks(md_chunks)
        stats["markdown_files"] += app_readmes
        logger.info(f"  Indexed {app_readmes} app READMEs")

    stats["total_time"] = time.time() - start_time

    # 5. Save index to disk
    logger.info("Saving RAG index to disk...")
    index_path = project_root / "data" / "rag_index"
    index_path.mkdir(parents=True, exist_ok=True)
    retriever.save(index_path)

    # 6. Print statistics
    print("\n" + "=" * 80)
    print("Full Codebase Indexing Complete")
    print("=" * 80)
    print(f"Python chunks:    {stats['python_chunks']:,}")
    print(f"Markdown files:   {stats['markdown_files']:,}")
    print(f"Markdown chunks:  {stats['markdown_chunks']:,}")
    print(f"Total chunks:     {stats['python_chunks'] + stats['markdown_chunks']:,}")
    print(f"Indexing time:    {stats['total_time']:.1f} seconds")
    print(f"Index saved to:   {index_path}")
    print("=" * 80)

    # 7. Test retrieval with a sample query
    logger.info("Testing retrieval with sample query...")
    test_query = ("How do I implement async database connection pooling?",)
    results = retriever.retrieve(test_query, k=5)

    print(f"\nSample query: '{test_query}'")
    print(f"Top {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.chunk.file_path}:{result.chunk.line_start}")
        print(f"     Score: {result.score:.3f} | Method: {result.retrieval_method}")
        print(f"     Signature: {result.chunk.signature[:80]}")
        print()

    logger.info("Indexing complete and validated")


if __name__ == "__main__":
    index_full_codebase()
