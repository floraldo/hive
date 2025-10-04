"""Golden Rules analyzer integrating with hive-tests framework."""

import time
from pathlib import Path

from guardian_agent.core.interfaces import AnalysisResult, Severity, Suggestion, Violation, ViolationType
from hive_logging import get_logger
from hive_tests.ast_validator import EnhancedValidator as ASTValidator
from hive_tests.autofix import GoldenRulesAutoFixer

logger = get_logger(__name__)


class GoldenRulesAnalyzer:
    """
    Analyzes code against the Hive platform's Golden Rules.

    Integrates with the existing AST-based validator and autofix capabilities.
    """

    def __init__(self) -> None:
        """Initialize the Golden Rules analyzer."""
        self.validator = ASTValidator(project_root=Path("."))
        self.autofixer = GoldenRulesAutoFixer(project_root=Path("."), dry_run=True)

        # Map Golden Rules to severity levels
        self.severity_map = {
            "rule-5": Severity.ERROR,  # Package vs App Discipline,
            "rule-6": Severity.ERROR,  # Dependency Direction,
            "rule-7": Severity.WARNING,  # Interface Contracts,
            "rule-8": Severity.ERROR,  # Error Handling,
            "rule-9": Severity.WARNING,  # Logging Standards,
            "rule-10": Severity.ERROR,  # Service Layer Discipline
            "rule-11": Severity.WARNING,  # Communication Patterns
            "rule-12": Severity.WARNING,  # Package Naming
            "rule-13": Severity.INFO,  # Dev Tools Consistency
            "rule-14": Severity.WARNING,  # Async Pattern Consistency
            "rule-15": Severity.INFO,  # CLI Pattern Consistency
            "rule-16": Severity.ERROR,  # No Global State Access
            "rule-17": Severity.WARNING,  # Test-to-Source Mapping
            "rule-18": Severity.WARNING,  # Test File Quality
        }

    async def analyze(self, file_path: Path, content: str) -> AnalysisResult:
        """
        Analyze file against Golden Rules.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            AnalysisResult with Golden Rules violations
        """
        start_time = time.time(),
        violations = [],
        suggestions = []

        try:
            # Run AST validator
            validation_results = self.validator.validate_file(file_path)

            # Convert validator violations to our format
            for val_violation in validation_results:
                severity = self.severity_map.get(val_violation.rule_id, Severity.WARNING)

                violation = Violation(
                    type=ViolationType.GOLDEN_RULE,
                    severity=severity,
                    rule=val_violation.rule_id,
                    message=val_violation.message,
                    file_path=file_path,
                    line_number=val_violation.line_number,
                    metadata={"rule_name": val_violation.rule_name},
                )

                # Check if autofix is available
                if self._can_autofix(val_violation.rule_id):
                    violation.fix_suggestion = (
                        f"Can be automatically fixed using autofix.py for {val_violation.rule_id}"
                    )

                violations.append(violation)

            # Generate improvement suggestions
            suggestions.extend(self._generate_suggestions(file_path, violations))

        except Exception as e:
            logger.error("Golden Rules analysis failed for %s: %s", file_path, e)
            return AnalysisResult(analyzer_name=self.__class__.__name__, error=str(e))

        execution_time = (time.time() - start_time) * 1000

        return AnalysisResult(
            analyzer_name=self.__class__.__name__,
            violations=violations,
            suggestions=suggestions,
            metrics={
                "golden_rules_checked": len(self.severity_map),
                "violations_found": len(violations),
                "auto_fixable": sum(1 for v in violations if v.fix_suggestion),
            },
            execution_time_ms=execution_time,
        )

    def _can_autofix(self, rule_id: str) -> bool:
        """Check if a rule violation can be automatically fixed."""
        # Rules that autofix.py can handle
        auto_fixable_rules = {"rule-14", "rule-9", "rule-8"}
        return rule_id in auto_fixable_rules

    def _generate_suggestions(self, file_path: Path, violations: list[Violation]) -> list[Suggestion]:
        """Generate improvement suggestions based on violations."""
        suggestions = []

        # Suggest running autofix if applicable
        auto_fixable = [v for v in violations if v.fix_suggestion]
        if auto_fixable:
            rules = {v.rule for v in auto_fixable}
            suggestions.append(
                Suggestion(
                    category="automation",
                    message="Run autofix.py to automatically fix mechanical violations",
                    file_path=file_path,
                    line_range=(1, 1),
                    confidence=1.0,
                    example=f"python -m hive_tests.autofix --execute --rules {' '.join(rules)}",
                    rationale="These violations can be fixed automatically without manual intervention",
                ),
            )

        # Suggest architectural improvements for service layer violations
        service_violations = [v for v in violations if v.rule == "rule-10"]
        if service_violations:
            suggestions.append(
                Suggestion(
                    category="architecture",
                    message="Extract business logic from service layer to domain modules",
                    file_path=file_path,
                    line_range=(1, 100),
                    confidence=0.9,
                    rationale="Service layers should be thin orchestrators, not contain business logic",
                ),
            )

        # Suggest dependency injection for global state violations
        global_state_violations = [v for v in violations if v.rule == "rule-16"]
        if global_state_violations:
            suggestions.append(
                Suggestion(
                    category="architecture",
                    message="Replace global state access with dependency injection",
                    file_path=file_path,
                    line_range=(1, 50),
                    confidence=0.95,
                    example="def __init__(self, config: Config) -> None:",
                    rationale="Global state makes testing difficult and creates hidden dependencies",
                ),
            )

        # Suggest test creation for missing tests
        test_violations = [v for v in violations if v.rule in ["rule-17", "rule-18"]]
        if test_violations:
            test_file = file_path.parent.parent / "tests" / f"test_{file_path.stem}.py"
            suggestions.append(
                Suggestion(
                    category="testing",
                    message=f"Create or enhance test file: {test_file.name}",
                    file_path=file_path,
                    line_range=(1, 1),
                    confidence=0.85,
                    rationale="Every source file should have corresponding tests with good coverage",
                ),
            )

        return suggestions

    async def get_autofix_preview(self, file_path: Path) -> str | None:
        """
        Get a preview of what autofix would change.

        Args:
            file_path: Path to the file

        Returns:
            Preview of changes or None if no fixes available
        """
        try:
            # Run autofix in dry-run mode
            results = self.autofixer.fix_all_violations()

            # Filter results for this file
            file_results = [r for r in results if r.file_path == file_path]

            if not file_results:
                return None

            # Generate preview
            preview_lines = [f"Autofix preview for {file_path.name}:", ""]

            for result in file_results:
                if result.success and result.changes_made:
                    preview_lines.append(f"Rule {result.rule_id} ({result.rule_name}):")
                    for change in result.changes_made:
                        preview_lines.append(f"  - {change}")
                    preview_lines.append("")

            return "\n".join(preview_lines)

        except Exception as e:
            logger.error("Failed to generate autofix preview: %s", e)
            return None
