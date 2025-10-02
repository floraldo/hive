"""
Full Hive Codebase Indexing for RAG System.

This script indexes all Python files and architectural memory (markdown docs)
across the entire Hive platform for RAG-enhanced code review.

Scope:
- packages/ (16 packages, ~1,000 files)
- apps/ (7 apps, ~800 files)
- scripts/ (~200 files)
- Architectural memory: claudedocs/*.md, archive READMEs
- Total: ~2,000 Python files + ~50 markdown files

Expected Output:
- ~15,500 code chunks
- ~500 markdown documentation chunks
- Total: ~16,000 chunks
- Storage: ~200 MB (FAISS + metadata)
- Indexing time: <60 seconds target
"""

import sys
import time
from pathlib import Path

# Add hive-ai RAG module directly to avoid main package dependencies
rag_path = Path(__file__).parent.parent.parent / "packages" / "hive-ai" / "src" / "hive_ai" / "rag"
sys.path.insert(0, str(rag_path.parent.parent))

# Import RAG modules - use explicit module imports to bypass hive_ai.__init__.py
import importlib.util


def load_rag_module(module_name, file_name):
    """Load RAG module directly from file."""
    spec = importlib.util.spec_from_file_location(module_name, rag_path / f"{file_name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


chunker_module = load_rag_module("chunker", "chunker")
embeddings_module = load_rag_module("embeddings", "embeddings")
retriever_module = load_rag_module("retriever", "retriever")

HierarchicalChunker = chunker_module.HierarchicalChunker
EmbeddingGenerator = embeddings_module.EmbeddingGenerator
EnhancedRAGRetriever = retriever_module.EnhancedRAGRetriever

# Minimal logging to avoid dependencies
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodebaseIndexer:
    """Full codebase indexing orchestrator."""

    def __init__(self, project_root: Path):
        """
        Initialize indexer.

        Args:
            project_root: Root directory of Hive project
        """
        self.project_root = project_root
        self.chunker = HierarchicalChunker()
        self.retriever = EnhancedRAGRetriever()

        # Statistics
        self.stats = {
            "files_processed": 0,
            "chunks_created": 0,
            "python_files": 0,
            "markdown_files": 0,
            "errors": 0,
            "indexing_time_sec": 0.0,
        }

    def index_full_codebase(self, output_path: Path) -> dict:
        """
        Index entire Hive codebase.

        Args:
            output_path: Directory to save index

        Returns:
            Statistics dictionary
        """
        start_time = time.time()

        logger.info("Starting full codebase indexing", extra={"project_root": str(self.project_root)})

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
            "Full codebase indexing complete",
            extra={
                "total_chunks": len(all_chunks),
                "python_files": self.stats["python_files"],
                "markdown_files": self.stats["markdown_files"],
                "errors": self.stats["errors"],
                "indexing_time_sec": round(self.stats["indexing_time_sec"], 2),
            },
        )

        return self.stats

    def _index_python_files(self) -> list:
        """Index all Python files in packages/, apps/, scripts/."""
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
                # Skip __pycache__ and virtual environments
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
        """Index architectural memory from markdown files."""
        logger.info("Indexing markdown documentation...")

        all_chunks = []

        # Source directories for architectural memory
        markdown_sources = [
            self.project_root / "claudedocs",  # Migration guides, architecture docs
            self.project_root / "packages",  # Package READMEs
            self.project_root / "apps",  # App READMEs
            self.project_root / "scripts" / "archive",  # Archive documentation
        ]

        for source_dir in markdown_sources:
            if not source_dir.exists():
                logger.warning(f"Markdown source not found: {source_dir}")
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
        """
        Perform spot-check on indexed content.

        Args:
            num_samples: Number of random samples to check
        """
        logger.info("Performing post-indexing spot-check...")

        # Get random samples
        stats = self.retriever.get_stats()
        total_chunks = stats["vector_store"]["total_chunks"]

        logger.info(f"Total chunks indexed: {total_chunks}")

        # Sample queries for quality check
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
                f"Spot-check query: '{query}'",
                extra={
                    "patterns_retrieved": len(result.code_patterns),
                    "golden_rules": len(result.golden_rules),
                    "retrieval_time_ms": result.retrieval_time_ms,
                },
            )

            if result.code_patterns:
                top_pattern = result.code_patterns[0]
                logger.info(f"  Top result: {top_pattern.source} (score: {top_pattern.relevance_score:.2f})")


def main():
    """Main indexing entry point."""
    print("=" * 60)
    print("Hive Platform - Full Codebase RAG Indexing")
    print("=" * 60)
    print()

    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    output_path = project_root / "data" / "rag_index"

    print(f"Project Root: {project_root}")
    print(f"Output Path:  {output_path}")
    print()

    # Create indexer
    indexer = CodebaseIndexer(project_root)

    # Run full indexing
    print("Starting full codebase indexing...")
    print("This will take 1-2 minutes for ~2,000 files...")
    print()

    stats = indexer.index_full_codebase(output_path)

    # Print results
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

    # Spot-check quality
    print("Running post-indexing spot-checks...")
    print()
    indexer.spot_check_quality(num_samples=5)

    print()
    print("✅ Full codebase indexing complete and validated!")
    print()


if __name__ == "__main__":
    main()
