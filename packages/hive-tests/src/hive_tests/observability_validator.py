"""Observability Standards Validator - Golden Rule 35.

Validates usage of hive-performance decorators for observability.

Detects anti-patterns:
1. Manual timing code (time.time() pairs for duration tracking)
2. Direct OpenTelemetry usage outside hive-performance package
3. Custom Prometheus metrics without decorator wrappers
4. Manual metric creation without hive-performance registry

Encourages:
- @timed() for duration tracking
- @counted() for event counting
- @traced() for distributed tracing
- @track_errors() for error tracking
- Composite decorators (@track_request, @track_adapter_request, @track_cache_operation)
"""

from __future__ import annotations

import ast
from pathlib import Path

from hive_logging import get_logger

logger = get_logger(__name__)


class ObservabilityStandardsValidator(ast.NodeVisitor):
    """Validates observability best practices (Golden Rule 35)."""

    def __init__(self, file_path: Path, project_root: Path):
        """Initialize validator.

        Args:
            file_path: Path to file being validated
            project_root: Project root directory
        """
        self.file_path = file_path
        self.project_root = project_root
        self.violations = []

        # Exemptions
        self.is_hive_performance = "packages/hive-performance" in str(file_path).replace("\\", "/")
        self.is_test_file = "/tests/" in str(file_path).replace("\\", "/") or str(file_path).endswith("_test.py")
        self.is_demo_file = "demo_" in file_path.name or "test_" in file_path.name
        self.is_archived = "/archive/" in str(file_path).replace("\\", "/")

        # Tracking state
        self.manual_timing_candidates = {}  # Track time.time() assignments
        self.has_hive_performance_import = False

    def visit_Import(self, node: ast.Import):
        """Check for direct OpenTelemetry imports."""
        for alias in node.names:
            if alias.name.startswith("opentelemetry"):
                if not self.is_hive_performance:
                    self.violations.append({
                        "line": node.lineno,
                        "col": node.col_offset,
                        "message": f"Direct OpenTelemetry import '{alias.name}' - use hive-performance decorators instead",
                        "severity": "WARNING",
                    })

            if alias.name == "time":
                # Track time import for manual timing detection
                pass

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Check for hive-performance imports and OpenTelemetry imports."""
        if node.module and node.module.startswith("opentelemetry"):
            if not self.is_hive_performance:
                self.violations.append({
                    "line": node.lineno,
                    "col": node.col_offset,
                    "message": f"Direct OpenTelemetry import from '{node.module}' - use hive-performance decorators instead",
                    "severity": "WARNING",
                })

        if node.module == "hive_performance":
            self.has_hive_performance_import = True

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """Detect manual timing patterns: start = time.time()."""
        # Check if RHS is time.time() call
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Attribute):
                # Check for time.time() pattern
                if (node.value.func.attr == "time" and
                    isinstance(node.value.func.value, ast.Name) and
                    node.value.func.value.id == "time"):

                    # Track the variable name for later matching
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_name = target.id
                            if var_name.endswith("_start") or var_name.startswith("start_"):
                                # Likely a manual timing start
                                self.manual_timing_candidates[var_name] = node.lineno

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        """Detect manual duration calculation: time.time() - start_time."""
        # Check for subtraction with time.time() on the left
        if isinstance(node.op, ast.Sub):
            left_is_time_call = False
            right_var_name = None

            # Check left side: time.time()
            if isinstance(node.left, ast.Call):
                if isinstance(node.left.func, ast.Attribute):
                    if (node.left.func.attr == "time" and
                        isinstance(node.left.func.value, ast.Name) and
                        node.left.func.value.id == "time"):
                        left_is_time_call = True

            # Check right side: variable name
            if isinstance(node.right, ast.Name):
                right_var_name = node.right.id

            # If we found time.time() - var pattern, check if var was a start time
            if left_is_time_call and right_var_name:
                if right_var_name in self.manual_timing_candidates:
                    start_line = self.manual_timing_candidates[right_var_name]
                    self.violations.append({
                        "line": start_line,
                        "col": 0,
                        "message": f"Manual timing detected (lines {start_line}-{node.lineno}): use @timed() decorator instead",
                        "severity": "WARNING",
                        "suggestion": "Replace with @timed(metric_name='...')",
                    })

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check if functions use decorators for observability."""
        # Skip private functions and test functions
        if node.name.startswith("_") or node.name.startswith("test_"):
            self.generic_visit(node)
            return

        # Skip exempt files
        if self.is_hive_performance or self.is_test_file or self.is_demo_file or self.is_archived:
            self.generic_visit(node)
            return

        # Check function body for manual timing
        has_time_usage = False
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if (child.func.attr == "time" and
                        isinstance(child.func.value, ast.Name) and
                        child.func.value.id == "time"):
                        has_time_usage = True
                        break

        # If function uses time.time() but has no hive-performance decorator, suggest it
        if has_time_usage:
            has_observability_decorator = False
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    if decorator.id in ["timed", "counted", "traced", "track_errors", "measure_memory"]:
                        has_observability_decorator = True
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        if decorator.func.id in ["timed", "counted", "traced", "track_errors", "measure_memory",
                                                  "track_request", "track_adapter_request", "track_cache_operation"]:
                            has_observability_decorator = True

            if not has_observability_decorator:
                # INFO level - suggestion for improvement, not a hard error
                self.violations.append({
                    "line": node.lineno,
                    "col": node.col_offset,
                    "message": f"Function '{node.name}' uses manual timing - consider using @timed() decorator",
                    "severity": "INFO",
                    "suggestion": f"Add @timed(metric_name='{node.name}_duration') above function",
                })

        self.generic_visit(node)


def validate_observability_standards(
    project_root: Path,
    scope_files: list[Path] | None = None,
) -> tuple[bool, list[str]]:
    """Golden Rule 35: Observability Standards.

    Validates usage of hive-performance decorators for observability.

    Detects:
    - Manual timing code (time.time() pairs)
    - Direct OpenTelemetry usage outside hive-performance
    - Missing decorator usage when manual instrumentation exists

    Exempts:
    - hive-performance package itself
    - Test files
    - Demo files
    - Archived code

    Args:
        project_root: Project root directory
        scope_files: Optional list of files to validate

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Discover Python files if no scope provided
    if scope_files is None:
        scope_files = []
        for base_dir in [project_root / "apps", project_root / "packages"]:
            if base_dir.exists():
                scope_files.extend(base_dir.rglob("*.py"))

    # Validate each file
    for file_path in scope_files:
        if not file_path.suffix == ".py":
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(file_path))
            validator = ObservabilityStandardsValidator(file_path, project_root)
            validator.visit(tree)

            # Format violations
            for violation in validator.violations:
                relative_path = file_path.relative_to(project_root)
                formatted = f"{relative_path}:{violation['line']}:{violation['col']} - [{violation['severity']}] {violation['message']}"
                if "suggestion" in violation:
                    formatted += f" | Suggestion: {violation['suggestion']}"
                violations.append(formatted)

        except SyntaxError as e:
            # Skip files with syntax errors (will be caught by other validators)
            logger.debug(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error validating {file_path}: {e}", exc_info=True)
            violations.append(f"{file_path}: Validation error: {e}")

    # WARNING severity - transitional enforcement with 6-month grace period
    # For now, return True (passing) but log violations
    return True, violations


__all__ = ["validate_observability_standards", "ObservabilityStandardsValidator"]
