"""Pattern storage and retrieval for semantic code search."""

import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from hive_ai.vector import VectorStore as HiveVectorStore
from hive_logging import get_logger

logger = get_logger(__name__)


class PatternStore:
    """
    Manages storage and retrieval of code patterns for semantic search.

    Stores embeddings of common patterns, anti-patterns, and best practices
    to enable context-aware code review suggestions.
    """

    def __init__(
        self,
        index_path: Path,
        dimension: int = 1536,  # Default for text-embedding-ada-002
    ) -> None:
        """Initialize the pattern store."""
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)

        self.dimension = dimension
        self.patterns_file = self.index_path / "patterns.json"
        self.embeddings_file = self.index_path / "embeddings.npy"
        self.metadata_file = self.index_path / "metadata.pkl"

        # Load existing patterns
        self.patterns = self._load_patterns()
        self.embeddings = self._load_embeddings()
        self.metadata = self._load_metadata()

        # Initialize Hive vector store for efficient search
        self.vector_store = HiveVectorStore(
            index_path=str(self.index_path / "hive_index"),
            dimension=dimension,
        )

        logger.info(
            "PatternStore initialized with %d patterns",
            len(self.patterns),
        )

    async def add_pattern(
        self,
        pattern_id: str,
        pattern_content: str,
        embedding: np.ndarray,
        pattern_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a new pattern to the store.

        Args:
            pattern_id: Unique identifier for the pattern
            pattern_content: The actual code pattern
            embedding: Embedding vector
            pattern_type: Type of pattern (best_practice, anti_pattern, etc.)
            metadata: Additional metadata
        """
        # Add to in-memory storage
        self.patterns[pattern_id] = {
            "content": pattern_content,
            "type": pattern_type,
            "metadata": metadata or {},
        }

        # Add embedding
        if self.embeddings is None:
            self.embeddings = embedding.reshape(1, -1)
        else:
            self.embeddings = np.vstack([self.embeddings, embedding])

        # Add metadata
        self.metadata[pattern_id] = {
            "index": len(self.embeddings) - 1,
            "type": pattern_type,
            "metadata": metadata or {},
        }

        # Add to vector store
        await self.vector_store.add(
            embedding=embedding,
            metadata={
                "pattern_id": pattern_id,
                "type": pattern_type,
                **(metadata or {}),
            },
        )

        # Persist to disk
        self._save_patterns()
        self._save_embeddings()
        self._save_metadata()

        logger.info("Added pattern %s of type %s", pattern_id, pattern_type)

    async def search_similar_patterns(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        pattern_type: Optional[str] = None,
        threshold: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar patterns.

        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            pattern_type: Filter by pattern type
            threshold: Similarity threshold (0-1)

        Returns:
            List of similar patterns with similarity scores
        """
        # Search using vector store
        results = await self.vector_store.search(
            query=query_embedding,
            k=k * 2 if pattern_type else k,  # Get more if filtering
            threshold=threshold,
        )

        # Filter by pattern type if specified
        if pattern_type:
            results = [r for r in results if r.get("type") == pattern_type]
            results = results[:k]

        # Enrich results with pattern content
        enriched_results = []
        for result in results:
            pattern_id = result.get("pattern_id")
            if pattern_id and pattern_id in self.patterns:
                enriched_results.append(
                    {
                        "pattern_id": pattern_id,
                        "content": self.patterns[pattern_id]["content"],
                        "type": self.patterns[pattern_id]["type"],
                        "similarity": result.get("similarity", 0),
                        "metadata": self.patterns[pattern_id].get("metadata", {}),
                    }
                )

        return enriched_results

    async def find_anti_patterns(
        self,
        code_embedding: np.ndarray,
        threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """
        Find anti-patterns in the code.

        Args:
            code_embedding: Embedding of the code to check
            threshold: Similarity threshold

        Returns:
            List of detected anti-patterns
        """
        return await self.search_similar_patterns(
            query_embedding=code_embedding,
            k=10,
            pattern_type="anti_pattern",
            threshold=threshold,
        )

    async def find_best_practices(
        self,
        code_embedding: np.ndarray,
        context: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find relevant best practices for the code.

        Args:
            code_embedding: Embedding of the code
            context: Additional context (e.g., "error_handling", "performance")

        Returns:
            List of relevant best practices
        """
        results = await self.search_similar_patterns(
            query_embedding=code_embedding,
            k=5,
            pattern_type="best_practice",
            threshold=0.7,
        )

        # Filter by context if provided
        if context:
            results = [r for r in results if context in r.get("metadata", {}).get("categories", [])]

        return results

    async def get_fix_suggestions(
        self,
        violation_embedding: np.ndarray,
        violation_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Get fix suggestions for a violation.

        Args:
            violation_embedding: Embedding of the violation
            violation_type: Type of violation

        Returns:
            List of fix suggestions
        """
        # Search for similar violations with fixes
        results = await self.search_similar_patterns(
            query_embedding=violation_embedding,
            k=3,
            pattern_type="fix",
            threshold=0.8,
        )

        # Filter by violation type
        relevant_fixes = [r for r in results if r.get("metadata", {}).get("fixes_violation") == violation_type]

        return relevant_fixes

    def initialize_default_patterns(self) -> None:
        """Initialize store with default patterns."""
        default_patterns = [
            {
                "id": "singleton_pattern",
                "content": """class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance""",
                "type": "design_pattern",
                "metadata": {
                    "name": "Singleton Pattern",
                    "categories": ["design_patterns", "creational"],
                    "description": "Ensures a class has only one instance",
                },
            },
            {
                "id": "sql_injection",
                "content": """# Anti-pattern
query = f"SELECT * FROM users WHERE id = {user_id}"
cursor.execute(query)""",
                "type": "anti_pattern",
                "metadata": {
                    "name": "SQL Injection Vulnerability",
                    "categories": ["security", "database"],
                    "severity": "critical",
                    "fix": "Use parameterized queries",
                },
            },
            {
                "id": "sql_injection_fix",
                "content": """# Best practice
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))""",
                "type": "fix",
                "metadata": {
                    "fixes_violation": "sql_injection",
                    "categories": ["security", "database"],
                },
            },
            {
                "id": "context_manager",
                "content": """with open('file.txt', 'r') as f:
    content = f.read()
    # File automatically closed""",
                "type": "best_practice",
                "metadata": {
                    "name": "Context Manager Usage",
                    "categories": ["resource_management", "pythonic"],
                    "description": "Ensures proper resource cleanup",
                },
            },
        ]

        logger.info("Initializing default patterns...")
        # Note: In a real implementation, would generate embeddings for these

    def _load_patterns(self) -> Dict[str, Any]:
        """Load patterns from disk."""
        if self.patterns_file.exists():
            with open(self.patterns_file) as f:
                return json.load(f)
        return {}

    def _save_patterns(self) -> None:
        """Save patterns to disk."""
        with open(self.patterns_file, "w") as f:
            json.dump(self.patterns, f, indent=2)

    def _load_embeddings(self) -> Optional[np.ndarray]:
        """Load embeddings from disk."""
        if self.embeddings_file.exists():
            return np.load(self.embeddings_file)
        return None

    def _save_embeddings(self) -> None:
        """Save embeddings to disk."""
        if self.embeddings is not None:
            np.save(self.embeddings_file, self.embeddings)

    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from disk."""
        if self.metadata_file.exists():
            with open(self.metadata_file, "rb") as f:
                return pickle.load(f)
        return {}

    def _save_metadata(self) -> None:
        """Save metadata to disk."""
        with open(self.metadata_file, "wb") as f:
            pickle.dump(self.metadata, f)
