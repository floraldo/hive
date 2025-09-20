"""
Core review logic for analyzing code quality, tests, and documentation
"""

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
from anthropic import Anthropic
from pydantic import BaseModel, Field


class ReviewDecision(Enum):
    """Possible review decisions"""
    APPROVE = "approve"
    REJECT = "reject"
    REWORK = "rework"
    ESCALATE = "escalate"


class QualityMetrics(BaseModel):
    """Quality metrics for code review"""
    code_quality: float = Field(ge=0, le=100, description="Code quality score")
    test_coverage: float = Field(ge=0, le=100, description="Test coverage score")
    documentation: float = Field(ge=0, le=100, description="Documentation quality score")
    security: float = Field(ge=0, le=100, description="Security assessment score")
    architecture: float = Field(ge=0, le=100, description="Architecture quality score")

    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score"""
        weights = {
            "code_quality": 0.3,
            "test_coverage": 0.25,
            "documentation": 0.15,
            "security": 0.2,
            "architecture": 0.1
        }

        total = sum(
            getattr(self, metric) * weight
            for metric, weight in weights.items()
        )
        return round(total, 2)


@dataclass
class ReviewResult:
    """Result of an AI review"""
    task_id: str
    decision: ReviewDecision
    metrics: QualityMetrics
    summary: str
    issues: List[str]
    suggestions: List[str]
    confidence: float
    escalation_reason: Optional[str] = None
    confusion_points: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        result = {
            "task_id": self.task_id,
            "decision": self.decision.value,
            "metrics": self.metrics.model_dump(),
            "overall_score": self.metrics.overall_score,
            "summary": self.summary,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "confidence": self.confidence
        }

        if self.escalation_reason:
            result["escalation_reason"] = self.escalation_reason

        if self.confusion_points:
            result["confusion_points"] = self.confusion_points

        return result


class ReviewEngine:
    """
    AI-powered code review engine using Claude API
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize review engine"""
        self.client = Anthropic(api_key=api_key) if api_key else None

    def review_task(
        self,
        task_id: str,
        task_description: str,
        code_files: Dict[str, str],
        test_results: Optional[Dict[str, Any]] = None,
        transcript: Optional[str] = None
    ) -> ReviewResult:
        """
        Perform AI review of a task

        Args:
            task_id: Unique task identifier
            task_description: What the task was supposed to accomplish
            code_files: Dictionary of filename -> content
            test_results: Test execution results if available
            transcript: Claude conversation transcript if available

        Returns:
            ReviewResult with decision and metrics
        """
        # Analyze code quality
        metrics = self._analyze_code_quality(code_files, test_results)

        # Detect issues
        issues = self._detect_issues(code_files, test_results)

        # Generate suggestions
        suggestions = self._generate_suggestions(code_files, issues, metrics)

        # Make decision based on metrics
        decision = self._make_decision(metrics, issues)

        # Generate escalation reasoning if needed
        escalation_reason = None
        confusion_points = None

        if decision == ReviewDecision.ESCALATE:
            escalation_reason, confusion_points = self._generate_escalation_reasoning(
                metrics, issues, suggestions
            )

        # Generate summary
        summary = self._generate_summary(
            task_description,
            metrics,
            decision,
            len(issues)
        )

        # Calculate confidence
        confidence = self._calculate_confidence(metrics, test_results)

        return ReviewResult(
            task_id=task_id,
            decision=decision,
            metrics=metrics,
            summary=summary,
            issues=issues,
            suggestions=suggestions,
            confidence=confidence,
            escalation_reason=escalation_reason,
            confusion_points=confusion_points
        )

    def _analyze_code_quality(
        self,
        code_files: Dict[str, str],
        test_results: Optional[Dict[str, Any]] = None
    ) -> QualityMetrics:
        """Analyze code quality across multiple dimensions"""

        # Code quality checks
        code_score = self._score_code_quality(code_files)

        # Test coverage analysis
        test_score = self._score_test_coverage(code_files, test_results)

        # Documentation quality
        doc_score = self._score_documentation(code_files)

        # Security assessment
        security_score = self._score_security(code_files)

        # Architecture quality
        arch_score = self._score_architecture(code_files)

        return QualityMetrics(
            code_quality=code_score,
            test_coverage=test_score,
            documentation=doc_score,
            security=security_score,
            architecture=arch_score
        )

    def _score_code_quality(self, code_files: Dict[str, str]) -> float:
        """Score code quality based on various heuristics"""
        score = 100.0

        for filename, content in code_files.items():
            # Check for code smells
            lines = content.split('\n')

            # Long functions (>50 lines)
            function_lengths = self._get_function_lengths(content)
            if any(length > 50 for length in function_lengths):
                score -= 10

            # Deep nesting (>3 levels)
            max_nesting = self._get_max_nesting(content)
            if max_nesting > 3:
                score -= 5

            # TODO comments
            todo_count = len(re.findall(r'#\s*TODO', content, re.IGNORECASE))
            score -= todo_count * 2

            # Magic numbers
            magic_numbers = len(re.findall(r'\b\d{2,}\b', content))
            if magic_numbers > 5:
                score -= 5

            # Duplicate code (simplified check)
            if self._has_duplicate_code(content):
                score -= 10

        return max(0, min(100, score))

    def _score_test_coverage(
        self,
        code_files: Dict[str, str],
        test_results: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score test coverage"""
        # Look for test files
        test_files = [f for f in code_files.keys() if 'test' in f.lower()]

        if not test_files:
            return 0.0

        # Basic scoring based on test presence
        score = 50.0

        # Check test results if available
        if test_results:
            if test_results.get("passed", False):
                score += 30
            if test_results.get("coverage", 0) > 80:
                score += 20

        # Check for test patterns
        for test_file in test_files:
            content = code_files[test_file]
            test_count = len(re.findall(r'def test_', content))
            if test_count > 5:
                score += 10
                break

        return min(100, score)

    def _score_documentation(self, code_files: Dict[str, str]) -> float:
        """Score documentation quality"""
        score = 0.0
        total_functions = 0
        documented_functions = 0

        for content in code_files.values():
            # Count functions with docstrings
            functions = re.findall(r'def \w+\([^)]*\):', content)
            total_functions += len(functions)

            # Simple docstring detection
            docstrings = re.findall(r'def \w+\([^)]*\):\s*"""[^"]+"""', content)
            documented_functions += len(docstrings)

        if total_functions > 0:
            score = (documented_functions / total_functions) * 100

        return score

    def _score_security(self, code_files: Dict[str, str]) -> float:
        """Basic security assessment"""
        score = 100.0

        security_issues = [
            (r'eval\(', 10),  # eval usage
            (r'exec\(', 10),  # exec usage
            (r'pickle\.', 5),  # pickle usage
            (r'os\.system\(', 8),  # os.system
            (r'subprocess\.call\(.*shell=True', 8),  # shell injection
            (r'password\s*=\s*["\'][^"\']+["\']', 15),  # hardcoded passwords
        ]

        for content in code_files.values():
            for pattern, penalty in security_issues:
                if re.search(pattern, content):
                    score -= penalty

        return max(0, score)

    def _score_architecture(self, code_files: Dict[str, str]) -> float:
        """Score architectural quality"""
        score = 80.0  # Start with good baseline

        # Check for proper separation of concerns
        if len(code_files) == 1:
            score -= 20  # Everything in one file

        # Check for proper module structure
        has_init = any('__init__.py' in f for f in code_files.keys())
        if has_init:
            score += 10

        # Check for configuration management
        has_config = any('config' in f.lower() for f in code_files.keys())
        if has_config:
            score += 10

        return min(100, score)

    def _detect_issues(
        self,
        code_files: Dict[str, str],
        test_results: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Detect specific issues in the code"""
        issues = []

        for filename, content in code_files.items():
            # Check for common issues
            if 'TODO' in content:
                issues.append(f"Unfinished TODO comments in {filename}")

            if re.search(r'except\s*:', content):
                issues.append(f"Bare except clause in {filename}")

            if re.search(r'print\(', content):
                issues.append(f"Print statements found in {filename} (use logging)")

            # Long lines
            long_lines = [i for i, line in enumerate(content.split('\n'), 1)
                         if len(line) > 120]
            if long_lines:
                issues.append(f"Lines exceeding 120 characters in {filename}")

        # Test failures
        if test_results and not test_results.get("passed", True):
            issues.append("Test failures detected")

        return issues

    def _generate_suggestions(
        self,
        code_files: Dict[str, str],
        issues: List[str],
        metrics: QualityMetrics
    ) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []

        # Based on metrics
        if metrics.test_coverage < 60:
            suggestions.append("Add more test coverage, aim for at least 80%")

        if metrics.documentation < 50:
            suggestions.append("Add docstrings to all public functions and classes")

        if metrics.security < 80:
            suggestions.append("Review security practices, avoid eval/exec and hardcoded secrets")

        if metrics.code_quality < 70:
            suggestions.append("Refactor long functions and reduce code complexity")

        # Based on specific issues
        if any("TODO" in issue for issue in issues):
            suggestions.append("Complete or remove TODO items before submission")

        if any("print" in issue for issue in issues):
            suggestions.append("Replace print statements with proper logging")

        return suggestions

    def _make_decision(
        self,
        metrics: QualityMetrics,
        issues: List[str]
    ) -> ReviewDecision:
        """Make review decision based on metrics and issues"""
        overall_score = metrics.overall_score
        critical_issues = [i for i in issues if "security" in i.lower() or "fail" in i.lower()]

        # Enhanced decision logic with escalation reasoning
        if critical_issues:
            # Critical issues but borderline score - escalate for human judgment
            if overall_score >= 50:
                return ReviewDecision.ESCALATE
            else:
                return ReviewDecision.REJECT
        elif overall_score >= 80:
            return ReviewDecision.APPROVE
        elif overall_score >= 60:
            # Check for complex scenarios that need human review
            if self._has_complex_scenario(metrics, issues):
                return ReviewDecision.ESCALATE
            return ReviewDecision.REWORK
        elif overall_score >= 40:
            # Borderline case - AI uncertain, needs human review
            return ReviewDecision.ESCALATE
        else:
            return ReviewDecision.REJECT

    def _has_complex_scenario(self, metrics: QualityMetrics, issues: List[str]) -> bool:
        """Detect complex scenarios requiring human judgment"""
        # High variance in metrics suggests complexity
        scores = [metrics.code_quality, metrics.test_coverage,
                 metrics.documentation, metrics.security, metrics.architecture]
        variance = max(scores) - min(scores)

        # Complex if high variance or many issues
        return variance > 50 or len(issues) > 5

    def _generate_summary(
        self,
        task_description: str,
        metrics: QualityMetrics,
        decision: ReviewDecision,
        issue_count: int
    ) -> str:
        """Generate review summary"""
        summary = f"Task review completed with overall score: {metrics.overall_score}/100. "

        if decision == ReviewDecision.APPROVE:
            summary += "Code meets quality standards and is approved for integration."
        elif decision == ReviewDecision.REWORK:
            summary += f"Code needs improvements. Found {issue_count} issues to address."
        elif decision == ReviewDecision.REJECT:
            summary += "Code has critical issues and requires significant rework."
        else:
            summary += "Code requires human review for final decision."

        return summary

    def _generate_escalation_reasoning(
        self,
        metrics: QualityMetrics,
        issues: List[str],
        suggestions: List[str]
    ) -> tuple[str, List[str]]:
        """Generate detailed reasoning for escalation"""
        confusion_points = []
        reasons = []

        # Analyze metric variance
        scores = [metrics.code_quality, metrics.test_coverage,
                 metrics.documentation, metrics.security, metrics.architecture]
        variance = max(scores) - min(scores)

        if variance > 50:
            confusion_points.append(f"High variance in quality metrics ({variance:.0f} point spread)")
            reasons.append("Inconsistent quality across different aspects")

        # Check for critical issues with decent overall score
        if metrics.overall_score >= 50 and any("security" in i.lower() for i in issues):
            confusion_points.append("Security concerns despite reasonable overall score")
            reasons.append("Security issues require human risk assessment")

        # Many issues but not clearly bad
        if len(issues) > 5 and metrics.overall_score >= 40:
            confusion_points.append(f"{len(issues)} issues found but score is borderline")
            reasons.append("Too many issues to automatically determine severity")

        # Conflicting signals
        if metrics.test_coverage > 80 and metrics.code_quality < 50:
            confusion_points.append("Good test coverage but poor code quality")
            reasons.append("Conflicting quality signals need human interpretation")

        # Low confidence scenario
        if metrics.overall_score >= 40 and metrics.overall_score < 60:
            confusion_points.append("Score in uncertain range (40-60)")
            reasons.append("Borderline quality requires human judgment")

        # Default reason if none specific
        if not reasons:
            reasons.append("Complex decision requiring human expertise")
            confusion_points.append("AI unable to make confident decision")

        # Create main reason string
        main_reason = reasons[0] if reasons else "Requires human review"

        # Add suggested actions for human reviewer
        if confusion_points:
            confusion_points.append(f"Suggested focus: {', '.join(suggestions[:2])}" if suggestions else "Review overall quality")

        return main_reason, confusion_points

    def _calculate_confidence(
        self,
        metrics: QualityMetrics,
        test_results: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calculate confidence in the review decision"""
        confidence = 0.7  # Base confidence

        # Adjust based on test results
        if test_results:
            confidence += 0.1
            if test_results.get("passed", False):
                confidence += 0.1

        # Adjust based on metric clarity
        if metrics.overall_score > 85 or metrics.overall_score < 40:
            confidence += 0.1  # Clear decision

        return min(1.0, confidence)

    def _get_function_lengths(self, content: str) -> List[int]:
        """Get lengths of functions in code"""
        lengths = []
        lines = content.split('\n')
        in_function = False
        current_length = 0

        for line in lines:
            if re.match(r'^def \w+\(', line.strip()):
                if in_function:
                    lengths.append(current_length)
                in_function = True
                current_length = 0
            elif in_function and line.strip() and not line.startswith(' '):
                lengths.append(current_length)
                in_function = False
            elif in_function:
                current_length += 1

        if in_function:
            lengths.append(current_length)

        return lengths

    def _get_max_nesting(self, content: str) -> int:
        """Get maximum nesting level in code"""
        max_level = 0
        current_level = 0

        for line in content.split('\n'):
            # Count leading spaces (assuming 4 spaces per level)
            spaces = len(line) - len(line.lstrip())
            level = spaces // 4
            max_level = max(max_level, level)

        return max_level

    def _has_duplicate_code(self, content: str) -> bool:
        """Simplified duplicate code detection"""
        lines = content.split('\n')
        # Look for duplicate blocks (>5 consecutive lines)
        for i in range(len(lines) - 10):
            block = lines[i:i+5]
            remaining = '\n'.join(lines[i+5:])
            if '\n'.join(block) in remaining:
                return True
        return False