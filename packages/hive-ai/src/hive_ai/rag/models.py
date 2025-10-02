"""
Data models for RAG system with rich metadata support.

Provides enhanced code chunks with AST-derived metadata, operational context,
and architectural memory for intelligent retrieval and context generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np


class ChunkType(Enum):
    """Types of code chunks."""

    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    MODULE = "module"
    DOCSTRING = "docstring"
    UNKNOWN = "unknown"


@dataclass
class CodeChunk:
    """
    Enhanced code chunk with operational metadata and architectural context.

    Combines AST-derived code structure with operational metadata from
    scripts_metadata.json, USAGE_MATRIX.md, and architectural memory from
    migration reports and deprecation notes.
    """

    # Core content
    code: str
    chunk_type: ChunkType
    file_path: str

    # Embedding (generated lazily)
    embedding: np.ndarray | None = None

    # AST-derived metadata
    signature: str = ""
    imports: list[str] = field(default_factory=list)
    parent_class: str | None = None
    docstring: str = ""
    line_start: int = 0
    line_end: int = 0

    # Operational metadata (from scripts_metadata.json, USAGE_MATRIX.md)
    purpose: str | None = None
    usage_context: str | None = None  # "CI/CD", "Manual", "Testing", etc.
    execution_type: str | None = None  # "utility", "maintenance", "testing"
    dependencies: list[str] = field(default_factory=list)

    # Architectural memory (from archive/, migration reports)
    deprecation_reason: str | None = None
    migration_notes: str | None = None
    is_archived: bool = False
    replacement_pattern: str | None = None  # Points to newer implementation

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    # Quality metadata
    has_tests: bool = False
    test_coverage: float = 0.0
    golden_rule_compliance: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "code": self.code,
            "chunk_type": self.chunk_type.value,
            "file_path": self.file_path,
            "signature": self.signature,
            "imports": self.imports,
            "parent_class": self.parent_class,
            "docstring": self.docstring,
            "line_range": f"{self.line_start}-{self.line_end}",
            "purpose": self.purpose,
            "usage_context": self.usage_context,
            "execution_type": self.execution_type,
            "is_archived": self.is_archived,
            "deprecation_reason": self.deprecation_reason,
        }

    def get_enriched_code(self) -> str:
        """
        Get enriched code for embedding generation.

        Prepends signature and docstring to code for better semantic representation.
        """
        parts = []

        if self.signature:
            parts.append(self.signature)

        if self.docstring:
            parts.append(f'"""{self.docstring}"""')

        parts.append(self.code)

        return "\n".join(parts)


@dataclass
class PatternContext:
    """Code pattern with relevance context for agent prompts."""

    code: str
    source: str  # file_path:signature
    purpose: str | None = None
    relevance_score: float = 0.0
    usage_context: str | None = None
    deprecation_warning: str | None = None


@dataclass
class RuleContext:
    """Golden rule with relevance explanation."""

    rule_number: int
    rule_text: str
    relevance_reason: str
    severity: str = "ERROR"  # CRITICAL, ERROR, WARNING, INFO
    examples: list[str] = field(default_factory=list)


@dataclass
class StructuredContext:
    """
    Structured context for agent prompt generation.

    Provides code patterns, golden rules, and deprecation warnings
    in a format optimized for LLM consumption.
    """

    code_patterns: list[PatternContext] = field(default_factory=list)
    golden_rules: list[RuleContext] = field(default_factory=list)
    deprecation_warnings: list[str] = field(default_factory=list)

    # Metadata
    retrieval_time_ms: float = 0.0
    total_chunks_searched: int = 0
    filters_applied: dict[str, Any] = field(default_factory=dict)

    def to_prompt_section(self) -> str:
        """
        Convert to formatted prompt section for LLM.

        Generates structured markdown sections with code patterns,
        golden rules, and deprecation warnings.
        """
        sections = []

        # Code patterns section
        if self.code_patterns:
            sections.append("--- RELEVANT CODE PATTERNS FROM HIVE ---\n")
            for i, pattern in enumerate(self.code_patterns, 1):
                sections.append(f"PATTERN {i} (from {pattern.source})")
                if pattern.purpose:
                    sections.append(f"Purpose: {pattern.purpose}")
                if pattern.usage_context:
                    sections.append(f"Context: {pattern.usage_context}")
                sections.append(f"Relevance: {pattern.relevance_score:.2f}")
                sections.append(f"```python\n{pattern.code}\n```\n")

        # Golden rules section
        if self.golden_rules:
            sections.append("--- APPLICABLE GOLDEN RULES ---\n")
            for rule in self.golden_rules:
                sections.append(f"Rule #{rule.rule_number} ({rule.severity}): {rule.rule_text}")
                sections.append(f"  Reason: {rule.relevance_reason}\n")

        # Deprecation warnings section
        if self.deprecation_warnings:
            sections.append("⚠️ DEPRECATION WARNINGS ---\n")
            for warning in self.deprecation_warnings:
                sections.append(f"- {warning}\n")

        return "\n".join(sections)


@dataclass
class RetrievalQuery:
    """Query specification for RAG retrieval."""

    query: str
    k: int = 5  # Number of results to return

    # Filters
    exclude_archived: bool = True
    usage_context: str | None = None
    chunk_types: list[ChunkType] = field(default_factory=list)
    file_path_pattern: str | None = None

    # Retrieval strategy
    use_hybrid: bool = True
    semantic_weight: float = 0.7
    keyword_weight: float = 0.3

    # Re-ranking
    use_reranking: bool = False
    rerank_top_k: int = 20


@dataclass
class RetrievalResult:
    """Single retrieval result with metadata."""

    chunk: CodeChunk
    score: float
    retrieval_method: str  # "semantic", "keyword", "hybrid"
    rank: int = 0

    def to_pattern_context(self) -> PatternContext:
        """Convert to PatternContext for prompt generation."""
        deprecation_warning = None
        if self.chunk.is_archived and self.chunk.deprecation_reason:
            deprecation_warning = f"This pattern is archived: {self.chunk.deprecation_reason}"
            if self.chunk.replacement_pattern:
                deprecation_warning += f" Use {self.chunk.replacement_pattern} instead."

        return PatternContext(
            code=self.chunk.code,
            source=f"{self.chunk.file_path}:{self.chunk.signature}",
            purpose=self.chunk.purpose,
            relevance_score=self.score,
            usage_context=self.chunk.usage_context,
            deprecation_warning=deprecation_warning,
        )
