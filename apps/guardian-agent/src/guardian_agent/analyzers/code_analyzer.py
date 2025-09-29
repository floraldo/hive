"""AST-based code analyzer for deep code understanding."""

import ast
import time
from pathlib import Path
from typing import Any, Dict, List

from hive_logging import get_logger

from guardian_agent.core.interfaces import (
    AnalysisResult,
    Severity,
    Suggestion,
    Violation,
    ViolationType,
)

logger = get_logger(__name__)


class CodeAnalyzer:
    """
    Analyzes code using Python's AST for deep understanding.

    Detects code smells, complexity issues, and structural problems.
    """

    def __init__(self) -> None:
        """Initialize the code analyzer."""
        self.max_complexity = 10
        self.max_function_length = 50
        self.max_parameters = 5
        self.max_nesting_depth = 4

    async def analyze(self, file_path: Path, content: str) -> AnalysisResult:
        """
        Analyze code content using AST.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            AnalysisResult with findings
        """
        start_time = time.time()
        violations = []
        suggestions = []
        metrics = {}

        try:
            # Parse AST
            tree = ast.parse(content, filename=str(file_path))

            # Run various analyses
            violations.extend(self._check_complexity(tree, file_path))
            violations.extend(self._check_function_length(tree, file_path, content))
            violations.extend(self._check_naming_conventions(tree, file_path))
            violations.extend(self._check_imports(tree, file_path))

            suggestions.extend(self._suggest_refactoring(tree, file_path))
            suggestions.extend(self._suggest_type_hints(tree, file_path))

            # Collect metrics
            metrics = self._collect_metrics(tree, content)

        except SyntaxError as e:
            logger.error("Syntax error in %s: %s", file_path, e)
            violations.append(
                Violation(
                    type=ViolationType.BUG,
                    severity=Severity.ERROR,
                    rule="syntax-error",
                    message=f"Syntax error: {e.msg}",
                    file_path=file_path,
                    line_number=e.lineno or 0,
                    column=e.offset,
                )
            )
        except Exception as e:
            logger.error("Failed to analyze %s: %s", file_path, e)
            return AnalysisResult(
                analyzer_name=self.__class__.__name__,
                error=str(e),
            )

        execution_time = (time.time() - start_time) * 1000

        return AnalysisResult(
            analyzer_name=self.__class__.__name__,
            violations=violations,
            suggestions=suggestions,
            metrics=metrics,
            execution_time_ms=execution_time,
        )

    def _check_complexity(self, tree: ast.AST, file_path: Path) -> List[Violation]:
        """Check cyclomatic complexity of functions."""
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = self._calculate_complexity(node)

                if complexity > self.max_complexity:
                    violations.append(
                        Violation(
                            type=ViolationType.CODE_SMELL,
                            severity=Severity.WARNING,
                            rule="high-complexity",
                            message=f"Function '{node.name}' has high cyclomatic complexity ({complexity})",
                            file_path=file_path,
                            line_number=node.lineno,
                            fix_suggestion=f"Consider breaking '{node.name}' into smaller functions",
                        )
                    )

        return violations

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Each decision point adds to complexity
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # and/or operators add complexity
                complexity += len(child.values) - 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1

        return complexity

    def _check_function_length(self, tree: ast.AST, file_path: Path, content: str) -> List[Violation]:
        """Check function length."""
        violations = []
        lines = content.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if hasattr(node, "end_lineno"):
                    length = node.end_lineno - node.lineno + 1
                else:
                    # Fallback for older Python versions
                    length = self._estimate_function_length(node, lines)

                if length > self.max_function_length:
                    violations.append(
                        Violation(
                            type=ViolationType.CODE_SMELL,
                            severity=Severity.WARNING,
                            rule="long-function",
                            message=f"Function '{node.name}' is too long ({length} lines)",
                            file_path=file_path,
                            line_number=node.lineno,
                            fix_suggestion=f"Consider splitting '{node.name}' into smaller functions",
                        )
                    )

                # Check parameter count
                if len(node.args.args) > self.max_parameters:
                    violations.append(
                        Violation(
                            type=ViolationType.CODE_SMELL,
                            severity=Severity.WARNING,
                            rule="too-many-parameters",
                            message=f"Function '{node.name}' has too many parameters ({len(node.args.args)})",
                            file_path=file_path,
                            line_number=node.lineno,
                            fix_suggestion="Consider using a configuration object or splitting the function",
                        )
                    )

        return violations

    def _estimate_function_length(self, node: ast.FunctionDef, lines: List[str]) -> int:
        """Estimate function length for older Python versions."""
        start_line = node.lineno - 1
        indent_level = len(lines[start_line]) - len(lines[start_line].lstrip())

        end_line = start_line + 1
        while end_line < len(lines):
            line = lines[end_line]
            if line.strip() and not line[indent_level:].startswith(" "):
                break
            end_line += 1

        return end_line - start_line

    def _check_naming_conventions(self, tree: ast.AST, file_path: Path) -> List[Violation]:
        """Check Python naming conventions."""
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Classes should be PascalCase
                if not node.name[0].isupper() or "_" in node.name:
                    violations.append(
                        Violation(
                            type=ViolationType.STYLE,
                            severity=Severity.INFO,
                            rule="naming-convention",
                            message=f"Class '{node.name}' should use PascalCase",
                            file_path=file_path,
                            line_number=node.lineno,
                            fix_suggestion=self._to_pascal_case(node.name),
                        )
                    )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Functions should be snake_case
                if node.name != node.name.lower() and not node.name.startswith("_"):
                    violations.append(
                        Violation(
                            type=ViolationType.STYLE,
                            severity=Severity.INFO,
                            rule="naming-convention",
                            message=f"Function '{node.name}' should use snake_case",
                            file_path=file_path,
                            line_number=node.lineno,
                            fix_suggestion=self._to_snake_case(node.name),
                        )
                    )

        return violations

    def _to_pascal_case(self, name: str) -> str:
        """Convert name to PascalCase."""
        return "".join(word.capitalize() for word in name.split("_"))

    def _to_snake_case(self, name: str) -> str:
        """Convert name to snake_case."""
        import re

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    def _check_imports(self, tree: ast.AST, file_path: Path) -> List[Violation]:
        """Check import organization and usage."""
        violations = []
        imports = []
        used_names = set()

        # Collect imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append(f"{node.module}.{alias.name}" if node.module else alias.name)
            elif isinstance(node, ast.Name):
                used_names.add(node.id)

        # Check for unused imports (simple check)
        for imp in imports:
            imp_name = imp.split(".")[-1]
            if imp_name not in used_names and imp_name not in ["__future__", "annotations"]:
                # Note: This is a simplified check
                pass  # Could add violation for unused imports

        return violations

    def _suggest_refactoring(self, tree: ast.AST, file_path: Path) -> List[Suggestion]:
        """Suggest refactoring opportunities."""
        suggestions = []

        # Check for duplicate code patterns
        function_bodies = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body_str = ast.unparse(node.body) if hasattr(ast, "unparse") else str(node.body)
                if body_str in function_bodies:
                    suggestions.append(
                        Suggestion(
                            category="refactoring",
                            message=f"Functions '{function_bodies[body_str]}' and '{node.name}' have similar implementations",
                            file_path=file_path,
                            line_range=(node.lineno, node.lineno + 10),
                            confidence=0.7,
                            rationale="Duplicate code increases maintenance burden",
                        )
                    )
                else:
                    function_bodies[body_str] = node.name

        return suggestions

    def _suggest_type_hints(self, tree: ast.AST, file_path: Path) -> List[Suggestion]:
        """Suggest adding type hints."""
        suggestions = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check for missing return type
                if node.returns is None and not node.name.startswith("__"):
                    suggestions.append(
                        Suggestion(
                            category="type-hints",
                            message=f"Add return type hint to function '{node.name}'",
                            file_path=file_path,
                            line_range=(node.lineno, node.lineno),
                            confidence=0.9,
                            example=f"def {node.name}(...) -> None:",
                            rationale="Type hints improve code maintainability and IDE support",
                        )
                    )

                # Check for missing parameter types
                for arg in node.args.args:
                    if arg.annotation is None and arg.arg != "self":
                        suggestions.append(
                            Suggestion(
                                category="type-hints",
                                message=f"Add type hint to parameter '{arg.arg}' in function '{node.name}'",
                                file_path=file_path,
                                line_range=(node.lineno, node.lineno),
                                confidence=0.9,
                                example=f"{arg.arg}: str",
                                rationale="Type hints help prevent type-related bugs",
                            )
                        )

        return suggestions

    def _collect_metrics(self, tree: ast.AST, content: str) -> Dict[str, Any]:
        """Collect code metrics."""
        metrics = {
            "lines_of_code": len(content.split("\n")),
            "num_classes": sum(1 for _ in ast.walk(tree) if isinstance(_, ast.ClassDef)),
            "num_functions": sum(1 for _ in ast.walk(tree) if isinstance(_, (ast.FunctionDef, ast.AsyncFunctionDef))),
            "num_async_functions": sum(1 for _ in ast.walk(tree) if isinstance(_, ast.AsyncFunctionDef)),
            "num_imports": sum(1 for _ in ast.walk(tree) if isinstance(_, (ast.Import, ast.ImportFrom))),
            "max_nesting_depth": self._calculate_max_nesting(tree),
        }

        return metrics

    def _calculate_max_nesting(self, tree: ast.AST) -> int:
        """Calculate maximum nesting depth in the code."""

        def get_depth(node: ast.AST, current_depth: int = 0) -> int:
            max_depth = current_depth

            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.With, ast.Try)):
                    child_depth = get_depth(child, current_depth + 1)
                    max_depth = max(max_depth, child_depth)
                else:
                    child_depth = get_depth(child, current_depth)
                    max_depth = max(max_depth, child_depth)

            return max_depth

        return get_depth(tree)
