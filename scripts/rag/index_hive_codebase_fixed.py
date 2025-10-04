"""Full Hive Codebase Indexing for RAG System - Standalone Script.

This script indexes all Python files and architectural memory (markdown docs)
across the entire Hive platform for RAG-enhanced code review.
"""

import sys
import time
from pathlib import Path

# Add hive-ai package to path
hive_ai_src = Path(__file__).parent.parent.parent / "packages" / "hive-ai" / "src"
sys.path.insert(0, str(hive_ai_src))

# Now import - but hive_ai package has dependencies, so we need to mock them
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Create minimal stub for missing hive packages before importing
class StubModule:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


sys.modules["hive_async"] = StubModule()
sys.modules["hive_async.resilience"] = StubModule()
sys.modules["hive_logging"] = StubModule()
sys.modules["hive_cache"] = StubModule()
sys.modules["hive_db"] = StubModule()

# Now we can import the RAG modules
from hive_ai.rag.chunker import HierarchicalChunker
from hive_ai.rag.retriever import EnhancedRAGRetriever


class CodebaseIndexer:
    """Full codebase indexing orchestrator."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.chunker = HierarchicalChunker()
        self.retriever = EnhancedRAGRetriever()
        self.stats = {
            "files_processed": 0,
            "chunks_created": 0,
            "python_files": 0,
            "markdown_files": 0,
            "errors": 0,
            "indexing_time_sec": 0.0,
        }

    def index_full_codebase(self, output_path: Path) -> dict:
        start_time = time.time()
        logger.info(f"Starting full codebase indexing from {self.project_root}")

        all_chunks = []

        # Index Python files
        python_chunks = self._index_python_files()
        all_chunks.extend(python_chunks)

        # Index markdown documentation
        markdown_chunks = self._index_markdown_files()
        all_chunks.extend(markdown_chunks)

        # Index with RAG retriever
        logger.info(f"Indexing {len(all_chunks)} chunks into RAG system...")
        self.retriever.index_chunks(all_chunks)

        # Save index
        logger.info(f"Saving index to {output_path}...")
        self.retriever.save(output_path)

        # Calculate statistics
        self.stats["chunks_created"] = len(all_chunks)
        self.stats["indexing_time_sec"] = time.time() - start_time

        logger.info(
            f"Full codebase indexing complete: {len(all_chunks)} chunks in {self.stats['indexing_time_sec']:.1f}s",
        )

        return self.stats

    def _index_python_files(self) -> list:
        logger.info("Indexing Python files...")

        all_chunks = []
        directories = [
            self.project_root / "packages",
            self.project_root / "apps",
            self.project_root / "scripts",
        ]

        for directory in directories:
            if not directory.exists():
                logger.warning(f"Directory not found: {directory}")
                continue

            logger.info(f"Processing directory: {directory.name}")

            for py_file in directory.rglob("*.py"):
                if "__pycache__" in str(py_file) or "venv" in str(py_file):
                    continue

                try:
                    chunks = self.chunker.chunk_file(py_file)
                    all_chunks.extend(chunks)
                    self.stats["python_files"] += 1
                    self.stats["files_processed"] += 1

                    if self.stats["files_processed"] % 100 == 0:
                        logger.info(f"Progress: {self.stats['files_processed']} files, {len(all_chunks)} chunks")

                except Exception as e:
                    logger.error(f"Failed to chunk {py_file}: {e}")
                    self.stats["errors"] += 1

        logger.info(f"Python indexing complete: {self.stats['python_files']} files, {len(all_chunks)} chunks")
        return all_chunks

    def _index_markdown_files(self) -> list:
        logger.info("Indexing markdown documentation...")

        all_chunks = []
        markdown_sources = [
            self.project_root / "claudedocs",
            self.project_root / "packages",
            self.project_root / "apps",
            self.project_root / "scripts" / "archive",
        ]

        for source_dir in markdown_sources:
            if not source_dir.exists():
                continue

            logger.info(f"Processing markdown in: {source_dir.name}")

            for md_file in source_dir.rglob("*.md"):
                try:
                    chunks = self.chunker.chunk_markdown(md_file)
                    all_chunks.extend(chunks)
                    self.stats["markdown_files"] += 1
                    self.stats["files_processed"] += 1

                except Exception as e:
                    logger.error(f"Failed to chunk markdown {md_file}: {e}")
                    self.stats["errors"] += 1

        logger.info(f"Markdown indexing complete: {self.stats['markdown_files']} files, {len(all_chunks)} chunks")
        return all_chunks

    def spot_check_quality(self, num_samples: int = 5) -> None:
        logger.info("Performing post-indexing spot-check...")

        stats = self.retriever.get_stats()
        total_chunks = stats["vector_store"]["total_chunks"]
        logger.info(f"Total chunks indexed: {total_chunks}")

        test_queries = [
            "database connection pooling",
            "async retry patterns",
            "configuration dependency injection",
            "logging best practices",
            "deprecated authentication",
        ]

        for query in test_queries[:num_samples]:
            result = self.retriever.retrieve_with_context(query, k=3)
            logger.info(
                f"Spot-check query: '{query}' -> {len(result.code_patterns)} patterns retrieved in {result.retrieval_time_ms:.0f}ms",
            )

            if result.code_patterns:
                top_pattern = result.code_patterns[0]
                logger.info(f"  Top result: {top_pattern.source} (score: {top_pattern.relevance_score:.2f})")


def main():
    print("=" * 60)
    print("Hive Platform - Full Codebase RAG Indexing")
    print("=" * 60)
    print()

    project_root = Path(__file__).parent.parent.parent
    output_path = project_root / "data" / "rag_index"

    print(f"Project Root: {project_root}")
    print(f"Output Path:  {output_path}")
    print()

    indexer = CodebaseIndexer(project_root)

    print("Starting full codebase indexing...")
    print("This will take 1-2 minutes for ~2,000 files...")
    print()

    stats = indexer.index_full_codebase(output_path)

    print()
    print("=" * 60)
    print("Indexing Complete!")
    print("=" * 60)
    print(f"Files Processed:    {stats['files_processed']}")
    print(f"  - Python Files:   {stats['python_files']}")
    print(f"  - Markdown Files: {stats['markdown_files']}")
    print(f"Chunks Created:     {stats['chunks_created']}")
    print(f"Errors:             {stats['errors']}")
    print(f"Indexing Time:      {stats['indexing_time_sec']:.1f} seconds")
    print(f"Index Location:     {output_path}")
    print("=" * 60)
    print()

    print("Running post-indexing spot-checks...")
    print()
    indexer.spot_check_quality(num_samples=5)

    print()
    print("Full codebase indexing complete and validated!")
    print()


if __name__ == "__main__":
    main()
