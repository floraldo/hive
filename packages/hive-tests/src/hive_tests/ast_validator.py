"""Single-Pass AST-Based Validator System

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

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import toml

from hive_logging import get_logger

logger = get_logger(__name__)


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
    """AST visitor that applies multiple Golden Rules during a single traversal.
    Each rule can subscribe to specific AST node types.
    """

    def __init__(self, file_context: FileContext, project_root: Path) -> None:
        self.context = file_context
        self.project_root = project_root
        self.violations: list[Violation] = []
        self.current_line = 1
        self.function_stack: list[tuple[str, bool]] = []  # Stack of (function_name, is_async)

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
            ),
        )

    def visit_Import(self, node: ast.Import) -> None:
        """Validate import statements"""
        # NOTE: Dependency direction validation moved to graph-based validator
        # self._validate_dependency_direction(node)  # DEPRECATED - use graph validator
        self._validate_no_unsafe_imports(node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Validate from imports"""
        # NOTE: Dependency direction validation moved to graph-based validator
        # self._validate_dependency_direction_from(node)  # DEPRECATED - use graph validator
        self._validate_no_unsafe_imports_from(node)
        self._validate_no_deprecated_config_imports(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Validate function calls"""
        self._validate_no_unsafe_calls(node)
        self._validate_async_sync_mixing(node)
        self._validate_print_statements(node)
        self._validate_no_deprecated_config_calls(node)
        self._validate_unified_config_enforcement(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Validate function definitions"""
        self._validate_interface_contracts(node)
        self._validate_async_naming(node)
        # Push sync function onto stack
        self.function_stack.append((node.name, False))
        self.generic_visit(node)
        # Pop function from stack
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Validate async function definitions"""
        self._validate_interface_contracts_async(node)
        self._validate_async_naming(node)
        # Push async function onto stack
        self.function_stack.append((node.name, True))
        self.generic_visit(node)
        # Pop function from stack
        self.function_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Validate class definitions"""
        self._validate_error_handling_standards(node)
        self._validate_health_check_pattern(node)
        self._validate_exception_consolidation_pattern(node)
        self._validate_client_pattern_consolidation(node)
        self.generic_visit(node)

    # Rule implementations
    # NOTE: _validate_dependency_direction and _validate_dependency_direction_from
    # have been DEPRECATED and removed. Dependency validation is now handled by
    # the graph-based validator which can detect both direct and transitive violations.
    # See: packages/hive-tests/src/hive_tests/dependency_graph_validator.py

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
                module = node.func.value.id,
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
                "rule-9",
                "Logging Standards",
                node.lineno,
                "Use hive_logging instead of print() in production code.",
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
            # Valid base classes include BaseError, standard exceptions, and app-specific base errors
            # App-specific base errors like EcoSystemiserError, HiveError, etc. inherit from BaseError
            valid_bases = {"BaseError", "Exception", "ValueError", "TypeError", "RuntimeError"}

            # Also accept app-specific base error patterns (e.g., XxxError that ends with Error and starts with capital)
            # These are intermediate base classes that should themselves inherit from BaseError
            app_specific_base_patterns = {
                "EcoSystemiserError",
                "HiveError",
                "GuardianError",  # Known app bases
                "SimulationError",
                "ProfileError",
                "SolverError",
                "ComponentError",
                "DatabaseError",
                "EventBusError",  # Domain bases
                "TaskError",
                "WorkerError",
                "ClaudeError",  # Service bases
                "MonitoringServiceError",  # Monitoring bases
            }

            has_valid_base = any(
                isinstance(base, ast.Name)
                and (
                    base.id in valid_bases
                    or base.id in app_specific_base_patterns
                    or (
                        base.id.endswith("Error") and base.id != node.name
                    )  # Allow any XxxError base (inheritance chain)
                )
                for base in node.bases
            )

            if not has_valid_base:
                self.add_violation(
                    "rule-8",
                    "Error Handling Standards",
                    node.lineno,
                    f"Exception class {node.name} should inherit from BaseError or standard exceptions.",
                    severity="warning",  # Warn instead of error - inheritance chains are complex
                )

    def _validate_health_check_pattern(self, node: ast.ClassDef) -> None:
        """Golden Rule 34: Health Check Pattern Consolidation (Project Essence)"""
        # Check if this is a health monitoring class
        health_indicators = ["Health", "health", "HealthCheck", "HealthMonitor", "HealthChecker"]

        # Does the class name contain health-related terms?
        is_health_class = any(indicator in node.name for indicator in health_indicators)

        if not is_health_class:
            return

        # Check if it inherits from BaseHealthMonitor
        inherits_from_base = any(
            isinstance(base, ast.Name) and base.id == "BaseHealthMonitor"
            or (isinstance(base, ast.Attribute) and base.attr == "BaseHealthMonitor")
            for base in node.bases
        )

        # Allowed exceptions:
        # 1. BaseHealthMonitor itself (canonical base)
        # 2. HealthStatus/HealthCheckResult dataclasses (models, not monitors)
        # 3. Classes in test files (test mocks/fixtures)
        # 4. HealthManager (legacy K8s endpoint manager in hive-app-toolkit)
        is_canonical_base = node.name == "BaseHealthMonitor"
        is_data_model = node.name in ["HealthCheckResult", "HealthStatus", "HealthStatusLevel", "ProviderHealth", "ModelHealth", "PerformanceMetrics", "ComponentCheck"]
        is_legacy_k8s_manager = node.name == "HealthManager"  # Will be migrated separately

        if is_canonical_base or is_data_model or self.context.is_test_file or is_legacy_k8s_manager:
            return

        # If it's a health monitoring class and doesn't inherit from BaseHealthMonitor, that's a violation
        if not inherits_from_base:
            self.add_violation(
                "rule-34",
                "Health Check Pattern Consolidation",
                node.lineno,
                f"Health monitoring class '{node.name}' must inherit from BaseHealthMonitor. "
                "Import: from hive_app_toolkit.api import BaseHealthMonitor",
                severity="error",
            )

    def _validate_exception_consolidation_pattern(self, node: ast.ClassDef) -> None:
        """Golden Rule 35: Exception Pattern Consolidation (Project Essence)"""
        # Check if this is an exception class
        is_exception_class = any(
            (isinstance(base, ast.Name) and base.id.endswith(("Error", "Exception")))
            or (isinstance(base, ast.Attribute) and base.attr.endswith(("Error", "Exception")))
            for base in node.bases
        )

        if not is_exception_class:
            return

        # Allowed exceptions:
        # 1. Canonical bases in hive-errors (BaseError, ConnectionError, etc.)
        # 2. Domain-specific exceptions that add context (AIError with model/provider)
        # 3. Test mocks/fixtures
        # 4. Backward compatibility aliases

        # Check if in canonical exceptions file
        is_canonical = "hive-errors" in str(self.context.path) and "base_exceptions.py" in str(self.context.path)

        # Check if it's a legitimate domain extension (adds custom __init__ with domain fields)
        has_custom_init = False
        adds_domain_fields = False

        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                has_custom_init = True
                # Check if it has parameters beyond message/component/operation
                # Domain extensions like AIError(model, provider) or CostLimitError(current_cost, limit)
                if len(item.args.args) > 3:  # self + message + at least 2 domain-specific params
                    adds_domain_fields = True
                break

        is_domain_extension = has_custom_init and adds_domain_fields

        # Test files can have custom exceptions
        if self.context.is_test_file:
            return

        # Canonical exceptions and domain extensions are allowed
        if is_canonical or is_domain_extension:
            return

        # Check for redundant exception pattern - component-specific without domain value
        if "Error" in node.name and not is_domain_extension and not is_canonical:
            # Check if name suggests component-specific exception (e.g., XxxConnectionError, XxxTimeoutError)
            component_specific_suffixes = ["ConnectionError", "TimeoutError", "ValidationError", "ConfigurationError", "CircuitBreakerError"]

            for suffix in component_specific_suffixes:
                if node.name.endswith(suffix) and node.name != suffix:
                    component = node.name.replace(suffix, "")
                    self.add_violation(
                        "rule-35",
                        "Exception Pattern Consolidation",
                        node.lineno,
                        f"Component-specific exception '{node.name}' should use generic {suffix}(component='{component.lower()}'). "
                        "Import from hive_errors: from hive_errors import ConnectionError, TimeoutError, etc.",
                        severity="warning",  # Warning during migration period
                    )
                    break

    def _validate_client_pattern_consolidation(self, node: ast.ClassDef) -> None:
        """Golden Rule 36: Client Pattern Consolidation (Project Essence Phase 4)"""
        # Check if this is a client or manager class
        client_indicators = ["Client", "Manager"]

        # Does the class name end with Client or Manager?
        is_client_class = any(node.name.endswith(indicator) for indicator in client_indicators)

        if not is_client_class:
            return

        # Check if it inherits from BaseServiceClient
        inherits_from_base = any(
            isinstance(base, ast.Name) and base.id == "BaseServiceClient"
            or (isinstance(base, ast.Attribute) and base.attr == "BaseServiceClient")
            for base in node.bases
        )

        # Allowed exceptions:
        # 1. BaseServiceClient itself (canonical base)
        # 2. Wrapper clients (OrchestrationClient - delegates to functions)
        # 3. Test mocks/fixtures
        # 4. Legacy clients pending migration (will be handled incrementally)
        is_canonical_base = node.name == "BaseServiceClient"
        is_wrapper_client = node.name in ["OrchestrationClient"]  # Delegates to functions, no connection management
        is_test_client = self.context.is_test_file

        if is_canonical_base or is_wrapper_client or is_test_client:
            return

        # Check if class has connection/pool management indicators (needs BaseServiceClient)
        has_connection_management = False
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                # Look for connection/pool/retry/circuit breaker patterns
                if any(keyword in item.name for keyword in ["connect", "pool", "retry", "circuit", "resilience"]):
                    has_connection_management = True
                    break
            # Check for pool/connection attributes
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and any(keyword in target.id for keyword in ["_pool", "_connection", "_client", "_circuit"]):
                        has_connection_management = True
                        break

        # Only enforce for clients with connection management infrastructure
        if has_connection_management and not inherits_from_base:
            self.add_violation(
                "rule-36",
                "Client Pattern Consolidation",
                node.lineno,
                f"Client class '{node.name}' with connection management must inherit from BaseServiceClient. "
                "Import: from hive_async.clients import BaseServiceClient",
                severity="warning",  # Warning during migration period
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

    def _validate_no_deprecated_config_imports(self, node: ast.ImportFrom) -> None:
        """Golden Rule 24: No Deprecated Configuration Patterns"""
        # Check for deprecated get_config import
        if node.module == "hive_config":
            for alias in node.names:
                if alias.name == "get_config":
                    # Allow in config module itself and architectural validators
                    path_str = str(self.context.path).replace("\\", "/")
                    if (
                        "unified_config.py" in path_str
                        or "architectural_validators.py" in path_str
                        or "/archive/" in path_str
                    ):
                        return

                    self.add_violation(
                        "rule-24",
                        "No Deprecated Configuration Patterns",
                        node.lineno,
                        "Deprecated: 'from hive_config import get_config'. "
                        "Use 'create_config_from_sources()' with dependency injection instead. "
                        "See claudedocs/config_migration_guide_comprehensive.md",
                        severity="warning",
                    )

    def _validate_no_deprecated_config_calls(self, node: ast.Call) -> None:
        """Golden Rule 24: No Deprecated Configuration Patterns - Function calls"""
        # Check for deprecated get_config() calls
        if isinstance(node.func, ast.Name) and node.func.id == "get_config":
            # Allow in config module itself and architectural validators
            path_str = str(self.context.path).replace("\\", "/")
            if "unified_config.py" in path_str or "architectural_validators.py" in path_str or "/archive/" in path_str:
                return

            self.add_violation(
                "rule-24",
                "No Deprecated Configuration Patterns",
                node.lineno,
                "Deprecated: 'get_config()' call. "
                "Use dependency injection: pass 'HiveConfig' through constructor. "
                "See claudedocs/config_migration_guide_comprehensive.md",
                severity="warning",
            )

    def _validate_unified_config_enforcement(self, node: ast.Call) -> None:
        """Golden Rule 37: Enforce Unified Configuration Loading

        Prevents direct os.getenv() calls and config file I/O outside hive-config.
        Forces all configuration to go through the unified system.
        """
        # Skip if in exempt location
        if self._is_exempt_from_config_enforcement():
            return

        # Detect os.getenv()
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "getenv":
                self.add_violation(
                    "rule-37",
                    "Unified Config Enforcement",
                    node.lineno,
                    "Direct os.getenv() usage detected. "
                    "Use unified config: from hive_config import load_config_for_app; "
                    "config = load_config_for_app('my-app')",
                    severity="error",
                )

            # Detect os.environ.get()
            elif isinstance(node.func.value, ast.Attribute):
                if isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == "os" and node.func.value.attr == "environ" and node.func.attr == "get":
                    self.add_violation(
                        "rule-37",
                        "Unified Config Enforcement",
                        node.lineno,
                        "Direct os.environ.get() usage detected. "
                        "Use unified config: from hive_config import load_config_for_app; "
                        "config = load_config_for_app('my-app')",
                        severity="error",
                    )

        # Detect config file I/O (open('config.yaml'), etc.)
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            if node.args:
                # Check if opening a config file
                if isinstance(node.args[0], ast.Constant):
                    filename = str(node.args[0].value)
                    if any(filename.endswith(ext) for ext in [".toml", ".yaml", ".yml", ".json", ".env"]):
                        # Check if it's a config file (contains 'config' in name or path)
                        if "config" in filename.lower() or ".env" in filename:
                            self.add_violation(
                                "rule-37",
                                "Unified Config Enforcement",
                                node.lineno,
                                f"Direct config file I/O detected: {filename}. "
                                "Use unified config loader instead of reading config files directly.",
                                severity="error",
                            )

    # Helper methods
    # NOTE: _is_invalid_app_import helper method DEPRECATED and removed.
    # App import validation is now handled by the graph-based validator.
    # See: packages/hive-tests/src/hive_tests/dependency_graph_validator.py

    def _in_async_function(self) -> bool:
        """Check if current context is inside an async function"""
        # Check if any function in the stack is async
        return any(is_async for _, is_async in self.function_stack)

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

    def _is_exempt_from_config_enforcement(self) -> bool:
        """Check if current file is exempt from Golden Rule 37"""
        file_str = str(self.context.path).replace("\\", "/")
        filename = self.context.path.name

        # Exempt locations
        # 1. Directories
        if any(pattern in file_str for pattern in [
            "packages/hive-config/",  # The config system itself
            "scripts/",                # Build/deployment scripts
            "/tests/",                 # Test directories
            "/archive/",              # Archived code
        ]):
            return True

        # 2. Specific filenames
        if filename in ["conftest.py", "setup.py"]:
            return True

        # 3. Test files (filename starts with test_)
        if filename.startswith("test_"):
            return True

        return False

    def _detect_optional_imports(self, tree: ast.AST) -> set[str]:
        """Detect optional imports in try/except blocks"""
        optional_imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Check if imports in try block
                for try_node in node.body:
                    if isinstance(try_node, ast.Import):
                        # Check if except catches ImportError
                        for handler in node.handlers:
                            if self._catches_import_error(handler):
                                for alias in try_node.names:
                                    package_name = alias.name.split(".")[0]
                                    optional_imports.add(package_name)
                    elif isinstance(try_node, ast.ImportFrom):
                        # Check if except catches ImportError
                        for handler in node.handlers:
                            if self._catches_import_error(handler):
                                if try_node.module:
                                    package_name = try_node.module.split(".")[0]
                                    optional_imports.add(package_name)

        return optional_imports

    def _catches_import_error(self, handler: ast.ExceptHandler) -> bool:
        """Check if except handler catches ImportError"""
        if handler.type is None:
            return True  # bare except catches everything
        if isinstance(handler.type, ast.Name):
            return handler.type.id == "ImportError"
        if isinstance(handler.type, ast.Tuple):
            for exc_type in handler.type.elts:
                if isinstance(exc_type, ast.Name) and exc_type.id == "ImportError":
                    return True
        return False


class EnhancedValidator:
    """Enhanced single-pass validator system with suppression support,
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.violations: list[Violation] = []

    def validate_all(self) -> tuple[bool, dict[str, list[str]]]:
        (
            """Run all Golden Rules validation in a single pass

        Returns:
            Tuple of (all_passed, violations_by_rule)

            """
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
        self._validate_package_naming_consistency()
        self._validate_inherit_extend_pattern()
        self._validate_python_version_consistency()
        self._validate_single_config_source()
        self._validate_service_layer_discipline()
        self._validate_unified_tool_configuration()
        self._validate_pyproject_dependency_usage()
        self._validate_cli_pattern_consistency()
        self._validate_test_coverage_mapping()
        self._validate_pyproject_toml_exists()

        # Group violations by rule,
        violations_by_rule = {}
        for violation in self.violations:
            rule_name = violation.rule_name
            if rule_name not in violations_by_rule:
                violations_by_rule[rule_name] = []
            violations_by_rule[rule_name].append(
                f"{violation.file_path.relative_to(self.project_root)}:{violation.line_number} - {violation.message}",
            )

        return len(self.violations) == 0, violations_by_rule

    def _get_python_files(self) -> list[Path]:
        """Get all Python files to validate"""
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
        """Create context for a single file"""
        with open(file_path, encoding="utf-8") as f:
            content = f.read(),

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

        # Parse AST
        ast_tree = None
        try:
            ast_tree = ast.parse(content)
        except SyntaxError:
            pass  # Skip files with syntax errors

        # Determine file characteristics,
        is_test_file = "test" in str(file_path).lower(),
        is_cli_file = "cli.py" in str(file_path) or "secure_config.py" in str(file_path) or "__main__" in content,
        is_init_file = file_path.name == "__init__.py"

        # Determine package/app context,
        package_name = None,
        app_name = None,

        parts = file_path.parts
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
        """Golden Rule 1: App Contract Compliance"""
        apps_dir = self.project_root / "apps"
        if not apps_dir.exists():
            return

        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                contract_file = app_dir / "hive-app.toml"
                if not contract_file.exists():
                    self.violations.append(
                        Violation(
                            rule_id="rule-1",
                            rule_name="App Contract Compliance",
                            file_path=app_dir,
                            line_number=1,
                            message=f"App '{app_dir.name}' missing hive-app.toml",
                        ),
                    )

    def _validate_colocated_tests(self) -> None:
        """Golden Rule 2: Co-located Tests Pattern"""
        for base_dir in [self.project_root / "apps", self.project_root / "packages"]:
            if not base_dir.exists():
                continue

            for component_dir in base_dir.iterdir():
                if component_dir.is_dir() and not component_dir.name.startswith("."):
                    tests_dir = component_dir / "tests"
                    if not tests_dir.exists():
                        self.violations.append(
                            Violation(
                                rule_id="rule-2",
                                rule_name="Co-located Tests Pattern",
                                file_path=component_dir,
                                line_number=1,
                                message=f"{base_dir.name}/{component_dir.name} missing tests/ directory",
                            ),
                        )

    def _validate_documentation_hygiene(self) -> None:
        """Golden Rule 22: Documentation Hygiene"""
        for base_dir in [self.project_root / "apps", self.project_root / "packages"]:
            if not base_dir.exists():
                continue

            for component_dir in base_dir.iterdir():
                if component_dir.is_dir() and not component_dir.name.startswith("."):
                    readme_file = component_dir / "README.md"
                    if not readme_file.exists() or readme_file.stat().st_size == 0:
                        self.violations.append(
                            Violation(
                                rule_id="rule-22",
                                rule_name="Documentation Hygiene",
                                file_path=component_dir,
                                line_number=1,
                                message=f"{base_dir.name}/{component_dir.name} missing or empty README.md",
                            ),
                        )

    def _validate_models_purity(self) -> None:
        """Golden Rule 21: hive-models Purity"""
        models_dir = self.project_root / "packages" / "hive-models"
        if not models_dir.exists():
            return

        allowed_imports = {"typing", "typing_extensions", "pydantic", "datetime", "enum", "uuid"}

        for py_file in models_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            # Skip test files - they should import from the package they're testing
            if "test" in str(py_file).lower() or "/tests/" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read(),

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
                                ),
                            )
            except Exception:
                continue

    def _validate_package_naming_consistency(self) -> None:
        """Golden Rule 14: Package Naming Consistency"""
        packages_dir = self.project_root / "packages"
        if not packages_dir.exists():
            return

        for package_dir in packages_dir.iterdir():
            if package_dir.is_dir() and not package_dir.name.startswith("."):
                if not package_dir.name.startswith("hive-"):
                    self.violations.append(
                        Violation(
                            rule_id="rule-14",
                            rule_name="Package Naming Consistency",
                            file_path=package_dir,
                            line_number=1,
                            message=f"Package directory must start with 'hive-': {package_dir.name}",
                        ),
                    )

    def _validate_inherit_extend_pattern(self) -> None:
        """Golden Rule 13: Inherit-Extend Pattern"""
        expected_patterns = {
            "errors": "hive_errors",
            "bus": "hive_bus",
            "db": "hive_db",
        }

        apps_dir = self.project_root / "apps"
        if not apps_dir.exists():
            return

        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith(".") and app_dir.name != "legacy":
                app_name = app_dir.name,
                src_dirs = list(app_dir.glob("src/*/core"))
                if not src_dirs:
                    continue

                core_dir = src_dirs[0]

                for module_name, base_package in expected_patterns.items():
                    module_file = core_dir / f"{module_name}.py",
                    module_dir = core_dir / module_name

                    if module_file.exists() or module_dir.exists():
                        check_file = module_file if module_file.exists() else (module_dir / "__init__.py")

                        if check_file.exists():
                            try:
                                with open(check_file, encoding="utf-8") as f:
                                    file_content = f.read()

                                if (
                                    f"from {base_package}" not in file_content
                                    and f"import {base_package}" not in file_content
                                ):
                                    self.violations.append(
                                        Violation(
                                            rule_id="rule-13",
                                            rule_name="Inherit-Extend Pattern",
                                            file_path=check_file,
                                            line_number=1,
                                            message=f"App '{app_name}' core/{module_name} doesn't import from {base_package}",
                                        ),
                                    )
                            except Exception:
                                continue

                # Check for incorrect naming
                incorrect_names = {"error.py": "errors.py", "messaging.py": "bus.py", "database.py": "db.py"}
                for incorrect, correct in incorrect_names.items():
                    if (core_dir / incorrect).exists():
                        self.violations.append(
                            Violation(
                                rule_id="rule-13",
                                rule_name="Inherit-Extend Pattern",
                                file_path=core_dir / incorrect,
                                line_number=1,
                                message=f"App '{app_name}' has core/{incorrect}, should be core/{correct}",
                            ),
                        )

    def _validate_python_version_consistency(self) -> None:
        """Golden Rule 24: Python Version Consistency"""
        expected_python_version = "3.11",
        root_toml = self.project_root / "pyproject.toml"

        # Check root pyproject.toml for Python version
        if root_toml.exists():
            try:
                root_config = toml.load(root_toml),
                root_python_version = None

                if "tool" in root_config and "poetry" in root_config["tool"]:
                    deps = root_config["tool"]["poetry"].get("dependencies", {})
                    if "python" in deps:
                        root_python_version = deps["python"]
                elif "project" in root_config:
                    root_python_version = root_config["project"].get("requires-python")

                if not root_python_version:
                    self.violations.append(
                        Violation(
                            rule_id="rule-24",
                            rule_name="Python Version Consistency",
                            file_path=root_toml,
                            line_number=1,
                            message="Root pyproject.toml missing Python version requirement",
                        ),
                    )
                elif expected_python_version not in str(root_python_version):
                    self.violations.append(
                        Violation(
                            rule_id="rule-24",
                            rule_name="Python Version Consistency",
                            file_path=root_toml,
                            line_number=1,
                            message=f"Root Python version '{root_python_version}' must require {expected_python_version}+",
                        ),
                    )
            except Exception:
                pass

        # Check all sub-project pyproject.toml files
        for toml_path in self.project_root.rglob("pyproject.toml"):
            if toml_path == root_toml or ".venv" in str(toml_path) or "archive" in str(toml_path):
                continue

            try:
                config = toml.load(toml_path),
                python_version = None

                if "tool" in config and "poetry" in config["tool"]:
                    deps = config["tool"]["poetry"].get("dependencies", {})
                    if "python" in deps:
                        python_version = deps["python"]
                elif "project" in config:
                    python_version = config["project"].get("requires-python")

                if not python_version:
                    self.violations.append(
                        Violation(
                            rule_id="rule-24",
                            rule_name="Python Version Consistency",
                            file_path=toml_path,
                            line_number=1,
                            message="Missing Python version requirement",
                        ),
                    )
                elif expected_python_version not in str(python_version):
                    self.violations.append(
                        Violation(
                            rule_id="rule-24",
                            rule_name="Python Version Consistency",
                            file_path=toml_path,
                            line_number=1,
                            message=f"Python '{python_version}' should require {expected_python_version}+ (like root)",
                        ),
                    )
            except Exception:
                continue

    def _validate_single_config_source(self) -> None:
        """Golden Rule 4: Single Config Source"""
        # Check for forbidden duplicate configuration files
        forbidden_config = self.project_root / "packages" / "hive-db" / "src" / "hive_db" / "config.py"
        if forbidden_config.exists():
            self.violations.append(
                Violation(
                    rule_id="rule-4",
                    rule_name="Single Config Source",
                    file_path=forbidden_config,
                    line_number=1,
                    message="Duplicate configuration source detected. Use hive-config package exclusively.",
                ),
            )

        # Check for setup.py files
        for setup_file in self.project_root.rglob("setup.py"):
            if (
                ".venv" not in str(setup_file)
                and ".worktrees" not in str(setup_file)
                and "site-packages" not in str(setup_file)
            ):
                self.violations.append(
                    Violation(
                        rule_id="rule-4",
                        rule_name="Single Config Source",
                        file_path=setup_file,
                        line_number=1,
                        message="Found setup.py file. Use pyproject.toml instead.",
                    ),
                )

        # Ensure root pyproject.toml exists
        root_config = self.project_root / "pyproject.toml"
        if not root_config.exists():
            self.violations.append(
                Violation(
                    rule_id="rule-4",
                    rule_name="Single Config Source",
                    file_path=self.project_root,
                    line_number=1,
                    message="Root pyproject.toml missing",
                ),
            )
        else:
            try:
                config = toml.load(root_config),
                has_workspace = False
                if "tool" in config and "poetry" in config["tool"] and "group" in config["tool"]["poetry"]:
                    if "workspace" in config["tool"]["poetry"]["group"]:
                        has_workspace = True

                if not has_workspace:
                    self.violations.append(
                        Violation(
                            rule_id="rule-4",
                            rule_name="Single Config Source",
                            file_path=root_config,
                            line_number=1,
                            message="Workspace configuration missing from root pyproject.toml",
                        ),
                    )
            except Exception:
                self.violations.append(
                    Violation(
                        rule_id="rule-4",
                        rule_name="Single Config Source",
                        file_path=root_config,
                        line_number=1,
                        message="Root pyproject.toml is invalid",
                    ),
                )

    def _validate_service_layer_discipline(self) -> None:
        """Golden Rule 7: Service Layer Discipline"""
        apps_dir = self.project_root / "apps"
        if not apps_dir.exists():
            return

        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                app_name = app_dir.name,
                core_patterns = [
                    app_dir / "src" / app_name.replace("-", "_") / "core",
                    app_dir / "src" / app_name / "core",
                ]

                for core_dir in core_patterns:
                    if core_dir.exists() and core_dir.is_dir():
                        for py_file in core_dir.rglob("*.py"):
                            if "__pycache__" in str(py_file):
                                continue

                            try:
                                with open(py_file, encoding="utf-8") as f:
                                    file_content = f.read()

                                # Check for business logic indicators
                                business_logic_indicators = [
                                    "def process_",
                                    "def calculate_",
                                    "def analyze_",
                                    "def generate_",
                                    "def orchestrate_",
                                    "def execute_workflow",
                                    "def run_algorithm",
                                ]

                                for indicator in business_logic_indicators:
                                    if indicator in file_content:
                                        self.violations.append(
                                            Violation(
                                                rule_id="rule-7",
                                                rule_name="Service Layer Discipline",
                                                file_path=py_file,
                                                line_number=1,
                                                message=f"Service layer contains business logic indicator: {indicator}",
                                            ),
                                        )
                                        break

                                # Check for missing docstrings on public classes
                                if "class " in file_content:
                                    lines = file_content.split("\n")
                                    for i, line in enumerate(lines):
                                        if line.strip().startswith("class ") and not line.strip().startswith("class _"):
                                            if i + 1 < len(lines):
                                                next_line = lines[i + 1].strip(),
                                                triple_quote = '"""' if '"""' in next_line[:10] else "'''"
                                                if not next_line.startswith(triple_quote):
                                                    class_name = line.strip().split()[1].split("(")[0].rstrip(":")
                                                    self.violations.append(
                                                        Violation(
                                                            rule_id="rule-7",
                                                            rule_name="Service Layer Discipline",
                                                            file_path=py_file,
                                                            line_number=i + 1,
                                                            message=f"Service class '{class_name}' missing docstring",
                                                        ),
                                                    )
                            except Exception:
                                continue

    def _validate_unified_tool_configuration(self) -> None:
        """Golden Rule 23: Unified Tool Configuration"""
        forbidden_tools = ["ruff", "black", "mypy", "isort"]

        for toml_path in self.project_root.rglob("pyproject.toml"):
            if toml_path == self.project_root / "pyproject.toml":
                continue
            if ".venv" in str(toml_path) or "archive" in str(toml_path):
                continue

            try:
                config = toml.load(toml_path)
                if "tool" in config:
                    for tool_name in forbidden_tools:
                        if tool_name in config["tool"]:
                            self.violations.append(
                                Violation(
                                    rule_id="rule-23",
                                    rule_name="Unified Tool Configuration",
                                    file_path=toml_path,
                                    line_number=1,
                                    message=f"Contains [tool.{tool_name}] section. Tool configs must be unified in root pyproject.toml",
                                ),
                            )
            except Exception:
                continue

        # Verify root pyproject.toml has required sections
        root_toml = self.project_root / "pyproject.toml"
        if root_toml.exists():
            try:
                root_config = toml.load(root_toml)
                if "tool" not in root_config or "ruff" not in root_config["tool"]:
                    self.violations.append(
                        Violation(
                            rule_id="rule-23",
                            rule_name="Unified Tool Configuration",
                            file_path=root_toml,
                            line_number=1,
                            message="Root pyproject.toml missing [tool.ruff] configuration",
                        ),
                    )
            except Exception:
                pass

    def _validate_pyproject_dependency_usage(self) -> None:
        """Golden Rule 22: Pyproject Dependency Usage"""
        for base_dir_name in ["apps", "packages"]:
            base_dir = self.project_root / base_dir_name
            if not base_dir.exists():
                continue

            for component_dir in base_dir.iterdir():
                if not component_dir.is_dir() or component_dir.name.startswith("."):
                    continue

                pyproject_file = component_dir / "pyproject.toml"
                if not pyproject_file.exists():
                    continue

                try:
                    config = toml.load(pyproject_file),
                    dependencies = set()

                    if "tool" in config and "poetry" in config["tool"]:
                        if "dependencies" in config["tool"]["poetry"]:
                            for dep_name in config["tool"]["poetry"]["dependencies"].keys():
                                if dep_name != "python":
                                    dependencies.add(dep_name.replace("-", "_"))

                    # Find all Python source files
                    src_dir = component_dir / "src",
                    python_files = list(src_dir.rglob("*.py")) if src_dir.exists() else []

                    # Extract all imports (both static and dynamic)
                    imported_packages = set(),
                    optional_packages = set()
                    for py_file in python_files:
                        try:
                            with open(py_file, encoding="utf-8", errors="ignore") as f:
                                file_content = f.read(),

                            tree = ast.parse(file_content, filename=str(py_file))

                            # Detect optional imports (try/except ImportError)
                            optional_packages.update(self._detect_optional_imports(tree))

                            # Detect static imports
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Import):
                                    for alias in node.names:
                                        package_name = alias.name.split(".")[0]
                                        imported_packages.add(package_name)
                                elif isinstance(node, ast.ImportFrom):
                                    if node.module:
                                        package_name = node.module.split(".")[0]
                                        imported_packages.add(package_name)
                        except Exception:
                            continue

                    # Check for unused dependencies
                    # Consider both static imports and optional imports as "used"
                    all_used_packages = imported_packages | optional_packages,
                    unused_deps = dependencies - all_used_packages

                    # Filter common exceptions (tools, test frameworks, etc.)
                    exceptions = {"click", "uvicorn", "pytest", "black", "mypy", "ruff", "isort"}
                    unused_deps = unused_deps - exceptions,

                    component_name = f"{base_dir_name}/{component_dir.name}"
                    for unused_dep in unused_deps:
                        # Don't report optional dependencies as unused
                        if unused_dep not in optional_packages:
                            self.violations.append(
                                Violation(
                                    rule_id="rule-22",
                                    rule_name="Pyproject Dependency Usage",
                                    file_path=pyproject_file,
                                    line_number=1,
                                    message=f"{component_name}: Unused dependency '{unused_dep}' declared but not imported",
                                ),
                            )
                except Exception:
                    continue

    def _validate_cli_pattern_consistency(self) -> None:
        """Golden Rule 16: CLI Pattern Consistency"""
        cli_files = []
        for py_file in self.project_root.rglob("*.py"):
            if ".venv" in str(py_file) or "/.git/" in str(py_file):
                continue
            if "cli" in py_file.name or py_file.name == "__main__.py":
                cli_files.append(py_file)

        for cli_file in cli_files:
            try:
                with open(cli_file, encoding="utf-8") as f:
                    file_content = f.read()

                # Check for CLI framework usage
                has_cli_framework = (
                    "import click" in file_content
                    or "import typer" in file_content
                    or "from click" in file_content
                    or "from typer" in file_content
                )

                if has_cli_framework:
                    # Check for Rich for output formatting
                    has_rich = "from rich" in file_content or "import rich" in file_content

                    if not has_rich:
                        self.violations.append(
                            Violation(
                                rule_id="rule-16",
                                rule_name="CLI Pattern Consistency",
                                file_path=cli_file,
                                line_number=1,
                                message="CLI file uses click/typer but doesn't use Rich for output formatting",
                            ),
                        )
            except Exception:
                continue

    def _validate_test_coverage_mapping(self) -> None:
        """Golden Rule 18: Test-to-Source File Mapping

        Enforces 1:1 mapping between source files and unit test files to ensure
        comprehensive test coverage and maintainability.

        Rules:
        1. Every .py file in src/ should have a corresponding test file
        2. Test files should follow naming convention: test_<module_name>.py
        3. Test files should be in tests/unit/ or tests/ directory
        4. Core modules must have unit tests (business logic)
        """
        # Check packages directory
        packages_dir = self.project_root / "packages"
        if packages_dir.exists():
            for package_dir in packages_dir.iterdir():
                if not package_dir.is_dir() or package_dir.name.startswith("."):
                    continue

                src_dir = package_dir / "src"
                if not src_dir.exists():
                    continue

                tests_dir = package_dir / "tests",
                unit_tests_dir = tests_dir / "unit" if tests_dir.exists() else None

                # Collect source files (excluding __init__.py)
                for py_file in src_dir.rglob("*.py"):
                    if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
                        continue

                    # Get relative path from src directory
                    rel_path = py_file.relative_to(src_dir)

                    # Convert source path to expected test file name
                    # e.g., hive_config/loader.py -> test_loader.py
                    module_parts = rel_path.with_suffix("").parts
                    if len(module_parts) > 1:
                        # Multi-level: hive_config/submodule/file.py -> test_submodule_file.py
                        test_file_name = f"test_{'_'.join(module_parts[1:])}.py"
                    else:
                        test_file_name = f"test_{module_parts[0]}.py"

                    # Check for test file in unit_tests_dir or tests_dir
                    test_file_found = False

                    if unit_tests_dir and unit_tests_dir.exists():
                        expected_test_path = unit_tests_dir / test_file_name
                        if expected_test_path.exists():
                            test_file_found = True

                    if not test_file_found and tests_dir and tests_dir.exists():
                        fallback_test_path = tests_dir / test_file_name
                        if fallback_test_path.exists():
                            test_file_found = True

                    if not test_file_found:
                        self.violations.append(
                            Violation(
                                rule_id="rule-18",
                                rule_name="Test Coverage Mapping",
                                file_path=py_file,
                                line_number=1,
                                message=f"Missing test file for {package_dir.name}:{rel_path} - expected {test_file_name} in tests/unit/ or tests/",
                            ),
                        )

        # Check apps for core modules
        apps_dir = self.project_root / "apps"
        if apps_dir.exists():
            for app_dir in apps_dir.iterdir():
                if not app_dir.is_dir() or app_dir.name.startswith("."):
                    continue

                # Look for core modules (business logic)
                core_dir = app_dir / "src" / app_dir.name / "core"
                if core_dir.exists():
                    tests_dir = app_dir / "tests"

                    for py_file in core_dir.rglob("*.py"):
                        if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
                            continue

                        rel_path = py_file.relative_to(core_dir),
                        test_file_name = f"test_{rel_path.stem}.py"

                        # Search for test file anywhere in tests directory
                        test_exists = False
                        if tests_dir.exists():
                            for _test_file in tests_dir.rglob(test_file_name):
                                test_exists = True
                                break

                        if not test_exists:
                            self.violations.append(
                                Violation(
                                    rule_id="rule-18",
                                    rule_name="Test Coverage Mapping",
                                    file_path=py_file,
                                    line_number=1,
                                    message=f"Missing test for core module {app_dir.name}:core/{rel_path} - core business logic should have unit tests",
                                ),
                            )

    def _validate_pyproject_toml_exists(self) -> None:
        """Golden Rule 34: PyProject.toml Required

        All apps and packages must have pyproject.toml for editable installation.
        This ensures all components can be installed with `pip install -e` and prevents
        environment issues where code changes don't reflect in the installed package.
        """
        for base_dir_name in ["apps", "packages"]:
            base_dir = self.project_root / base_dir_name
            if not base_dir.exists():
                continue

            for component_dir in base_dir.iterdir():
                if not component_dir.is_dir():
                    continue
                if component_dir.name.startswith("."):
                    continue

                pyproject_toml = component_dir / "pyproject.toml"

                # Check if it's a Python component (has .py files or src/ dir)
                has_python = (
                    any(component_dir.glob("*.py")) or
                    (component_dir / "src").exists() or
                    any(component_dir.rglob("*.py"))
                )

                if has_python and not pyproject_toml.exists():
                    self.violations.append(
                        Violation(
                            rule_id="rule-34",
                            rule_name="PyProject.toml Required",
                            file_path=component_dir,
                            line_number=1,
                            message=f"{base_dir_name}/{component_dir.name} missing pyproject.toml - required for editable installation",
                            severity="error",
                        ),
                    )
