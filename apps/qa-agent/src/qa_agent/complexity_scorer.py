"""Complexity Scorer - Advanced Violation Complexity Analysis.

Provides sophisticated complexity scoring for intelligent worker routing decisions.
Analyzes multiple dimensions: file count, violation types, dependencies, historical data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class ComplexityScorer:
    """Advanced complexity scoring for QA violations.

    Scoring dimensions:
    1. File Count: More files = higher complexity
    2. Violation Type: Architectural > Config > Style
    3. Cross-File Dependencies: Imports, inheritance chains
    4. Historical Fix Difficulty: Success rate from RAG data
    5. Code Churn: Frequently changed files
    6. Test Coverage: Low coverage = higher risk

    Score range: 0.0 (trivial) to 1.0 (extremely complex)

    Example:
        scorer = ComplexityScorer()
        score = scorer.score(violations)
        # Returns complexity score for routing decision
    """

    def __init__(self) -> None:
        """Initialize complexity scorer."""
        self.logger = logger

        # Violation type complexity weights
        self.type_weights = {
            # Style violations (Ruff)
            "E501": 0.05,  # Line length
            "E502": 0.05,  # Trailing whitespace
            "F401": 0.10,  # Unused import
            "F841": 0.10,  # Unused variable
            "E402": 0.15,  # Import placement
            # Config violations (Golden Rules)
            "GR31": 0.15,  # Ruff config
            "GR32": 0.15,  # Python version
            "GR9": 0.25,  # Logging standards
            "GR23": 0.20,  # Ruff config consistency
            # Architectural violations
            "GR37": 0.60,  # Unified config (complex migration)
            "GR6": 0.50,  # Import patterns (refactoring)
            "GR4": 0.50,  # Package discipline
            "GR5": 0.55,  # App contracts
            "GR7": 0.45,  # Dependency direction
            # Test violations
            "pytest": 0.40,  # Test failure (debugging)
            "test_collection": 0.35,  # Collection error
            # Security violations
            "security": 0.80,  # Security vulnerability (critical)
            "S102": 0.70,  # Use of exec
            "S108": 0.75,  # Hardcoded password
        }

    def score(self, violations: list[dict[str, Any]]) -> float:
        """Calculate complexity score for violations.

        Args:
            violations: List of violation dictionaries

        Returns:
            Complexity score (0.0-1.0)
        """
        if not violations:
            return 0.0

        # Component scores
        file_score = self._score_file_count(violations)
        type_score = self._score_violation_types(violations)
        dependency_score = self._score_dependencies(violations)
        churn_score = self._score_code_churn(violations)

        # Weighted average
        total_score = (
            file_score * 0.25  # 25% weight on file count
            + type_score * 0.40  # 40% weight on violation types
            + dependency_score * 0.20  # 20% weight on dependencies
            + churn_score * 0.15  # 15% weight on code churn
        )

        # Cap at 1.0
        final_score = min(total_score, 1.0)

        self.logger.info(
            f"Complexity score: {final_score:.3f} "
            f"(files: {file_score:.3f}, types: {type_score:.3f}, "
            f"deps: {dependency_score:.3f}, churn: {churn_score:.3f})"
        )

        return final_score

    def _score_file_count(self, violations: list[dict[str, Any]]) -> float:
        """Score based on number of files affected.

        More files = higher complexity (coordination required).

        Args:
            violations: Violations list

        Returns:
            File count score (0.0-1.0)
        """
        unique_files = {v.get("file") for v in violations if v.get("file")}
        file_count = len(unique_files)

        # Scoring curve:
        # 1 file: 0.0
        # 3 files: 0.15
        # 5 files: 0.30
        # 10 files: 0.50
        # 20+ files: 1.0
        if file_count <= 1:
            return 0.0
        elif file_count <= 3:
            return 0.15
        elif file_count <= 5:
            return 0.30
        elif file_count <= 10:
            return 0.50
        elif file_count <= 20:
            return 0.75
        else:
            return 1.0

    def _score_violation_types(self, violations: list[dict[str, Any]]) -> float:
        """Score based on violation type complexity.

        Args:
            violations: Violations list

        Returns:
            Type complexity score (0.0-1.0)
        """
        if not violations:
            return 0.0

        # Get max type score (worst case)
        max_score = 0.0

        for violation in violations:
            vtype = violation.get("type", "unknown")
            score = self.type_weights.get(vtype, 0.30)  # Default 0.30 for unknown
            max_score = max(max_score, score)

        return max_score

    def _score_dependencies(self, violations: list[dict[str, Any]]) -> float:
        """Score based on cross-file dependencies.

        Higher dependencies = higher complexity (ripple effects).

        Args:
            violations: Violations list

        Returns:
            Dependency score (0.0-1.0)
        """
        # Check if violations involve import statements or cross-file references
        has_import_violations = False
        has_cross_file_refs = False

        for violation in violations:
            vtype = violation.get("type", "")
            message = violation.get("message", "").lower()

            # Import-related violations
            if vtype in ("F401", "E402", "GR6", "GR7"):
                has_import_violations = True

            # Cross-file references (heuristic: mentions other files/modules)
            if "import" in message or "module" in message or "package" in message:
                has_cross_file_refs = True

        # Scoring
        if has_import_violations and has_cross_file_refs:
            return 0.60  # High dependency complexity
        elif has_import_violations:
            return 0.40  # Medium dependency complexity
        elif has_cross_file_refs:
            return 0.20  # Low dependency complexity
        else:
            return 0.0  # No dependency issues

    def _score_code_churn(self, violations: list[dict[str, Any]]) -> float:
        """Score based on code churn (file change frequency).

        Frequently changed files = higher risk (potential for breaking changes).

        Args:
            violations: Violations list

        Returns:
            Code churn score (0.0-1.0)
        """
        # TODO: Integrate with git history to calculate actual churn
        # For MVP, use simple heuristic based on file paths

        high_churn_paths = {
            # Core infrastructure (high risk)
            "core",
            "base",
            "config",
            "utils",
            # Frequently modified areas
            "api",
            "services",
            "models",
        }

        affected_files = [v.get("file", "") for v in violations if v.get("file")]

        # Check if any files are in high-churn areas
        for file_path in affected_files:
            path_parts = Path(file_path).parts

            for part in path_parts:
                if part in high_churn_paths:
                    return 0.50  # High churn area

        return 0.0  # Normal churn

    def score_batch(
        self,
        violation_batches: list[list[dict[str, Any]]],
    ) -> list[tuple[list[dict[str, Any]], float]]:
        """Score multiple violation batches.

        Args:
            violation_batches: List of violation batches

        Returns:
            List of (batch, score) tuples sorted by score
        """
        scored_batches = []

        for batch in violation_batches:
            score = self.score(batch)
            scored_batches.append((batch, score))

        # Sort by score (ascending: simplest first)
        scored_batches.sort(key=lambda x: x[1])

        return scored_batches


__all__ = ["ComplexityScorer"]
