"""
Combined quality metrics for RAG-Guardian integration.

Implements Design Decision 3 (Option C): Combined Quality Score that measures
both RAG retrieval quality (RAGAS metrics) and Guardian output quality.

This provides holistic system evaluation:
- Component Quality: Is the RAG retrieval engine working well?
- System Quality: Does the Guardian produce better code reviews with RAG?
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class RAGQualityMetrics:
    """RAGAS-based RAG retrieval quality metrics."""

    # Core RAGAS metrics
    context_precision: float = 0.0  # % of retrieved contexts that are relevant
    context_recall: float = 0.0  # % of relevant contexts that were retrieved
    faithfulness: float = 0.0  # Answer consistency with context
    answer_relevancy: float = 0.0  # Answer addresses the query

    # Hive-specific metrics
    deprecation_detection_rate: float = 0.0  # % of deprecated patterns detected
    golden_rule_coverage: float = 0.0  # % of applicable rules retrieved

    # Performance
    avg_retrieval_time_ms: float = 0.0
    cache_hit_rate: float = 0.0


@dataclass
class GuardianOutputQuality:
    """Guardian Agent output quality metrics."""

    # Correctness
    golden_rule_compliance_rate: float = 0.0  # % of violations correctly identified
    false_positive_rate: float = 0.0  # % of incorrect violations flagged
    false_negative_rate: float = 0.0  # % of real violations missed

    # Architectural quality
    architectural_consistency_score: float = 0.0  # 0-10 scale, pattern adherence
    deprecation_warning_accuracy: float = 0.0  # % correct deprecation warnings

    # Usability
    actionability_score: float = 0.0  # % of suggestions that are actionable
    review_clarity_score: float = 0.0  # 0-10 scale, human readability

    # Code quality improvement
    code_quality_improvement: float = 0.0  # % improvement after applying suggestions


@dataclass
class CombinedQualityScore:
    """
    Combined quality score for RAG-Guardian system.

    Weighted combination of component (RAG) and system (Guardian) quality.
    """

    # Component scores
    rag_score: float = 0.0  # 0-100
    guardian_score: float = 0.0  # 0-100

    # Weights (must sum to 1.0)
    rag_weight: float = 0.4  # RAG quality contributes 40%
    guardian_weight: float = 0.6  # Guardian output quality contributes 60%

    # Combined score
    combined_score: float = 0.0  # 0-100

    # Detailed metrics
    rag_metrics: RAGQualityMetrics = field(default_factory=RAGQualityMetrics)
    guardian_metrics: GuardianOutputQuality = field(default_factory=GuardianOutputQuality)

    # Metadata
    evaluation_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    golden_set_size: int = 0
    test_cases_passed: int = 0
    test_cases_failed: int = 0

    def calculate(self) -> float:
        """
        Calculate combined quality score.

        Returns:
            Combined score (0-100)
        """
        # Calculate RAG score from RAGAS metrics
        self.rag_score = self._calculate_rag_score()

        # Calculate Guardian score from output quality
        self.guardian_score = self._calculate_guardian_score()

        # Weighted combination
        self.combined_score = self.rag_score * self.rag_weight + self.guardian_score * self.guardian_weight

        return self.combined_score

    def _calculate_rag_score(self) -> float:
        """Calculate RAG component score (0-100)."""
        # Core RAGAS metrics (70% weight)
        ragas_score = (
            self.rag_metrics.context_precision * 0.25
            + self.rag_metrics.context_recall * 0.25
            + self.rag_metrics.faithfulness * 0.10
            + self.rag_metrics.answer_relevancy * 0.10
        )

        # Hive-specific metrics (20% weight)
        hive_score = self.rag_metrics.deprecation_detection_rate * 0.10 + self.rag_metrics.golden_rule_coverage * 0.10

        # Performance bonus (10% weight)
        perf_bonus = min(self.rag_metrics.cache_hit_rate, 1.0) * 0.10

        return (ragas_score + hive_score + perf_bonus) * 100

    def _calculate_guardian_score(self) -> float:
        """Calculate Guardian output quality score (0-100)."""
        # Correctness (50% weight)
        correctness = (
            self.guardian_metrics.golden_rule_compliance_rate * 0.30
            + (1.0 - self.guardian_metrics.false_positive_rate) * 0.10
            + (1.0 - self.guardian_metrics.false_negative_rate) * 0.10
        )

        # Architectural quality (30% weight)
        arch_quality = (
            self.guardian_metrics.architectural_consistency_score / 10.0
        ) * 0.15 + self.guardian_metrics.deprecation_warning_accuracy * 0.15

        # Usability (20% weight)
        usability = (
            self.guardian_metrics.actionability_score * 0.10
            + (self.guardian_metrics.review_clarity_score / 10.0) * 0.10
        )

        return (correctness + arch_quality + usability) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "combined_score": round(self.combined_score, 2),
            "rag_score": round(self.rag_score, 2),
            "guardian_score": round(self.guardian_score, 2),
            "weights": {
                "rag_weight": self.rag_weight,
                "guardian_weight": self.guardian_weight,
            },
            "rag_metrics": {
                "context_precision": round(self.rag_metrics.context_precision, 4),
                "context_recall": round(self.rag_metrics.context_recall, 4),
                "faithfulness": round(self.rag_metrics.faithfulness, 4),
                "answer_relevancy": round(self.rag_metrics.answer_relevancy, 4),
                "deprecation_detection_rate": round(self.rag_metrics.deprecation_detection_rate, 4),
                "golden_rule_coverage": round(self.rag_metrics.golden_rule_coverage, 4),
                "avg_retrieval_time_ms": round(self.rag_metrics.avg_retrieval_time_ms, 2),
                "cache_hit_rate": round(self.rag_metrics.cache_hit_rate, 4),
            },
            "guardian_metrics": {
                "golden_rule_compliance_rate": round(self.guardian_metrics.golden_rule_compliance_rate, 4),
                "false_positive_rate": round(self.guardian_metrics.false_positive_rate, 4),
                "false_negative_rate": round(self.guardian_metrics.false_negative_rate, 4),
                "architectural_consistency_score": round(self.guardian_metrics.architectural_consistency_score, 2),
                "deprecation_warning_accuracy": round(self.guardian_metrics.deprecation_warning_accuracy, 4),
                "actionability_score": round(self.guardian_metrics.actionability_score, 4),
                "review_clarity_score": round(self.guardian_metrics.review_clarity_score, 2),
                "code_quality_improvement": round(self.guardian_metrics.code_quality_improvement, 4),
            },
            "metadata": {
                "evaluation_timestamp": self.evaluation_timestamp,
                "golden_set_size": self.golden_set_size,
                "test_cases_passed": self.test_cases_passed,
                "test_cases_failed": self.test_cases_failed,
                "pass_rate": (
                    round(self.test_cases_passed / self.golden_set_size, 4) if self.golden_set_size > 0 else 0.0
                ),
            },
        }

    def generate_report(self) -> str:
        """Generate human-readable quality report."""
        lines = [
            "RAG-Guardian Combined Quality Report",
            "=" * 50,
            "",
            f"Combined Quality Score: {self.combined_score:.1f}/100",
            "",
            "Component Scores:",
            f"  - RAG Retrieval: {self.rag_score:.1f}/100 (weight: {self.rag_weight * 100:.0f}%)",
            f"  - Guardian Output: {self.guardian_score:.1f}/100 (weight: {self.guardian_weight * 100:.0f}%)",
            "",
            "RAG Retrieval Quality (RAGAS):",
            f"  - Context Precision:  {self.rag_metrics.context_precision:.1%}",
            f"  - Context Recall:     {self.rag_metrics.context_recall:.1%}",
            f"  - Faithfulness:       {self.rag_metrics.faithfulness:.1%}",
            f"  - Answer Relevancy:   {self.rag_metrics.answer_relevancy:.1%}",
            "",
            "Hive-Specific RAG Quality:",
            f"  - Deprecation Detection: {self.rag_metrics.deprecation_detection_rate:.1%}",
            f"  - Golden Rule Coverage:  {self.rag_metrics.golden_rule_coverage:.1%}",
            "",
            "Guardian Output Quality:",
            f"  - Golden Rule Compliance: {self.guardian_metrics.golden_rule_compliance_rate:.1%}",
            f"  - False Positives:        {self.guardian_metrics.false_positive_rate:.1%}",
            f"  - False Negatives:        {self.guardian_metrics.false_negative_rate:.1%}",
            f"  - Architectural Score:    {self.guardian_metrics.architectural_consistency_score:.1f}/10",
            f"  - Deprecation Accuracy:   {self.guardian_metrics.deprecation_warning_accuracy:.1%}",
            f"  - Actionability:          {self.guardian_metrics.actionability_score:.1%}",
            f"  - Review Clarity:         {self.guardian_metrics.review_clarity_score:.1f}/10",
            "",
            "Performance:",
            f"  - Avg Retrieval Time: {self.rag_metrics.avg_retrieval_time_ms:.1f}ms",
            f"  - Cache Hit Rate:     {self.rag_metrics.cache_hit_rate:.1%}",
            "",
            "Test Results:",
            f"  - Golden Set Size: {self.golden_set_size}",
            f"  - Passed: {self.test_cases_passed}",
            f"  - Failed: {self.test_cases_failed}",
            f"  - Pass Rate: {(self.test_cases_passed / self.golden_set_size if self.golden_set_size > 0 else 0):.1%}",
            "",
            f"Evaluation Time: {self.evaluation_timestamp}",
            "=" * 50,
        ]

        return "\n".join(lines)


class QualityBaseline:
    """
    Baseline quality tracker for regression detection.

    Stores baseline metrics and detects regressions across runs.
    """

    def __init__(self, baseline_file: Path = Path("tests/rag/baseline_results.json")):
        """
        Initialize baseline tracker.

        Args:
            baseline_file: Path to baseline results JSON file
        """
        self.baseline_file = baseline_file
        self.baseline: dict[str, Any] | None = None

        if baseline_file.exists():
            self.load_baseline()

    def load_baseline(self) -> None:
        """Load baseline from disk."""
        with open(self.baseline_file, encoding="utf-8") as f:
            self.baseline = json.load(f)

        logger.info(f"Loaded baseline from {self.baseline_file}")

    def save_baseline(self, score: CombinedQualityScore) -> None:
        """
        Save new baseline to disk.

        Args:
            score: Quality score to save as baseline
        """
        self.baseline_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.baseline_file, "w", encoding="utf-8") as f:
            json.dump(score.to_dict(), f, indent=2)

        self.baseline = score.to_dict()

        logger.info(f"Saved baseline to {self.baseline_file}")

    def detect_regressions(
        self,
        current_score: CombinedQualityScore,
        threshold: float = 0.05,
    ) -> list[str]:
        """
        Detect quality regressions compared to baseline.

        Args:
            current_score: Current quality score
            threshold: Regression threshold (e.g., 0.05 = 5% decrease)

        Returns:
            List of regression descriptions (empty if no regressions)
        """
        if self.baseline is None:
            logger.warning("No baseline available for regression detection")
            return []

        regressions = []

        # Check combined score
        baseline_combined = self.baseline["combined_score"]
        current_combined = current_score.combined_score

        if current_combined < baseline_combined * (1 - threshold):
            regressions.append(f"Combined score regressed: {baseline_combined:.1f} → {current_combined:.1f}")

        # Check component scores
        baseline_rag = self.baseline["rag_score"]
        current_rag = current_score.rag_score

        if current_rag < baseline_rag * (1 - threshold):
            regressions.append(f"RAG score regressed: {baseline_rag:.1f} → {current_rag:.1f}")

        baseline_guardian = self.baseline["guardian_score"]
        current_guardian = current_score.guardian_score

        if current_guardian < baseline_guardian * (1 - threshold):
            regressions.append(f"Guardian score regressed: {baseline_guardian:.1f} → {current_guardian:.1f}")

        if regressions:
            logger.warning(f"Detected {len(regressions)} quality regressions")
        else:
            logger.info("No quality regressions detected")

        return regressions


# Pytest integration


@pytest.fixture
def quality_baseline():
    """Pytest fixture for quality baseline."""
    return QualityBaseline()


def test_combined_quality_calculation():
    """Test combined quality score calculation."""
    score = CombinedQualityScore(
        rag_metrics=RAGQualityMetrics(
            context_precision=0.92,
            context_recall=0.88,
            faithfulness=0.95,
            answer_relevancy=0.90,
            deprecation_detection_rate=0.85,
            golden_rule_coverage=0.90,
            cache_hit_rate=0.87,
        ),
        guardian_metrics=GuardianOutputQuality(
            golden_rule_compliance_rate=0.95,
            false_positive_rate=0.05,
            false_negative_rate=0.08,
            architectural_consistency_score=8.5,
            deprecation_warning_accuracy=0.92,
            actionability_score=0.88,
            review_clarity_score=8.0,
        ),
    )

    combined = score.calculate()

    # Should be high quality score
    assert combined >= 85.0, f"Expected high quality, got {combined}"

    # Component scores should be reasonable
    assert score.rag_score >= 85.0
    assert score.guardian_score >= 85.0

    logger.info(f"Combined quality score: {combined:.1f}/100")


def test_regression_detection(quality_baseline):
    """Test quality regression detection."""
    # Create baseline
    baseline_score = CombinedQualityScore(
        rag_metrics=RAGQualityMetrics(
            context_precision=0.90,
            context_recall=0.85,
        ),
        guardian_metrics=GuardianOutputQuality(
            golden_rule_compliance_rate=0.92,
        ),
    )
    baseline_score.calculate()
    quality_baseline.save_baseline(baseline_score)

    # Current score with regression
    current_score = CombinedQualityScore(
        rag_metrics=RAGQualityMetrics(
            context_precision=0.80,  # 10% regression
            context_recall=0.75,  # 10% regression
        ),
        guardian_metrics=GuardianOutputQuality(
            golden_rule_compliance_rate=0.92,
        ),
    )
    current_score.calculate()

    # Detect regressions
    regressions = quality_baseline.detect_regressions(current_score, threshold=0.05)

    # Should detect regression
    assert len(regressions) > 0, "Should detect quality regression"

    logger.info(f"Detected regressions: {regressions}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
