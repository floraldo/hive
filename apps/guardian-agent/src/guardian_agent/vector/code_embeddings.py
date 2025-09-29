"""Code embedding generation for semantic search."""

import ast
import hashlib
from pathlib import Path
from typing import Any

from hive_ai.vector import EmbeddingModel
from hive_cache import CacheClient
from hive_logging import get_logger

logger = get_logger(__name__)


class CodeEmbeddingGenerator:
    """
    Generates embeddings for code snippets to enable semantic search.

    Uses a combination of structural features and semantic understanding
    to create rich embeddings for code pattern matching.
    """

    def __init__(
        self,
        model_name: str = "text-embedding-ada-002",
        cache_embeddings: bool = True,
    ) -> None:
        """Initialize the embedding generator."""
        self.embedding_model = EmbeddingModel(model_name=model_name)

        # Cache for embeddings
        self.cache = CacheClient(ttl_seconds=86400) if cache_embeddings else None

        logger.info("CodeEmbeddingGenerator initialized with model %s", model_name)

    async def generate_file_embeddings(
        self,
        file_path: Path,
        content: str,
        chunk_size: int = 50,
        overlap: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Generate embeddings for a file using sliding window approach.

        Args:
            file_path: Path to the file
            content: File content
            chunk_size: Lines per chunk
            overlap: Overlapping lines between chunks

        Returns:
            List of embedding dictionaries with metadata
        """
        embeddings = []
        lines = content.split("\n")

        # Parse AST for structural information
        try:
            tree = ast.parse(content)
            structure_info = self._extract_structure(tree)
        except (SyntaxError, ValueError, TypeError):
            # Code may not be valid Python - proceed without AST info
            structure_info = {}

        # Generate chunks with sliding window
        for i in range(0, len(lines), chunk_size - overlap):
            chunk_lines = lines[i : i + chunk_size]
            chunk_content = "\n".join(chunk_lines)

            # Skip empty or trivial chunks
            if len(chunk_content.strip()) < 10:
                continue

            # Check cache
            cache_key = self._get_cache_key(chunk_content)
            if self.cache:
                cached_embedding = await self.cache.get_async(cache_key)
                if cached_embedding:
                    embeddings.append(cached_embedding)
                    continue

            # Generate embedding with context
            context = self._build_context(
                chunk_content,
                file_path,
                start_line=i + 1,
                end_line=min(i + chunk_size, len(lines)),
                structure_info=structure_info,
            )

            embedding_vector = await self.embedding_model.embed(context)

            embedding_data = {
                "file_path": str(file_path),
                "start_line": i + 1,
                "end_line": min(i + chunk_size, len(lines)),
                "content": chunk_content,
                "embedding": embedding_vector,
                "metadata": {
                    "language": self._get_language(file_path),
                    "has_functions": self._has_functions(chunk_content),
                    "has_classes": self._has_classes(chunk_content),
                    "complexity_estimate": self._estimate_complexity(chunk_content),
                },
            }

            # Cache the embedding
            if self.cache:
                await self.cache.set_async(cache_key, embedding_data)

            embeddings.append(embedding_data)

        logger.info(
            "Generated %d embeddings for %s",
            len(embeddings),
            file_path,
        )

        return embeddings

    async def generate_pattern_embedding(
        self,
        pattern: str,
        pattern_type: str = "code",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate embedding for a specific code pattern.

        Args:
            pattern: The code pattern
            pattern_type: Type of pattern (code, error, antipattern)
            metadata: Additional metadata

        Returns:
            Embedding dictionary
        """
        # Check cache
        cache_key = self._get_cache_key(f"{pattern_type}:{pattern}")
        if self.cache:
            cached = await self.cache.get_async(cache_key)
            if cached:
                return cached

        # Build context for pattern
        context = self._build_pattern_context(pattern, pattern_type, metadata)

        # Generate embedding
        embedding_vector = await self.embedding_model.embed(context)

        embedding_data = {
            "pattern": pattern,
            "pattern_type": pattern_type,
            "embedding": embedding_vector,
            "metadata": metadata or {},
        }

        # Cache
        if self.cache:
            await self.cache.set_async(cache_key, embedding_data)

        return embedding_data

    def _extract_structure(self, tree: ast.AST) -> dict[str, Any]:
        """Extract structural information from AST."""
        structure = {
            "classes": [],
            "functions": [],
            "imports": [],
            "global_vars": [],
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                structure["classes"].append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                    }
                )
            elif isinstance(node, ast.FunctionDef):
                # Only top-level functions
                structure["functions"].append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                    }
                )
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        structure["imports"].append(alias.name)
                else:
                    structure["imports"].append(node.module or "")

        return structure

    def _build_context(
        self,
        chunk_content: str,
        file_path: Path,
        start_line: int,
        end_line: int,
        structure_info: dict[str, Any],
    ) -> str:
        """Build enriched context for embedding generation."""
        # Include structural context
        relevant_functions = [
            f["name"] for f in structure_info.get("functions", []) if start_line <= f["line"] <= end_line
        ]

        relevant_classes = [c["name"] for c in structure_info.get("classes", []) if start_line <= c["line"] <= end_line]

        context_parts = [
            f"File: {file_path.name}",
            f"Language: {self._get_language(file_path)}",
        ]

        if relevant_functions:
            context_parts.append(f"Functions: {', '.join(relevant_functions)}")

        if relevant_classes:
            context_parts.append(f"Classes: {', '.join(relevant_classes)}")

        context_parts.append(f"\nCode:\n{chunk_content}")

        return "\n".join(context_parts)

    def _build_pattern_context(
        self,
        pattern: str,
        pattern_type: str,
        metadata: dict[str, Any] | None,
    ) -> str:
        """Build context for pattern embedding."""
        context_parts = [
            f"Pattern Type: {pattern_type}",
        ]

        if metadata:
            if "description" in metadata:
                context_parts.append(f"Description: {metadata['description']}")
            if "category" in metadata:
                context_parts.append(f"Category: {metadata['category']}")
            if "severity" in metadata:
                context_parts.append(f"Severity: {metadata['severity']}")

        context_parts.append(f"\nPattern:\n{pattern}")

        return "\n".join(context_parts)

    def _get_cache_key(self, content: str) -> str:
        """Generate cache key for content."""
        return f"embedding:{hashlib.md5(content.encode()).hexdigest()}"

    def _get_language(self, file_path: Path) -> str:
        """Determine language from file extension."""
        extension_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
        }
        return extension_map.get(file_path.suffix.lower(), "Unknown")

    def _has_functions(self, content: str) -> bool:
        """Check if content has function definitions."""
        return "def " in content or "function " in content or "func " in content

    def _has_classes(self, content: str) -> bool:
        """Check if content has class definitions."""
        return "class " in content

    def _estimate_complexity(self, content: str) -> int:
        """Estimate complexity of code chunk."""
        complexity = 1

        # Count control flow keywords
        keywords = ["if", "else", "elif", "for", "while", "try", "except", "finally"]
        for keyword in keywords:
            complexity += content.count(f" {keyword} ") + content.count(f"\n{keyword} ")

        return min(complexity, 10)  # Cap at 10
