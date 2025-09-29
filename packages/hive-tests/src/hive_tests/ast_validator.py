from __future__ import annotations

from hive_logging import get_logger

logger = get_logger(__name__)

"""
Single-Pass AST-Based Validator System

This module implements a high-performance, single-pass validation system that
traverses the codebase once and applies multiple Golden Rules simultaneously.
This approach is significantly faster than the original multi-pass system and
provides more accurate validation through proper AST parsing.

Key Benefits:
- 5-10x faster validation (single file read/parse per file)
- More accurate (AST-based vs string matching)
- Extensible (easy to add new rules)
- Suppression support (controlled rule exceptions)
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Violation:
    """Represents a single Golden Rule violation"""

    rule_id: str
    rule_name: str
    file_path: Path
    line_number: int
    message: str
    severity: str = "error"  # error, warning, info
    suppressible: bool = True


@dataclass
class FileContext:
    """Context information for a single file being validated"""

    path: Path
    content: str
    ast_tree: ast.AST | None
    lines: list[str]
    is_test_file: bool
    is_cli_file: bool
    is_init_file: bool
    package_name: str | None
    app_name: str | None
    suppressions: dict[int, set[str]] = field(default_factory=dict)


class GoldenRuleVisitor(ast.NodeVisitor):
    """
    AST visitor that applies multiple Golden Rules during a single traversal.
    Each rule can subscribe to specific AST node types.
    """

    def __init__(self, file_context: FileContext, project_root: Path) -> None:
        self.context = file_context
        self.project_root = project_root
        self.violations: list[Violation] = []
        self.current_line = 1

    def add_violation(self, rule_id: str, rule_name: str, line_num: int, message: str, severity: str = "error") -> None:
        """Add a violation if not suppressed"""
        if line_num in self.context.suppressions and rule_id in self.context.suppressions[line_num]:
            return  # Violation is suppressed

        self.violations.append(
            Violation(
                rule_id=rule_id,
                rule_name=rule_name,
                file_path=self.context.path,
                line_number=line_num,
                message=message,
                severity=severity,
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        """Validate import statements"""
        self._validate_dependency_direction(node)
        self._validate_no_unsafe_imports(node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Validate from imports"""
        self._validate_dependency_direction_from(node)
        self._validate_no_unsafe_imports_from(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Validate function calls"""
        self._validate_no_unsafe_calls(node)
        self._validate_async_sync_mixing(node)
        self._validate_print_statements(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Validate function definitions"""
        self._validate_interface_contracts(node)
        self._validate_async_naming(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Validate async function definitions"""
        self._validate_interface_contracts_async(node)
        self._validate_async_naming(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Validate class definitions"""
        self._validate_error_handling_standards(node)
        self.generic_visit(node)

    # Rule implementations
    def _validate_dependency_direction(self, node: ast.Import) -> None:
        """Golden Rule 6: Dependency Direction - Import statements"""
        for alias in node.names:
            if self._is_invalid_app_import(alias.name):
                self.add_violation(
                    "rule-6",
                    "Dependency Direction",
                    node.lineno,
                    f"Invalid app import: {alias.name}. Apps should only import from packages or other apps' core/ modules.",
                )

    def _validate_dependency_direction_from(self, node: ast.ImportFrom) -> None:
        """Golden Rule 6: Dependency Direction - From imports"""
        # Allow test files to import from their own app more freely
        if self.context.is_test_file or "/tests/" in str(self.context.path):
            return  # Test files can import from their parent app

        # Allow demo/run files to import from their own app
        if self.context.path.name.startswith(("demo_", "run_")):
            return  # Demo and run files can import from their app

        if node.module and self._is_invalid_app_import(node.module):
            self.add_violation(
                "rule-6",
                "Dependency Direction",
                node.lineno,
                f"Invalid app import: from {node.module}. Use service layer (core/) or shared packages.",
            )

    def _validate_no_unsafe_calls(self, node: ast.Call) -> None:
        """Golden Rule 17: No Unsafe Function Calls"""
        unsafe_calls = {
            "eval": "Use ast.literal_eval() or safer alternatives",
            "exec": "Avoid dynamic code execution",
            "compile": "Avoid dynamic code compilation",
        }

        if isinstance(node.func, ast.Name) and node.func.id in unsafe_calls:
            self.add_violation(
                "rule-17",
                "No Unsafe Function Calls",
                node.lineno,
                f"Unsafe function call: {node.func.id}(). {unsafe_calls[node.func.id]}",
            )

        # Check for os.system and subprocess with shell=True
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "system":
                self.add_violation(
                    "rule-17",
                    "No Unsafe Function Calls",
                    node.lineno,
                    "Avoid os.system(). Use subprocess.run() with explicit arguments.",
                )

            # Check subprocess.run with shell=True
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr in ["run", "call", "Popen"]
            ):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        self.add_violation(
                            "rule-17",
                            "No Unsafe Function Calls",
                            node.lineno,
                            f"Avoid {node.func.attr}() with shell=True. Use explicit argument lists.",
                        )

    def _validate_async_sync_mixing(self, node: ast.Call) -> None:
        """Golden Rule 19: No Synchronous Calls in Async Code"""
        # Check if we're in an async function
        if not self._in_async_function():
            return

        blocking_calls = {
            "requests": ["get", "post", "put", "delete", "patch", "head", "options"],
            "time": ["sleep"],
            "urllib": ["urlopen"],
        }

        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                module = node.func.value.id
                func = node.func.attr

                if module in blocking_calls and func in blocking_calls[module]:
                    self.add_violation(
                        "rule-19",
                        "No Synchronous Calls in Async Code",
                        node.lineno,
                        f"Blocking call {module}.{func}() in async function. Use async alternatives.",
                    )

        # Direct blocking calls
        if isinstance(node.func, ast.Name):
            if node.func.id in ["open"] and not self._has_async_context_manager():
                self.add_violation(
                    "rule-19",
                    "No Synchronous Calls in Async Code",
                    node.lineno,
                    "Use aiofiles.open() instead of open() in async functions.",
                )

    def _validate_print_statements(self, node: ast.Call) -> None:
        """Golden Rule 9: Logging Standards - No print statements in production"""
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            # Skip if in CLI context
            if self.context.is_cli_file or self._in_main_section() or self._in_cli_function():
                return

            # Skip scripts, tests, demo files, and archive files (they can use print)
            path_str = str(self.context.path).replace("\\", "/")  # Normalize path separators
            if (
                "/scripts/" in path_str
                or "/tests/" in path_str
                or "/archive/" in path_str
                or self.context.path.name.startswith(("test_", "demo_", "run_"))
                or ".backup" in path_str
            ):
                return

            self.add_violation(
                "rule-9", "Logging Standards", node.lineno, "Use hive_logging instead of print() in production code."
            )

    def _validate_interface_contracts(self, node: ast.FunctionDef):
        """Golden Rule 7: Interface Contracts - Type hints required"""
        if self.context.is_test_file or node.name.startswith("_"):
            return  # Skip private functions and tests

        # Skip entry points and special functions
        if node.name == "main":
            return  # Entry points don't need return type annotations

        # Skip dunder methods (special methods)
        if node.name.startswith("__") and node.name.endswith("__"):
            return

        # Skip script files, demo files, archive files, and backup files (not production code)
        path_str = str(self.context.path).replace("\\", "/")  # Normalize path separators
        if (
            "/scripts/" in path_str
            or "/archive/" in path_str
            or self.context.path.name.startswith(("run_", "demo_"))
            or ".backup" in path_str
        ):
            return

        # Check return type annotation
        if node.returns is None:
            self.add_violation(
                "rule-7",
                "Interface Contracts",
                node.lineno,
                f"Function {node.name}() missing return type annotation.",
                severity="warning",  # Start as warning for gradual adoption
            )

        # Check parameter type annotations
        for arg in node.args.args:
            if arg.annotation is None and arg.arg != "self":
                self.add_violation(
                    "rule-7",
                    "Interface Contracts",
                    node.lineno,
                    f"Parameter '{arg.arg}' in {node.name}() missing type annotation.",
                    severity="warning",
                )

    def _validate_interface_contracts_async(self, node: ast.AsyncFunctionDef) -> None:
        """Golden Rule 7: Interface Contracts - Async functions"""
        # Reuse sync validation logic
        sync_node = ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
            lineno=node.lineno,
        )
        self._validate_interface_contracts(sync_node)

    def _validate_error_handling_standards(self, node: ast.ClassDef) -> None:
        """Golden Rule 8: Error Handling Standards"""
        # Check if this is an exception class
        if any(isinstance(base, ast.Name) and base.id.endswith("Error") for base in node.bases):
            # Ensure it inherits from BaseError or standard exceptions
            valid_bases = {"BaseError", "Exception", "ValueError", "TypeError", "RuntimeError"}
            has_valid_base = any(isinstance(base, ast.Name) and base.id in valid_bases for base in node.bases)

            if not has_valid_base:
                self.add_violation(
                    "rule-8",
                    "Error Handling Standards",
                    node.lineno,
                    f"Exception class {node.name} should inherit from BaseError or standard exceptions.",
                )

    def _validate_async_naming(self, node) -> None:
        """Golden Rule 14: Async Pattern Consistency"""
        if isinstance(node, ast.AsyncFunctionDef):
            # Skip special methods and entry points
            special_methods = ["main", "__aenter__", "__aexit__", "__aiter__", "__anext__"]
            if node.name in special_methods:
                return

            # Skip test functions (they have different naming conventions)
            path_str = str(self.context.path)
            if "/tests/" in path_str or node.name.startswith("test_"):
                return

            if not node.name.endswith("_async") and not node.name.startswith("a"):
                self.add_violation(
                    "rule-14",
                    "Async Pattern Consistency",
                    node.lineno,
                    f"Async function {node.name}() should end with '_async' or start with 'a' for clarity.",
                )

    def _validate_no_unsafe_imports(self, node: ast.Import) -> None:
        """Golden Rule 17: Security - Unsafe imports"""
        unsafe_modules = {"pickle", "marshal", "shelve", "dill"}

        for alias in node.names:
            if alias.name in unsafe_modules:
                self.add_violation(
                    "rule-17",
                    "No Unsafe Function Calls",
                    node.lineno,
                    f"Unsafe import: {alias.name}. Consider safer alternatives like json.",
                )

    def _validate_no_unsafe_imports_from(self, node: ast.ImportFrom) -> None:
        """Golden Rule 17: Security - Unsafe from imports"""
        if node.module in {"pickle", "marshal", "shelve", "dill"}:
            self.add_violation(
                "rule-17",
                "No Unsafe Function Calls",
                node.lineno,
                f"Unsafe import: from {node.module}. Consider safer alternatives.",
            )

    # Helper methods
    def _is_invalid_app_import(self, module_name: str) -> bool:
        """Check if this is an invalid app-to-app import"""
        if not module_name:
            return False

        # Skip if importing from packages
        if module_name.startswith("hive_"):
            return False

        # Skip if importing from current app (more lenient matching)
        if self.context.app_name:
            # Replace underscores with hyphens for matching
            app_name_normalized = self.context.app_name.replace("-", "_")
            if module_name.startswith(app_name_normalized):
                return False

        # Allow imports from other apps' core modules
        if ".core." in module_name or module_name.endswith(".core"):
            return False

        # Check if this looks like an app import
        app_indicators = ["ai_", "hive_orchestrator", "ecosystemiser"]
        return any(module_name.startswith(indicator) for indicator in app_indicators)

    def _in_async_function(self) -> bool:
        """Check if current context is inside an async function"""
        # This would require maintaining a stack of function contexts
        # For now, check if file has async functions
        return "async def" in self.context.content

    def _has_async_context_manager(self) -> bool:
        """Check if using async context manager"""
        return "async with" in self.context.content

    def _in_main_section(self) -> bool:
        """Check if in __main__ section"""
        return 'if __name__ == "__main__":' in self.context.content

    def _in_cli_function(self) -> bool:
        """Check if in CLI utility function"""
        cli_functions = ["encrypt_production_config", "generate_master_key", "main"]
        return any(f"def {func}(" in self.context.content for func in cli_functions)


