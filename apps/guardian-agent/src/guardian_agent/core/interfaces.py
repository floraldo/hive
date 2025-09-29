"""Core interfaces for the Guardian Agent."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Severity(Enum):
    """Severity levels for violations and suggestions."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ViolationType(Enum):
    """Types of violations detected."""

    GOLDEN_RULE = "golden_rule"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    BUG = "bug"
    CODE_SMELL = "code_smell"
    BEST_PRACTICE = "best_practice"


@dataclass
class Violation:
    """Represents a code violation detected during review."""

    type: ViolationType
    severity: Severity
    rule: str
    message: str
    file_path: Path
    line_number: int
    column: Optional[int] = None
    snippet: Optional[str] = None
    fix_suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Suggestion:
    """Represents an improvement suggestion."""

    category: str
    message: str
    file_path: Path
    line_range: tuple[int, int]
    confidence: float
    example: Optional[str] = None
    rationale: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Result from a specific analyzer."""

    analyzer_name: str
    violations: List[Violation] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class ReviewResult:
    """Complete result from a code review."""

    file_path: Path
    analysis_results: List[AnalysisResult]
    overall_score: float
    summary: str
    violations_count: Dict[Severity, int]
    suggestions_count: int
    auto_fixable_count: int
    ai_confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def all_violations(self) -> List[Violation]:
        """Get all violations from all analyzers."""
        violations = []
        for result in self.analysis_results:
            violations.extend(result.violations)
        return violations

    @property
    def all_suggestions(self) -> List[Suggestion]:
        """Get all suggestions from all analyzers."""
        suggestions = []
        for result in self.analysis_results:
            suggestions.extend(result.suggestions)
        return suggestions

    @property
    def has_blocking_issues(self) -> bool:
        """Check if review has blocking issues."""
        return self.violations_count.get(Severity.CRITICAL, 0) > 0 or self.violations_count.get(Severity.ERROR, 0) > 0

    def to_markdown(self) -> str:
        """Convert review result to markdown format."""
        lines = [
            f"# Code Review: {self.file_path.name}",
            "",
            f"**Overall Score**: {self.overall_score:.1f}/100",
            f"**AI Confidence**: {self.ai_confidence:.0%}",
            "",
            "## Summary",
            self.summary,
            "",
        ]

        if self.all_violations:
            lines.extend(
                [
                    "## Violations",
                    "",
                    f"Found {sum(self.violations_count.values())} violations:",
                    "",
                ]
            )

            for severity in Severity:
                count = self.violations_count.get(severity, 0)
                if count > 0:
                    lines.append(f"- {severity.value.upper()}: {count}")

            lines.append("")

            for violation in sorted(self.all_violations, key=lambda v: (v.severity.value, v.line_number)):
                icon = {"critical": "🔴", "error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(violation.severity.value, "")

                lines.extend(
                    [
                        f"### {icon} {violation.severity.value.upper()}: {violation.message}",
                        f"- **Type**: {violation.type.value}",
                        f"- **Location**: Line {violation.line_number}",
                    ]
                )

                if violation.snippet:
                    lines.extend(["", "```python", violation.snippet, "```"])

                if violation.fix_suggestion:
                    lines.extend(["", "**Suggested Fix**:", "", violation.fix_suggestion])

                lines.append("")

        if self.all_suggestions:
            lines.extend(
                [
                    "## Suggestions",
                    "",
                    f"Found {len(self.all_suggestions)} improvement suggestions:",
                    "",
                ]
            )

            for suggestion in sorted(self.all_suggestions, key=lambda s: -s.confidence):
                lines.extend(
                    [
                        f"### 💡 {suggestion.message}",
                        f"- **Category**: {suggestion.category}",
                        f"- **Lines**: {suggestion.line_range[0]}-{suggestion.line_range[1]}",
                        f"- **Confidence**: {suggestion.confidence:.0%}",
                    ]
                )

                if suggestion.rationale:
                    lines.extend(["", f"**Why**: {suggestion.rationale}"])

                if suggestion.example:
                    lines.extend(["", "**Example**:", "", "```python", suggestion.example, "```"])

                lines.append("")

        return "\n".join(lines)
