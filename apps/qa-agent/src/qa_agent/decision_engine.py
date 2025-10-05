"""Decision Engine - Intelligent Worker Routing.

Analyzes violations and decides whether to route to:
- Chimera agents (lightweight, fast auto-fix)
- CC workers headless (complex reasoning)
- CC workers interactive (HITL for critical issues)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class WorkerDecision:
    """Decision result for worker routing.

    Attributes:
        worker_type: Type of worker to use ('chimera-agent', 'cc-worker-headless', 'cc-worker-with-hitl')
        reason: Human-readable explanation of decision
        complexity_score: Computed complexity score (0.0-1.0)
        rag_confidence: RAG pattern match confidence (0.0-1.0)
        rag_context: Retrieved RAG patterns for worker context
    """

    worker_type: str
    reason: str
    complexity_score: float
    rag_confidence: float
    rag_context: list[dict[str, Any]]


class WorkerDecisionEngine:
    """Intelligent routing engine for QA violations.

    Decision algorithm:
    1. Score complexity (file count, violation type, historical data)
    2. Check RAG pattern confidence
    3. Apply decision matrix:
       - CRITICAL severity → cc-worker-with-hitl (always)
       - Complexity >0.7 → cc-worker-headless
       - Confidence >0.8 AND simple pattern → chimera-agent
       - Default → chimera-agent (can escalate later)

    Example:
        engine = WorkerDecisionEngine(rag_engine)
        decision = await engine.decide(violations)
        # Returns WorkerDecision with routing instructions
    """

    def __init__(self, rag_engine: Any) -> None:
        """Initialize decision engine.

        Args:
            rag_engine: RAG engine for pattern retrieval and confidence scoring
        """
        self.rag_engine = rag_engine
        self.logger = logger

        # Complexity thresholds
        self.complexity_threshold_high = 0.7
        self.confidence_threshold_high = 0.8

    async def decide(self, violations: list[dict[str, Any]]) -> WorkerDecision:
        """Analyze violations and decide worker type.

        Args:
            violations: List of violation dictionaries with metadata

        Returns:
            WorkerDecision with routing instructions and RAG context
        """
        self.logger.info(f"Analyzing {len(violations)} violations for routing decision...")

        # Score complexity
        complexity_score = self._calculate_complexity(violations)

        # Retrieve RAG patterns and calculate confidence
        rag_patterns = await self._retrieve_rag_patterns(violations)
        rag_confidence = self._calculate_rag_confidence(rag_patterns, violations)

        self.logger.info(f"Complexity: {complexity_score:.2f}, RAG confidence: {rag_confidence:.2f}")

        # Apply decision matrix
        decision = self._apply_decision_matrix(
            violations=violations,
            complexity_score=complexity_score,
            rag_confidence=rag_confidence,
            rag_patterns=rag_patterns,
        )

        self.logger.info(f"Decision: {decision.worker_type} - {decision.reason}")
        return decision

    def _calculate_complexity(self, violations: list[dict[str, Any]]) -> float:
        """Calculate complexity score for violations.

        Factors:
        - Number of files affected (more files = higher complexity)
        - Violation type (architectural > config > style)
        - Cross-file dependencies
        - Historical fix difficulty

        Args:
            violations: List of violations

        Returns:
            Complexity score between 0.0 (simple) and 1.0 (complex)
        """
        if not violations:
            return 0.0

        # Base complexity from violation count
        base_complexity = min(len(violations) / 20.0, 0.5)  # Cap at 0.5 for count alone

        # File count factor
        unique_files = len({v.get("file") for v in violations if v.get("file")})
        file_complexity = min(unique_files / 10.0, 0.3)  # Cap at 0.3

        # Violation type factor
        type_complexity = self._score_violation_types(violations)

        # Combined score
        total_complexity = base_complexity + file_complexity + type_complexity

        return min(total_complexity, 1.0)  # Cap at 1.0

    def _score_violation_types(self, violations: list[dict[str, Any]]) -> float:
        """Score complexity based on violation types.

        Complexity levels:
        - Style (Ruff E501, F401): 0.0-0.1 (simple auto-fix)
        - Config (Golden Rule 31, 32): 0.1-0.2 (file edits)
        - Architectural (Golden Rule 37, 6): 0.3-0.5 (complex refactoring)
        - Tests (pytest failures): 0.2-0.4 (debugging required)
        - Security: 0.5-0.7 (deep analysis)

        Args:
            violations: List of violations

        Returns:
            Type complexity score (0.0-0.7)
        """
        if not violations:
            return 0.0

        type_scores = {
            # Style violations (Ruff)
            "E501": 0.05,  # Line length
            "F401": 0.05,  # Unused import
            "E402": 0.1,  # Import placement
            # Config violations (Golden Rules)
            "GR31": 0.15,  # Ruff config
            "GR32": 0.15,  # Python version
            "GR9": 0.2,  # Logging standards
            # Architectural violations
            "GR37": 0.5,  # Unified config
            "GR6": 0.4,  # Import patterns
            "GR4": 0.4,  # Package discipline
            # Test failures
            "pytest": 0.3,  # Test failure
            # Security
            "security": 0.7,  # Security vulnerability
        }

        # Get max type score (worst case complexity)
        max_score = 0.0
        for violation in violations:
            violation_type = violation.get("type", "unknown")
            score = type_scores.get(violation_type, 0.2)  # Default 0.2 for unknown types
            max_score = max(max_score, score)

        return max_score

    async def _retrieve_rag_patterns(self, violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Retrieve similar fix patterns from RAG engine.

        Args:
            violations: List of violations

        Returns:
            List of RAG patterns with similarity scores
        """
        if not self.rag_engine:
            self.logger.warning("RAG engine not available, returning empty patterns")
            return []

        try:
            # Build query from violations
            query = self._build_rag_query(violations)

            # Retrieve patterns
            patterns = await self.rag_engine.retrieve(query=query, top_k=5)

            return patterns

        except Exception as e:
            self.logger.error(f"RAG retrieval failed: {e}", exc_info=True)
            return []

    def _build_rag_query(self, violations: list[dict[str, Any]]) -> str:
        """Build RAG query from violations.

        Args:
            violations: List of violations

        Returns:
            Query string for RAG retrieval
        """
        if not violations:
            return ""

        # Sample first violation for query
        first = violations[0]
        violation_type = first.get("type", "unknown")
        file_path = first.get("file", "")
        message = first.get("message", "")

        query = f"{violation_type} in {file_path}: {message}"
        return query

    def _calculate_rag_confidence(
        self,
        rag_patterns: list[dict[str, Any]],
        violations: list[dict[str, Any]],
    ) -> float:
        """Calculate confidence in RAG patterns.

        High confidence (>0.8) means we have very similar historical fixes.

        Args:
            rag_patterns: Retrieved RAG patterns
            violations: Current violations

        Returns:
            Confidence score (0.0-1.0)
        """
        if not rag_patterns:
            return 0.0

        # Average similarity scores from top patterns
        similarities = [p.get("similarity", 0.0) for p in rag_patterns[:3]]

        if not similarities:
            return 0.0

        avg_similarity = sum(similarities) / len(similarities)
        return avg_similarity

    def _apply_decision_matrix(
        self,
        violations: list[dict[str, Any]],
        complexity_score: float,
        rag_confidence: float,
        rag_patterns: list[dict[str, Any]],
    ) -> WorkerDecision:
        """Apply decision matrix to route violations.

        Decision rules (in priority order):
        1. CRITICAL severity → cc-worker-with-hitl (always)
        2. Complexity >0.7 → cc-worker-headless
        3. Confidence >0.8 AND batch >5 → chimera-agent
        4. Default → chimera-agent (can escalate later if needed)

        Args:
            violations: List of violations
            complexity_score: Computed complexity
            rag_confidence: RAG pattern confidence
            rag_patterns: Retrieved RAG patterns

        Returns:
            WorkerDecision with routing instructions
        """
        # Rule 1: CRITICAL severity always goes to HITL
        if self._has_critical_violations(violations):
            return WorkerDecision(
                worker_type="cc-worker-with-hitl",
                reason="Critical severity requires human review",
                complexity_score=complexity_score,
                rag_confidence=rag_confidence,
                rag_context=rag_patterns,
            )

        # Rule 2: High complexity goes to headless CC worker
        if complexity_score > self.complexity_threshold_high:
            return WorkerDecision(
                worker_type="cc-worker-headless",
                reason=f"Complex reasoning required (score: {complexity_score:.2f})",
                complexity_score=complexity_score,
                rag_confidence=rag_confidence,
                rag_context=rag_patterns,
            )

        # Rule 3: High confidence batch fixes go to Chimera
        if rag_confidence > self.confidence_threshold_high and len(violations) > 5:
            return WorkerDecision(
                worker_type="chimera-agent",
                reason=f"High-confidence batch fix via RAG patterns (conf: {rag_confidence:.2f})",
                complexity_score=complexity_score,
                rag_confidence=rag_confidence,
                rag_context=rag_patterns,
            )

        # Rule 4: Default to Chimera (lightweight, can escalate later)
        return WorkerDecision(
            worker_type="chimera-agent",
            reason="Lightweight auto-fix attempt (escalates if needed)",
            complexity_score=complexity_score,
            rag_confidence=rag_confidence,
            rag_context=rag_patterns,
        )

    def _has_critical_violations(self, violations: list[dict[str, Any]]) -> bool:
        """Check if any violations have CRITICAL severity.

        Args:
            violations: List of violations

        Returns:
            True if any violation is CRITICAL
        """
        for violation in violations:
            severity = violation.get("severity", "").upper()
            if severity == "CRITICAL":
                return True

        return False


__all__ = ["WorkerDecision", "WorkerDecisionEngine"]