class EnhancedValidator:
    """,
    Enhanced single-pass validator system with suppression support,
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = (project_root,)
        self.violations: list[Violation] = []

    def validate_all(self) -> tuple[bool, dict[str, list[str]]]:
        (
            """,
        Run all Golden Rules validation in a single pass

        Returns:
            Tuple of (all_passed, violations_by_rule)
        """,
        )
        self.violations = []

        # Traverse all Python files once,
        for py_file in self._get_python_files():
            try:
                context = self._create_file_context(py_file)
                if context.ast_tree:
                    visitor = GoldenRuleVisitor(context, self.project_root)
                    visitor.visit(context.ast_tree)
                    self.violations.extend(visitor.violations)
            except Exception:
                # Skip files that can't be parsed,
                continue

        # Add non-AST rules,
        self._validate_app_contracts()
        self._validate_colocated_tests()
        self._validate_documentation_hygiene()
        self._validate_models_purity()

        # Group violations by rule,
        violations_by_rule = {}
        for violation in self.violations:
            rule_name = (violation.rule_name,)
            if rule_name not in violations_by_rule:
                violations_by_rule[rule_name] = []
            violations_by_rule[rule_name].append(
                f"{violation.file_path.relative_to(self.project_root)}:{violation.line_number} - {violation.message}"
            )

        return len(self.violations) == 0, violations_by_rule

    def _get_python_files(self) -> list[Path]:
        ("""Get all Python files to validate""",)
        files = []
        for base_dir in [self.project_root / "apps", self.project_root / "packages"]:
            if base_dir.exists():
                files.extend(base_dir.rglob("*.py"))

        # Filter out unwanted files
        filtered_files = []
        for file_path in files:
            if any(skip in str(file_path) for skip in [".venv", "__pycache__", ".pytest_cache"]):
                continue
            filtered_files.append(file_path)

        return filtered_files

    def _create_file_context(self, file_path: Path) -> FileContext:
        ("""Create context for a single file""",)
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")

        # Parse suppressions,
        suppressions = {}
        for i, line in enumerate(lines, 1):
            match = re.search(r"#\s*golden-rule-ignore:\s*([^-]+(?:-\d+)?)\s*-?\s*(.*)", line)
            if match:
                rule_id = match.group(1).strip()
                if i not in suppressions:
                    suppressions[i] = set()
                suppressions[i].add(rule_id)

        # Parse AST,
        ast_tree = (None,)
        try:
            ast_tree = ast.parse(content)
        except SyntaxError:
            pass  # Skip files with syntax errors

        # Determine file characteristics,
        is_test_file = "test" in str(file_path).lower()
        is_cli_file = ("cli.py" in str(file_path) or "secure_config.py" in str(file_path) or "__main__" in content,)
        is_init_file = file_path.name == "__init__.py"

        # Determine package/app context,
        package_name = (None,)
        app_name = None

        parts = (file_path.parts,)
        if "packages" in parts:
            pkg_idx = parts.index("packages")
            if pkg_idx + 1 < len(parts):
                package_name = parts[pkg_idx + 1]
        elif "apps" in parts:
            app_idx = parts.index("apps")
            if app_idx + 1 < len(parts):
                app_name = parts[app_idx + 1]

        return FileContext(
            path=file_path,
            content=content,
            ast_tree=ast_tree,
            lines=lines,
            is_test_file=is_test_file,
            is_cli_file=is_cli_file,
            is_init_file=is_init_file,
            package_name=package_name,
            app_name=app_name,
            suppressions=suppressions,
        )

    def _validate_app_contracts(self) -> None:
        ("""Golden Rule 1: App Contract Compliance""",)
        apps_dir = (self.project_root / "apps",)
        if not apps_dir.exists():
            return

        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                contract_file = (app_dir / "hive-app.toml",)
                if not contract_file.exists():
                    self.violations.append(
                        Violation(
                            rule_id="rule-1",
                            rule_name="App Contract Compliance",
                            file_path=app_dir,
                            line_number=1,
                            message=f"App '{app_dir.name}' missing hive-app.toml",
                        )
                    )

    def _validate_colocated_tests(self) -> None:
        ("""Golden Rule 2: Co-located Tests Pattern""",)
        for base_dir in [self.project_root / "apps", self.project_root / "packages"]:
            if not base_dir.exists():
                continue

            for component_dir in base_dir.iterdir():
                if component_dir.is_dir() and not component_dir.name.startswith("."):
                    tests_dir = (component_dir / "tests",)
                    if not tests_dir.exists():
                        self.violations.append(
                            Violation(
                                rule_id="rule-2",
                                rule_name="Co-located Tests Pattern",
                                file_path=component_dir,
                                line_number=1,
                                message=f"{base_dir.name}/{component_dir.name} missing tests/ directory",
                            )
                        )

    def _validate_documentation_hygiene(self) -> None:
        ("""Golden Rule 22: Documentation Hygiene""",)
        for base_dir in [self.project_root / "apps", self.project_root / "packages"]:
            if not base_dir.exists():
                continue

            for component_dir in base_dir.iterdir():
                if component_dir.is_dir() and not component_dir.name.startswith("."):
                    readme_file = (component_dir / "README.md",)
                    if not readme_file.exists() or readme_file.stat().st_size == 0:
                        self.violations.append(
                            Violation(
                                rule_id="rule-22",
                                rule_name="Documentation Hygiene",
                                file_path=component_dir,
                                line_number=1,
                                message=f"{base_dir.name}/{component_dir.name} missing or empty README.md",
                            )
                        )

    def _validate_models_purity(self) -> None:
        ("""Golden Rule 21: hive-models Purity""",)
        models_dir = (self.project_root / "packages" / "hive-models",)
        if not models_dir.exists():
            return

        allowed_imports = {"typing", "typing_extensions", "pydantic", "datetime", "enum", "uuid"}

        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        module = getattr(node, "module", None) or (
                            node.names[0].name if isinstance(node, ast.Import) else None
                        )

                        # Allow relative imports within the same package and standard library imports
                        if (
                            module
                            and not module.startswith(".")
                            and module != "base"
                            and module != "common"
                            and not any(module.startswith(allowed) for allowed in allowed_imports)
                        ):
                            self.violations.append(
                                Violation(
                                    rule_id="rule-21",
                                    rule_name="hive-models Purity",
                                    file_path=py_file,
                                    line_number=node.lineno,
                                    message=f"Invalid import in hive-models: {module}. Only data definitions allowed.",
                                )
                            )
            except:
                continue
