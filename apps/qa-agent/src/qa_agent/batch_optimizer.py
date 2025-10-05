"""Batch Optimizer - Intelligent Violation Batching.

Groups violations into optimal batches for processing efficiency,
considering similarity, file proximity, and worker capacity.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class BatchOptimizer:
    """Intelligent violation batching for efficient processing.

    Batching strategies:
    1. **By Type**: Group similar violation types together
    2. **By File**: Group violations in same/nearby files
    3. **By Complexity**: Separate simple from complex violations
    4. **By Priority**: Critical > Error > Warning

    Goals:
    - Maximize Chimera agent throughput (batch simple fixes)
    - Minimize CC worker spawning (batch complex violations)
    - Respect worker capacity constraints

    Example:
        optimizer = BatchOptimizer(max_batch_size=20)
        batches = optimizer.create_batches(violations)
        # Returns optimized violation batches
    """

    def __init__(
        self,
        max_batch_size: int = 20,
        max_files_per_batch: int = 10,
    ):
        """Initialize batch optimizer.

        Args:
            max_batch_size: Maximum violations per batch
            max_files_per_batch: Maximum files per batch
        """
        self.max_batch_size = max_batch_size
        self.max_files_per_batch = max_files_per_batch
        self.logger = logger

    def create_batches(
        self,
        violations: list[dict[str, Any]],
        strategy: str = "auto",
    ) -> list[list[dict[str, Any]]]:
        """Create optimized batches from violations.

        Args:
            violations: List of violations to batch
            strategy: Batching strategy ('auto', 'by_type', 'by_file', 'by_complexity')

        Returns:
            List of violation batches
        """
        if not violations:
            return []

        self.logger.info(
            f"Creating batches for {len(violations)} violations "
            f"(strategy: {strategy})"
        )

        # Select batching strategy
        if strategy == "by_type":
            batches = self._batch_by_type(violations)
        elif strategy == "by_file":
            batches = self._batch_by_file(violations)
        elif strategy == "by_complexity":
            batches = self._batch_by_complexity(violations)
        else:  # auto
            batches = self._batch_auto(violations)

        # Ensure batch size constraints
        batches = self._enforce_batch_constraints(batches)

        self.logger.info(
            f"Created {len(batches)} batches "
            f"(avg size: {sum(len(b) for b in batches) / len(batches):.1f})"
        )

        return batches

    def _batch_by_type(self, violations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Batch violations by type.

        Groups violations of the same type together for efficient processing.

        Args:
            violations: Violations to batch

        Returns:
            List of batches grouped by type
        """
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for violation in violations:
            vtype = violation.get("type", "unknown")
            by_type[vtype].append(violation)

        # Convert to list of batches
        batches = list(by_type.values())

        self.logger.info(f"Batched by type: {len(batches)} type groups")

        return batches

    def _batch_by_file(self, violations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Batch violations by file/directory.

        Groups violations in same or nearby files for locality.

        Args:
            violations: Violations to batch

        Returns:
            List of batches grouped by file proximity
        """
        by_directory: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for violation in violations:
            file_path = violation.get("file", "")
            if not file_path:
                by_directory["_no_file"].append(violation)
                continue

            # Group by parent directory
            directory = str(Path(file_path).parent)
            by_directory[directory].append(violation)

        # Convert to list of batches
        batches = list(by_directory.values())

        self.logger.info(f"Batched by file: {len(batches)} directory groups")

        return batches

    def _batch_by_complexity(self, violations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Batch violations by complexity level.

        Separates simple (Chimera) from complex (CC worker) violations.

        Args:
            violations: Violations to batch

        Returns:
            List of batches grouped by complexity
        """
        from .complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()

        # Score each violation individually
        simple_violations = []
        medium_violations = []
        complex_violations = []

        for violation in violations:
            # Score single violation
            score = scorer.score([violation])

            if score < 0.3:
                simple_violations.append(violation)
            elif score < 0.7:
                medium_violations.append(violation)
            else:
                complex_violations.append(violation)

        # Create batches
        batches = []
        if simple_violations:
            batches.append(simple_violations)
        if medium_violations:
            batches.append(medium_violations)
        if complex_violations:
            batches.append(complex_violations)

        self.logger.info(
            f"Batched by complexity: "
            f"{len(simple_violations)} simple, "
            f"{len(medium_violations)} medium, "
            f"{len(complex_violations)} complex"
        )

        return batches

    def _batch_auto(self, violations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Auto-select best batching strategy.

        Analyzes violations and chooses optimal strategy.

        Args:
            violations: Violations to batch

        Returns:
            Optimized batches
        """
        # Analyze violation characteristics
        unique_types = len({v.get("type") for v in violations})
        unique_files = len({v.get("file") for v in violations if v.get("file")})
        total_violations = len(violations)

        # Decision logic
        if unique_types <= 3:
            # Few violation types -> batch by type for efficiency
            self.logger.info("Auto: Batching by type (few unique types)")
            return self._batch_by_type(violations)

        elif unique_files <= 5:
            # Few files -> batch by file for locality
            self.logger.info("Auto: Batching by file (few unique files)")
            return self._batch_by_file(violations)

        elif total_violations > 50:
            # Many violations -> batch by complexity to separate workloads
            self.logger.info("Auto: Batching by complexity (many violations)")
            return self._batch_by_complexity(violations)

        else:
            # Default: batch by type
            self.logger.info("Auto: Batching by type (default)")
            return self._batch_by_type(violations)

    def _enforce_batch_constraints(
        self,
        batches: list[list[dict[str, Any]]],
    ) -> list[list[dict[str, Any]]]:
        """Enforce batch size and file count constraints.

        Splits large batches to respect limits.

        Args:
            batches: Input batches

        Returns:
            Constrained batches
        """
        constrained_batches = []

        for batch in batches:
            # Check batch size
            if len(batch) <= self.max_batch_size:
                constrained_batches.append(batch)
                continue

            # Split large batch
            self.logger.info(
                f"Splitting large batch ({len(batch)} violations) "
                f"into chunks of {self.max_batch_size}"
            )

            for i in range(0, len(batch), self.max_batch_size):
                chunk = batch[i : i + self.max_batch_size]
                constrained_batches.append(chunk)

        return constrained_batches

    def prioritize_batches(
        self,
        batches: list[list[dict[str, Any]]],
    ) -> list[list[dict[str, Any]]]:
        """Prioritize batches by severity and complexity.

        Orders batches for optimal processing:
        1. Critical violations (highest priority)
        2. Simple violations (quick wins)
        3. Complex violations (require CC workers)

        Args:
            batches: Input batches

        Returns:
            Prioritized batches (ordered by priority)
        """
        from .complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()

        # Score each batch
        batch_scores = []
        for batch in batches:
            # Check for critical violations
            has_critical = any(
                v.get("severity", "").upper() == "CRITICAL" for v in batch
            )

            # Calculate complexity
            complexity = scorer.score(batch)

            # Priority score (lower = higher priority)
            # Critical violations: priority 0
            # Simple violations (low complexity): priority 1
            # Complex violations: priority 2
            if has_critical:
                priority = 0
            elif complexity < 0.3:
                priority = 1
            else:
                priority = 2

            batch_scores.append((batch, priority, complexity))

        # Sort by priority (ascending), then by complexity (ascending for same priority)
        batch_scores.sort(key=lambda x: (x[1], x[2]))

        # Extract batches in priority order
        prioritized_batches = [b[0] for b in batch_scores]

        self.logger.info("Batches prioritized by severity and complexity")

        return prioritized_batches


__all__ = ["BatchOptimizer"]
