import ast
from pathlib import Path

import toml
from hive_logging import get_logger

logger = get_logger(__name__)

"""
Architectural Validators - Core validation functions for Hive platform standards.

These validators are used by the Golden Tests to enforce architectural
gravity across the entire platform.
"""

def _should_validate_file(file_path: Path, scope_files: list[Path] | None) -> bool:
    """
    Check if a file should be validated based on scope.

    Args:
        file_path: File to check
        scope_files: Optional list of files to validate (None = validate all)

    Returns:
        True if file should be validated, False otherwise
    """
    if scope_files is None:
        return True

    for scope_file in scope_files:
        try:
            if file_path == scope_file or file_path.is_relative_to(scope_file.parent):
                return True
        except (ValueError, AttributeError):
            if str(file_path) == str(scope_file):
                return True
    return False



def validate_app_contracts(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Validate that all apps have proper hive-app.toml contracts.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []
    apps_dir = project_root / "apps"

    if not apps_dir.exists():
        return False, ["apps/ directory does not exist"]

    for app_dir in apps_dir.iterdir():
        if app_dir.is_dir() and not app_dir.name.startswith("."):
            app_name = app_dir.name
            contract_file = app_dir / "hive-app.toml"

            # Check if contract file exists
            if not contract_file.exists():
                violations.append(f"App '{app_name}' missing hive-app.toml")
                continue

            try:
                contract = toml.load(contract_file)

                # Validate required sections
                if "app" not in contract:
                    violations.append(f"App '{app_name}' missing [app] section in hive-app.toml")
                elif "name" not in contract["app"]:
                    violations.append(f"App '{app_name}' missing app.name in hive-app.toml")

                # Ensure at least one service definition
                service_sections = ["daemons", "tasks", "endpoints"]
                has_service = any(section in contract for section in service_sections)
                if not has_service:
                    violations.append(f"App '{app_name}' missing service definitions (daemons/tasks/endpoints)")

            except Exception as e:
                violations.append(f"App '{app_name}' has invalid hive-app.toml: {str(e)}")

    return len(violations) == 0, violations


def validate_colocated_tests(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Validate that all apps and packages have co-located tests directories.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []
    base_dirs = [project_root / "apps", project_root / "packages"]

    for base_dir in base_dirs:
        if not base_dir.exists():
            continue

        for component_dir in base_dir.iterdir():
            if component_dir.is_dir() and not component_dir.name.startswith("."):
                component_name = f"{base_dir.name}/{component_dir.name}"
                tests_dir = component_dir / "tests"

                if not tests_dir.exists():
                    violations.append(f"{component_name} missing tests/ directory")
                elif not (tests_dir / "__init__.py").exists():
                    violations.append(f"{component_name} missing tests/__init__.py")

    return len(violations) == 0, violations


def validate_no_syspath_hacks(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Validate that no sys.path hacks exist in the codebase.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []
    base_dirs = [project_root / "apps", project_root / "packages"]

    for base_dir in base_dirs:
        if not base_dir.exists():
            continue

        for py_file in base_dir.rglob("*.py"):
            # Skip verification scripts and virtual environments
            # File-level scoping optimization
            if not _should_validate_file(py_file, scope_files):
                continue

            if (
                "verify_environment.py" in str(py_file)
                or "architectural_validators.py" in str(py_file)
                or ".venv" in str(py_file)
                or "__pycache__" in str(py_file)
            ):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Check for actual sys.path manipulation (not just strings)
                lines = content.split("\n")
                for line in lines:
                    # Skip comments and strings
                    if not line.strip().startswith("#"):
                        if "sys.path.insert(" in line or "sys.path.append(" in line:
                            violations.append(str(py_file.relative_to(project_root)))
                            break

            except Exception:
                # Skip files that can't be read
                continue

    return len(violations) == 0, violations


def validate_single_config_source(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Validate that pyproject.toml is the single source of configuration truth.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Check for forbidden duplicate configuration files
    forbidden_config = project_root / "packages" / "hive-db" / "src" / "hive_db" / "config.py"
    if forbidden_config.exists():
        violations.append(
            "CRITICAL: Duplicate configuration source detected - ",
            "packages/hive-db/src/hive_db/config.py should not exist. ",
            "Use hive-config package exclusively.",
        )

    # Check for setup.py files
    setup_files = list(project_root.rglob("setup.py"))
    # Filter out virtual environments and worktrees
    setup_files = [
        f for f in setup_files if ".venv" not in str(f) and ".worktrees" not in str(f) and "site-packages" not in str(f)
    ]

    if setup_files:
        violations.extend([f"Found setup.py file: {f.relative_to(project_root)}" for f in setup_files])

    # Ensure root pyproject.toml exists
    root_config = project_root / "pyproject.toml"
    if not root_config.exists():
        violations.append("Root pyproject.toml missing")
    else:
        try:
            config = toml.load(root_config)
            # Check for workspace configuration
            has_workspace = False
            if "tool" in config and "poetry" in config["tool"] and "group" in config["tool"]["poetry"]:
                if "workspace" in config["tool"]["poetry"]["group"]:
                    has_workspace = True

            if not has_workspace:
                violations.append("Workspace configuration missing from root pyproject.toml")
        except Exception as e:
            violations.append(f"Root pyproject.toml is invalid: {str(e)}")

    return len(violations) == 0, violations


def validate_package_app_discipline(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 5: Package vs App Discipline

    Validate that packages contain only generic infrastructure,
    and apps contain business logic extending packages.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Check packages for business logic indicators
    packages_dir = project_root / "packages"
    if packages_dir.exists():
        business_logic_indicators = [
            "workflow",
            "task",
            "agent",
            "orchestrat",
            "business",
            "domain",
            "service",
            "controller",
            "api",
            "endpoint",
        ]

        for package_dir in packages_dir.iterdir():
            if package_dir.is_dir() and not package_dir.name.startswith("."):
                package_name = package_dir.name

                # Skip known infrastructure packages
                if package_name in [
                    "hive-utils",
                    "hive-logging",
                    "hive-testing-utils",
                    "hive-db-utils",
                    "hive-config",
                    "hive-deployment",
                    "hive-messaging",
                    "hive-error-handling",
                    "hive-async",  # Contains generic async utilities, not business logic
                    "hive-algorithms",  # Contains generic algorithms, not business logic
                    "hive-models",  # Contains data models, not business logic
                    "hive-db",  # Database infrastructure
                    "hive-bus",  # Event bus infrastructure
                    "hive-errors",  # Error handling infrastructure
                    "hive-tests",  # Testing infrastructure
                    "hive-ai",  # AI infrastructure framework (ADR-006)
                    "hive-performance",  # Performance monitoring infrastructure
                    "hive-service-discovery",  # Service discovery infrastructure
                    "hive-cache",  # Caching infrastructure
                ]:
                    continue

                # Check for business logic in package names or files
                for py_file in package_dir.rglob("*.py"):
                    # File-level scoping optimization
                    if not _should_validate_file(py_file, scope_files):
                        continue

                    if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                        continue

                    file_name = py_file.stem.lower()
                    for indicator in business_logic_indicators:
                        if indicator in file_name and "test" not in file_name:
                            violations.append(f"Package '{package_name}' may contain business logic: {py_file.name}")
                            break

    return len(violations) == 0, violations


def validate_dependency_direction(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 6: Dependency Direction

    Validate that:
    - Apps can depend on infrastructure packages
    - Apps can import from other apps' core/ service layers
    - Packages cannot depend on apps
    - Apps cannot import from other apps' internal implementation
    - Business logic stays in apps, service interfaces in core/

    Allowed patterns:
    - App → Infrastructure Package (hive-utils, hive-logging)
    - App → Other App's core/ service layer (hive_orchestrator.core)
    - Package → Other Infrastructure Package

    Forbidden patterns:
    - Package → App (breaks reusability)
    - App → Other App's internal src/ (creates tight coupling)
    - Business logic in packages (violates app ownership)

    Service Layer Pattern:
    - Apps can expose services via app/src/app_name/core/ subdirectory
    - Core modules provide service interfaces, not business logic
    - Communication via: Database queues, Event bus, REST APIs

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Check package imports for app dependencies
    packages_dir = project_root / "packages"
    if packages_dir.exists():
        for package_dir in packages_dir.iterdir():
            if package_dir.is_dir() and not package_dir.name.startswith("."):
                package_name = package_dir.name

                for py_file in package_dir.rglob("*.py"):
                    # File-level scoping optimization
                    if not _should_validate_file(py_file, scope_files):
                        continue

                    if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                        continue

                    try:
                        with open(py_file, encoding="utf-8") as f:
                            content = f.read()

                        # Check for imports from apps (always forbidden for packages)
                        # But skip if it's just a string literal (like in this validator itself)
                        app_imports = [
                            "from ai_planner",
                            "from ai_reviewer",
                            "from hive_orchestrator",
                            "from EcoSystemiser",
                            "from Systemiser",
                            "from event_dashboard",
                        ]

                        for app_import in app_imports:
                            # Check if it's an actual import line, not just a string
                            if app_import in content:
                                # Verify it's at the start of a line (actual import)
                                for line in content.split("\n"):
                                    if line.strip().startswith(app_import):
                                        violations.append(
                                            f"Package '{package_name}' imports from app: {py_file.relative_to(project_root)}",
                                        )
                                        break

                    except Exception:
                        continue

    # Check apps for direct app-to-app dependencies
    apps_dir = project_root / "apps"
    if apps_dir.exists():
        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                app_name = app_dir.name

                for py_file in app_dir.rglob("*.py"):
                    # File-level scoping optimization
                    if not _should_validate_file(py_file, scope_files):
                        continue

                    if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                        continue

                    try:
                        with open(py_file, encoding="utf-8") as f:
                            content = f.read()

                        # Get list of other apps
                        other_apps = [
                            d.name
                            for d in apps_dir.iterdir()
                            if d.is_dir() and d.name != app_name and not d.name.startswith(".")
                        ]

                        for other_app in other_apps:
                            # Convert app names to import patterns
                            app_module = other_app.replace("-", "_")
                            import_patterns = [
                                f"from {other_app}",
                                f"import {other_app}",
                                f"from {app_module}",
                                f"import {app_module}",
                            ]

                            for pattern in import_patterns:
                                # Check for actual import statements with word boundaries
                                # Avoid false positives like 'from dataclasses' matching 'from data'
                                import_lines = []
                                for line in content.split("\n"):
                                    line = line.strip()
                                    if line.startswith(pattern):
                                        # Make sure it's a complete module name match
                                        # After the pattern, there should be a space, dot, or nothing
                                        after_pattern = line[len(pattern) :]
                                        if not after_pattern or after_pattern[0] in (" ", ".", "\n"):
                                            import_lines.append(line)

                                if import_lines:
                                    # Check if it's importing from core/ service layer (allowed)
                                    # Look for patterns like "from hive_orchestrator.core" or "from app.core"
                                    core_import_patterns = [f"from {app_module}.core", f"import {app_module}.core"]

                                    is_core_import = any(
                                        core_pattern in content for core_pattern in core_import_patterns
                                    )

                                    # Also check for client/api patterns (allowed)
                                    client_patterns = [".client", ".Client", ".api", ".API"]
                                    is_client = any(cp in content for cp in client_patterns)

                                    if not is_core_import and not is_client:
                                        # Check if any of the import lines are non-core imports
                                        for import_line in import_lines:
                                            if ".core" not in import_line and ".client" not in import_line:
                                                violations.append(
                                                    f"App '{app_name}' directly imports from app '{other_app}' (non-core): {py_file.relative_to(project_root)}",
                                                )
                                                break

                    except Exception:
                        continue

    return len(violations) == 0, violations


def validate_service_layer_discipline(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 10: Service Layer Discipline

    Validate that:
    - Service layers (core/ directories) contain only interfaces
    - No business logic in service layers
    - Service layers are properly documented
    - Service layers expose clear contracts

    Allowed in core/:
    - Service interfaces and abstract base classes
    - Event definitions and data models
    - Database/bus/API service extensions
    - Type definitions and enums

    Forbidden in core/:
    - Business logic implementation
    - Workflow orchestration
    - Domain-specific algorithms
    - Complex processing logic

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Check apps for core/ directories
    apps_dir = project_root / "apps"
    if apps_dir.exists():
        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                app_name = app_dir.name

                # Look for core/ directory in the app
                core_patterns = [
                    app_dir / "src" / app_name.replace("-", "_") / "core",
                    app_dir / "src" / app_name / "core",
                ]

                for core_dir in core_patterns:
                    if core_dir.exists() and core_dir.is_dir():
                        # Check files in core/ for business logic indicators
                        for py_file in core_dir.rglob("*.py"):
                            # File-level scoping optimization
                            if not _should_validate_file(py_file, scope_files):
                                continue

                            if "__pycache__" in str(py_file):
                                continue

                            try:
                                with open(py_file, encoding="utf-8") as f:
                                    content = f.read()

                                # Check for business logic indicators
                                business_logic_indicators = [
                                    "def process_",
                                    "def calculate_",
                                    "def analyze_",
                                    "def generate_",
                                    "def orchestrate_",
                                    "def execute_workflow",
                                    "def run_algorithm",
                                    "# Business logic",
                                    "# TODO: Implement",
                                    "# Algorithm:",
                                ]

                                for indicator in business_logic_indicators:
                                    if indicator in content:
                                        violations.append(
                                            f"Service layer contains business logic: {py_file.relative_to(project_root)}",
                                        )
                                        break

                                # Check if service interfaces are documented
                                if "class " in content:
                                    # Simple check for docstrings on classes
                                    lines = content.split("\n")
                                    for i, line in enumerate(lines):
                                        if line.strip().startswith("class ") and not line.strip().startswith("class _"):
                                            # Check if next line has docstring
                                            if i + 1 < len(lines):
                                                next_line = lines[i + 1].strip()
                                                if not (next_line.startswith('"""') or next_line.startswith("'''")):
                                                    class_name = (line.strip().split()[1].split("(")[0].rstrip(":"),)
                                                    violations.append(
                                                        f"Service class '{class_name}' missing docstring: {py_file.relative_to(project_root)}",
                                                    )

                            except Exception:
                                continue

    return len(violations) == 0, violations


def validate_communication_patterns(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 11: Communication Patterns

    Validate that:
    - Apps use approved communication patterns
    - No synchronous circular dependencies
    - Background processes are properly managed
    - API endpoints follow REST conventions

    Approved patterns:
    - Database queues (async task processing)
    - Event bus (pub/sub messaging)
    - REST APIs (HTTP endpoints)
    - Service layers (core/ imports)

    Forbidden patterns:
    - Direct socket communication between apps
    - Shared memory or files for IPC
    - Undocumented communication channels

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    apps_dir = project_root / "apps"
    if apps_dir.exists():
        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                app_name = app_dir.name

                # Check hive-app.toml for proper daemon configuration
                app_contract = app_dir / "hive-app.toml"
                if app_contract.exists():
                    try:
                        contract = toml.load(app_contract)

                        # Check daemon configurations
                        if "daemons" in contract:
                            for daemon_name, daemon_config in contract["daemons"].items():
                                if "restart_on_failure" not in daemon_config:
                                    violations.append(
                                        f"Daemon '{daemon_name}' in {app_name} missing restart_on_failure setting",
                                    )
                                if "command" not in daemon_config:
                                    violations.append(
                                        f"Daemon '{daemon_name}' in {app_name} missing command specification",
                                    )

                    except Exception:
                        pass

                # Check for forbidden communication patterns
                for py_file in app_dir.rglob("*.py"):
                    # File-level scoping optimization
                    if not _should_validate_file(py_file, scope_files):
                        continue

                    if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                        continue

                    try:
                        with open(py_file, encoding="utf-8") as f:
                            content = f.read()

                        # Check for raw socket usage (forbidden unless in infrastructure)
                        forbidden_patterns = [
                            "socket.socket(",
                            "multiprocessing.Queue(",
                            "multiprocessing.Pipe(",
                            "mmap.mmap(",  # Memory-mapped files,
                            "SharedMemory(",  # Shared memory
                        ]

                        for pattern in forbidden_patterns:
                            if pattern in content:
                                violations.append(
                                    f"Forbidden IPC pattern '{pattern}' found: {py_file.relative_to(project_root)}",
                                )

                    except Exception:
                        continue

    return len(violations) == 0, violations


def validate_interface_contracts(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 7: Interface Contracts

    Validate that:
    - All public APIs have type hints
    - All public functions have docstrings
    - All async functions follow naming convention (suffix _async)

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    for base_dir in [project_root / "apps", project_root / "packages"]:
        if not base_dir.exists():
            continue

        for py_file in base_dir.rglob("*.py"):
            # File-level scoping optimization
            if not _should_validate_file(py_file, scope_files):
                continue

            if (
                ".venv" in str(py_file)
                or "__pycache__" in str(py_file)
                or "test" in str(py_file)
                or "conftest" in str(py_file)
            ):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Parse the AST
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Check public functions (not starting with _)
                    if isinstance(node, ast.FunctionDef):
                        if not node.name.startswith("_"):
                            # Check for docstring
                            if not ast.get_docstring(node):
                                violations.append(
                                    f"Public function '{node.name}' missing docstring: {py_file.relative_to(project_root)}:{node.lineno}",
                                )

                            # Check for type hints on parameters
                            for arg in node.args.args:
                                if arg.arg != "self" and arg.arg != "cls" and not arg.annotation:
                                    violations.append(
                                        f"Parameter '{arg.arg}' missing type hint in '{node.name}': {py_file.relative_to(project_root)}:{node.lineno}",
                                    )

                            # Check for return type hint
                            if not node.returns and node.name != "__init__":
                                violations.append(
                                    f"Function '{node.name}' missing return type hint: {py_file.relative_to(project_root)}:{node.lineno}",
                                )

                    # Check async function naming
                    elif isinstance(node, ast.AsyncFunctionDef):
                        if not node.name.startswith("_") and not node.name.endswith("_async"):
                            violations.append(
                                f"Async function '{node.name}' should end with '_async': {py_file.relative_to(project_root)}:{node.lineno}",
                            )

            except Exception:
                # Skip files that can't be parsed
                continue

    return len(violations) == 0, violations


def validate_error_handling_standards(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 8: Error Handling Standards

    Validate that:
    - All apps use hive-error-handling base classes
    - No bare exceptions in production code
    - All errors include context and recovery strategies

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    for base_dir in [project_root / "apps", project_root / "packages"]:
        if not base_dir.exists():
            continue

        for py_file in base_dir.rglob("*.py"):
            # File-level scoping optimization
            if not _should_validate_file(py_file, scope_files):
                continue

            if ".venv" in str(py_file) or "__pycache__" in str(py_file) or "test" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Check for bare except clauses (except: without any exception type)
                line_num = 0
                for line in content.split("\n"):
                    line_num += 1
                    stripped = line.strip()
                    if stripped == "except:" or (
                        stripped.startswith("except:") and stripped[7:].strip().startswith("#")
                    ):
                        violations.append(f"Bare except clause found: {py_file.relative_to(project_root)}:{line_num}")

                # Parse AST for more detailed checks
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        # Check if exception is re-raised or properly handled
                        if node.type is None:  # bare except
                            violations.append(
                                f"Bare except without type: {py_file.relative_to(project_root)}:{node.lineno}",
                            )

            except Exception:
                # Skip files that can't be parsed
                continue

    return len(violations) == 0, violations


def validate_no_hardcoded_env_values(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Validate that packages don't contain hardcoded environment-specific values.

    Ensures:
    - No hardcoded server paths, usernames, or hostnames in generic packages
    - Deployment configuration uses environment variables or configuration files
    - Generic packages remain environment-agnostic
    - Prevents coupling between infrastructure code and specific deployment environments

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Focus on packages directory - these should be environment-agnostic
    packages_dir = project_root / "packages"
    if not packages_dir.exists():
        return True, violations

    # Hardcoded values that indicate environment coupling
    hardcoded_patterns = [
        # Server paths that should be configurable
        (r"/home/smarthoo[^/]*", "hardcoded user home directory"),
        (r"/home/deploy[^/]*", "hardcoded deployment user directory"),
        (r"/etc/nginx/conf\.d", "hardcoded nginx config directory"),
        (r"/etc/systemd/system", "hardcoded systemd directory"),
        # Hostnames and domains
        (r"tasks\.smarthoods\.eco", "hardcoded hostname"),
        (r"smarthoods\.eco", "hardcoded domain name"),
        # User accounts
        (r'"smarthoo"', "hardcoded username"),
        (r"'smarthoo'", "hardcoded username"),
        (r'"www-data"', "hardcoded user group"),
        (r"'www-data'", "hardcoded user group"),
        # Base directory constants (should use env vars)
        (r'BASE_REMOTE_APPS_DIR\s*=\s*["\']/', "hardcoded base directory assignment"),
    ]

    for package_dir in packages_dir.iterdir():
        if not package_dir.is_dir() or package_dir.name.startswith("."):
            continue

        for py_file in package_dir.rglob("*.py"):
            # Skip test files, __pycache__, and virtual environments
            # File-level scoping optimization
            if not _should_validate_file(py_file, scope_files):
                continue

            if any(skip in str(py_file) for skip in ["test", "__pycache__", ".venv", ".pytest_cache"]):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Check each hardcoded pattern
                import re

                for pattern, description in hardcoded_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        # Find line number for better error reporting
                        line_num = content[: match.start()].count("\n") + 1

                        # Get surrounding context to detect os.environ.get() usage
                        lines = content.split("\n")
                        context_lines = []
                        for i in range(max(0, line_num - 3), min(len(lines), line_num + 2)):
                            context_lines.append(lines[i])
                        context = "\n".join(context_lines)

                        # Skip if this is a default value in os.environ.get() - this is proper configuration pattern
                        if "os.environ.get(" in context and match.group() in context:
                            continue

                        violations.append(
                            f"Hardcoded environment value ({description}): ",
                            f"{py_file.relative_to(project_root)}:{line_num} ",
                            f"- Found: {match.group()}",
                        )

            except Exception:
                # Skip files that can't be read
                continue

    return len(violations) == 0, violations


def validate_logging_standards(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 9: Logging Standards

    Validate that:
    - All components use hive-logging
    - No print statements in production code
    - Structured logging with appropriate levels

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    for base_dir in [project_root / "apps", project_root / "packages"]:
        if not base_dir.exists():
            continue

        for py_file in base_dir.rglob("*.py"):
            # File-level scoping optimization
            if not _should_validate_file(py_file, scope_files):
                continue

            if (
                ".venv" in str(py_file)
                or "__pycache__" in str(py_file)
                or "test" in str(py_file)
                or "example" in str(py_file)
                or "demo" in str(py_file)
                or "script" in str(py_file)
                or "benchmark" in str(py_file)
                or "__main__" in str(py_file.name)
                or "hive_status.py" in str(py_file)
                or "cli.py" in str(py_file)
                or "app.py" in str(py_file)  # Dashboard and CLI apps
            ):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                # Check for print statements in non-test, non-demo files
                if "logger.info(" in content:
                    # Check if this file is a CLI tool or has __main__ section
                    is_cli_tool = (
                        'if __name__ == "__main__":' in content
                        or "def main(" in content
                        or "secure_config.py" in str(py_file)
                        or "cli.py" in str(py_file)
                        or "command" in str(py_file)
                    )

                    line_num = 0
                    in_main_section = False
                    for line in content.split("\n"):
                        line_num += 1

                        # Track if we're in the __main__ section or CLI utility functions
                        if (
                            'if __name__ == "__main__":' in line
                            or "def encrypt_production_config(" in line
                            or "def generate_master_key(" in line
                        ):
                            in_main_section = True
                            continue

                        # Check for actual print() statements, not logger.info()!
                        if "print(" in line and not line.strip().startswith("#"):
                            stripped_line = line.strip()
                            # Skip if print( is inside a string
                            if '"print(' in line or "'print(" in line:
                                continue
                            # Skip if it's inside a multiline string (contains = and quotes)
                            if '="' in line and "print(" in line.split('="')[1]:
                                continue
                            # Skip if line starts with + or - (likely a diff)
                            if stripped_line.startswith(("+", "-")):
                                continue
                            if (
                                not stripped_line.startswith("from ")
                                and not stripped_line.startswith("import ")
                                and not stripped_line.startswith("#")
                                and not stripped_line.startswith('"')
                                and not stripped_line.startswith("'")
                                and not (is_cli_tool and in_main_section)
                            ):
                                violations.append(
                                    f"Print statement in production code: {py_file.relative_to(project_root)}:{line_num}",
                                )

                # Check if file actually uses logging (not just mentions it in comments)
                uses_logging = (
                    "logger." in content or "logging." in content or "getLogger(" in content or "get_logger(" in content
                )
                if uses_logging:
                    # Check for various valid hive_logging import patterns
                    has_hive_logging = (
                        "from hive_logging import" in content
                        or "import hive_logging" in content
                        or "from EcoSystemiser.hive_logging_adapter import" in content
                        or "from .hive_logging_adapter import" in content
                        or "hive_logging_adapter" in content
                    )

                    if not has_hive_logging:
                        # Allow standard logging ONLY in core logging infrastructure
                        # Check if this is the hive-logging package itself
                        is_logging_infrastructure = False
                        for part in py_file.parts:
                            if part in ["hive-logging"]:
                                is_logging_infrastructure = True
                                break

                        if not is_logging_infrastructure:
                            violations.append(
                                f"Uses logging but doesn't import hive_logging: {py_file.relative_to(project_root)}",
                            )

                # Check for direct import logging violations (stricter enforcement)
                if "import logging" in content and not content.startswith('"""') and "# type: ignore" not in content:
                    # Only allow import logging in hive-logging package itself
                    is_logging_infrastructure = False
                    for part in py_file.parts:
                        if part in ["hive-logging"]:
                            is_logging_infrastructure = True
                            break

                    if not is_logging_infrastructure:
                        line_num = 0
                        for line in content.split("\n"):
                            line_num += 1
                            if "import logging" in line and not line.strip().startswith("#"):
                                violations.append(
                                    f"Direct 'import logging' found (use hive_logging): {py_file.relative_to(project_root)}:{line_num}",
                                )

            except Exception:
                # Skip files that can't be read
                continue

    return len(violations) == 0, violations


def validate_inherit_extend_pattern(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 10: Inherit → Extend Pattern

    Validate that:
    - All apps with core modules properly extend base packages
    - Core module naming matches package naming (e.g., errors.py not error.py)
    - All extended modules import from the base package first

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Define the expected core module patterns
    expected_patterns = {
        "errors": "hive_errors",  # Should have errors.py extending hive_errors,
        "bus": "hive_bus",  # Should have bus.py extending hive_bus,
        "db": "hive_db",  # Should have db.py extending hive_db
    }

    apps_dir = project_root / "apps"
    if not apps_dir.exists():
        return False, ["apps/ directory does not exist"]

    for app_dir in apps_dir.iterdir():
        if app_dir.is_dir() and not app_dir.name.startswith(".") and app_dir.name != "legacy":
            app_name = app_dir.name

            # Find the app's source directory
            src_dirs = list(app_dir.glob("src/*/core"))
            if not src_dirs:
                continue

            core_dir = src_dirs[0]

            # Check each expected pattern
            for module_name, base_package in expected_patterns.items():
                module_file = core_dir / f"{module_name}.py"
                module_dir = core_dir / module_name

                # If the module exists (either as file or directory)
                if module_file.exists() or module_dir.exists():
                    # Check that it imports from the base package
                    check_file = module_file if module_file.exists() else (module_dir / "__init__.py")

                    if check_file.exists():
                        try:
                            with open(check_file, encoding="utf-8") as f:
                                content = f.read()

                            # Check for proper import
                            if f"from {base_package}" not in content and f"import {base_package}" not in content:
                                violations.append(
                                    f"App '{app_name}' core/{module_name} doesn't import from {base_package}",
                                )
                        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
                            logger.debug(f"Cannot read file {check_file}: {e}")
                            continue
                        except Exception as e:
                            logger.warning(f"Unexpected error reading {check_file}: {e}")
                            continue

            # Check for incorrect naming (error.py instead of errors.py)
            incorrect_names = {"error.py": "errors.py", "messaging.py": "bus.py", "database.py": "db.py"}

            for incorrect, correct in incorrect_names.items():
                if (core_dir / incorrect).exists():
                    violations.append(f"App '{app_name}' has core/{incorrect}, should be core/{correct}")

    return len(violations) == 0, violations


def validate_package_naming_consistency(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 12: Package Naming Consistency

    Validate that package names, directory names, and module names
    are consistent across the workspace.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []
    packages_dir = project_root / "packages"

    if not packages_dir.exists():
        return True, []  # No packages to validate

    for package_dir in packages_dir.iterdir():
        if not package_dir.is_dir() or package_dir.name.startswith("."):
            continue

        package_name = package_dir.name
        pyproject_file = package_dir / "pyproject.toml"

        if not pyproject_file.exists():
            violations.append(f"Package '{package_name}' missing pyproject.toml")
            continue

        try:
            pyproject = toml.load(pyproject_file)

            # Check that package name in pyproject.toml matches directory name
            declared_name = pyproject.get("tool", {}).get("poetry", {}).get("name", "")
            if declared_name != package_name:
                violations.append(
                    f"Package '{package_name}' directory name doesn't match pyproject.toml name '{declared_name}'",
                )

            # Check that source directory matches package name (with underscores)
            expected_src_name = package_name.replace("-", "_")
            src_dir = package_dir / "src" / expected_src_name
            if not src_dir.exists():
                violations.append(f"Package '{package_name}' missing expected src directory 'src/{expected_src_name}'")

        except Exception as e:
            violations.append(f"Package '{package_name}' has malformed pyproject.toml: {e}")

    return len(violations) == 0, violations


def validate_development_tools_consistency(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 13: Development Tools Consistency

    Validate that all packages and apps use standardized versions
    of development tools (pytest, black, mypy, ruff, isort).

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Standard tool versions
    standard_versions = {
        "pytest": "^8.3.2",
        "black": "^24.8.0",
        "mypy": "^1.8.0",
        "ruff": "^0.1.15",
        "isort": "^5.13.0",
    }

    # Check all pyproject.toml files
    for pyproject_file in project_root.rglob("pyproject.toml"):
        # Skip virtual environment and hidden directories
        if ".venv" in str(pyproject_file) or "/.git/" in str(pyproject_file):
            continue

        try:
            pyproject = toml.load(pyproject_file)
            dev_deps = (
                pyproject.get("tool", {}).get("poetry", {}).get("group", {}).get("dev", {}).get("dependencies", {})
            )

            # Check each standard tool if it exists
            for tool, expected_version in standard_versions.items():
                if tool in dev_deps:
                    actual_version = dev_deps[tool]
                    if actual_version != expected_version and actual_version != "*":
                        rel_path = pyproject_file.relative_to(project_root)
                        violations.append(
                            f"{rel_path}: {tool} version '{actual_version}' should be '{expected_version}'",
                        )

        except Exception as e:
            rel_path = pyproject_file.relative_to(project_root)
            violations.append(f"{rel_path}: Failed to parse pyproject.toml: {e}")

    return len(violations) == 0, violations


def validate_async_pattern_consistency(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 14: Async Pattern Consistency

    Validate that async code follows consistent patterns:
    - Use hive-async utilities for common patterns
    - Proper async context managers
    - Consistent error handling in async code

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Find Python files that use async
    for py_file in project_root.rglob("*.py"):
        # Skip virtual environment and hidden directories
        # File-level scoping optimization
        if not _should_validate_file(py_file, scope_files):
            continue

        if ".venv" in str(py_file) or "/.git/" in str(py_file):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                # Check for async functions
                if isinstance(node, ast.AsyncFunctionDef):
                    rel_path = py_file.relative_to(project_root)

                    # Look for connection pool patterns that should use hive-async
                    if "connection" in node.name.lower() and "pool" in node.name.lower():
                        # Check if hive_async is imported
                        has_hive_async_import = any(
                            isinstance(n, ast.ImportFrom) and n.module and "hive_async" in n.module
                            for n in ast.walk(tree)
                        )
                        if not has_hive_async_import:
                            violations.append(f"{rel_path}: Async connection handling should use hive-async utilities")

        except (UnicodeDecodeError, SyntaxError) as e:
            # Skip files that can't be parsed (binary files, syntax errors)
            logger.debug(f"Cannot parse file {py_file}: {e}")
            continue
        except Exception as e:
            # Skip other parsing errors
            logger.warning(f"Unexpected error parsing {py_file}: {e}")
            continue

    return len(violations) == 0, violations


def validate_cli_pattern_consistency(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 15: CLI Pattern Consistency

    Validate that CLI implementations use standardized patterns:
    - Use hive-cli base classes and utilities
    - Consistent output formatting with Rich
    - Proper error handling and validation

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Find CLI-related files
    cli_files = []
    for py_file in project_root.rglob("*.py"):
        # Skip virtual environment and hidden directories
        # File-level scoping optimization
        if not _should_validate_file(py_file, scope_files):
            continue

        if ".venv" in str(py_file) or "/.git/" in str(py_file):
            continue

        if "cli" in py_file.name or py_file.name == "__main__.py":
            cli_files.append(py_file)

    for cli_file in cli_files:
        try:
            with open(cli_file, encoding="utf-8") as f:
                content = f.read()

            rel_path = cli_file.relative_to(project_root)

            # Check for Click usage without hive-cli
            if "import click" in content and "from hive_cli" not in content:
                # Look for complex CLI patterns that should use hive-cli
                if any(pattern in content for pattern in ["@click.group", "@click.command", "click.echo"]):
                    violations.append(f"{rel_path}: CLI should use hive-cli utilities for consistency")

        except (UnicodeDecodeError, SyntaxError) as e:
            # Skip files that can't be parsed
            logger.debug(f"Cannot parse CLI file {cli_file}: {e}")
            continue
        except Exception as e:
            # Skip other parsing errors
            logger.warning(f"Unexpected error parsing CLI file {cli_file}: {e}")
            continue

    return len(violations) == 0, violations


def validate_no_global_state_access(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 16: No Global State Access

    Validate that no global state access patterns exist in the codebase.
    All configuration should be injected via dependency injection.

    Forbidden patterns:
    - Global configuration singletons
    - Direct os.getenv() calls outside config modules
    - Module-level state variables
    - Singleton pattern implementations
    - DI fallback anti-patterns (config=None, if config is None:)

    Allowed patterns:
    - Configuration passed via function parameters
    - Environment variable access in config loading functions
    - Constants and immutable module-level data

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []
    base_dirs = [project_root / "apps", project_root / "packages"]

    for base_dir in base_dirs:
        if not base_dir.exists():
            continue

        for py_file in base_dir.rglob("*.py"):
            # Skip test files, __pycache__, virtual environments, and config modules
            # File-level scoping optimization
            if not _should_validate_file(py_file, scope_files):
                continue

            if any(
                skip in str(py_file)
                for skip in [
                    "test",
                    "__pycache__",
                    ".venv",
                    ".pytest_cache",
                    "architectural_validators.py",  # Skip self
                ]
            ):
                continue

            # Allow os.getenv in specific config-related files
            config_related_files = [
                "unified_config.py",
                "config.py",
                "settings.py",
                "environment.py",
                "loader.py",
                "paths.py",
            ]
            is_config_file = any(config_file in py_file.name for config_file in config_related_files)

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                rel_path = py_file.relative_to(project_root)

                # Check for global singleton patterns
                singleton_patterns = [
                    "_instance",
                    "_config_instance",
                    "_global_config",
                    "_singleton",
                    "global_instance",
                    "_cache_instance",
                    "_database_manager",
                    "_async_database_manager",
                    "_db_manager",
                    "_connection_pool",
                    "_pool_manager",
                    "_client_instance",
                    "_service_instance",
                ]

                for pattern in singleton_patterns:
                    if pattern in content:
                        # Verify it's actually a global variable declaration, not in strings
                        lines = content.split("\n")
                        in_multiline_string = False
                        for line_num, line in enumerate(lines, 1):
                            stripped = line.strip()

                            # Skip content inside multiline strings (triple quotes)
                            if '"""' in stripped or "'''" in stripped:
                                in_multiline_string = not in_multiline_string
                                continue
                            if in_multiline_string:
                                continue

                            # Skip if pattern is inside a string literal
                            if (
                                f'"{pattern}"' in stripped
                                or f"'{pattern}'" in stripped
                                or f'"{pattern}' in stripped
                                or f"'{pattern}" in stripped
                            ):
                                continue

                            if (
                                stripped.startswith(f"{pattern}:")
                                or stripped.startswith(f"{pattern} =")
                                or f"global {pattern}" in stripped
                            ):
                                violations.append(f"Global singleton pattern '{pattern}' found: {rel_path}:{line_num}")

                # Check for direct os.getenv() calls outside config modules
                if not is_config_file and "os.getenv(" in content:
                    lines = content.split("\n")
                    for line_num, line in enumerate(lines, 1):
                        if "os.getenv(" in line and not line.strip().startswith("#"):
                            violations.append(f"Direct os.getenv() call outside config module: {rel_path}:{line_num}")

                # Check for global load_config() and get_config() calls
                forbidden_global_calls = ["load_config()", "get_config()", "reset_config()"]

                for call in forbidden_global_calls:
                    if call in content:
                        lines = content.split("\n")
                        in_multiline_string = False
                        for line_num, line in enumerate(lines, 1):
                            stripped = line.strip()

                            # Skip content inside multiline strings (triple quotes)
                            if '"""' in stripped or "'''" in stripped:
                                in_multiline_string = not in_multiline_string
                                continue
                            if in_multiline_string:
                                continue

                            # Skip comments and string literals containing the call
                            if stripped.startswith("#") or f'"{call}"' in stripped or f"'{call}'" in stripped:
                                continue

                            if call in line:
                                violations.append(f"Global config call '{call}' found: {rel_path}:{line_num}")

                # Check for singleton getter functions (common anti-pattern)
                singleton_getter_patterns = [
                    "get_database_manager()",
                    "get_async_database_manager()",
                    "get_db_manager()",
                    "get_connection_pool()",
                    "get_async_pool()",
                    "get_client_instance()",
                    "get_service_instance()",
                    "get_singleton()",
                ]

                for getter in singleton_getter_patterns:
                    if getter in content:
                        lines = content.split("\n")
                        for line_num, line in enumerate(lines, 1):
                            if getter in line and not line.strip().startswith("#"):
                                # Skip if this is defining the function itself
                                if not line.strip().startswith("def "):
                                    violations.append(f"Singleton getter call '{getter}' found: {rel_path}:{line_num}")

                # Check for DI fallback anti-patterns
                if "def __init__(" in content:
                    lines = content.split("\n")
                    for line_num, line in enumerate(lines, 1):
                        line_stripped = line.strip()

                        # Detect DI fallback pattern: def __init__(self, config=None):
                        # Be more precise - only detect actual config parameter defaults, not rate_config, etc.
                        if line_stripped.startswith("def __init__(") and (
                            ", config=None" in line_stripped or "(config=None" in line_stripped
                        ):
                            violations.append(f"DI fallback anti-pattern 'config=None' found: {rel_path}:{line_num}")

                        # Detect other common fallback patterns
                        fallback_patterns = ["settings=None", "configuration=None", "options=None"]
                        for pattern in fallback_patterns:
                            if line_stripped.startswith("def __init__(") and pattern in line_stripped:
                                violations.append(f"DI fallback anti-pattern '{pattern}' found: {rel_path}:{line_num}")

                # Check for fallback blocks in __init__ methods
                if "if config is None:" in content or "if settings is None:" in content:
                    lines = content.split("\n")
                    for line_num, line in enumerate(lines, 1):
                        line_stripped = line.strip()
                        fallback_checks = [
                            "if config is None:",
                            "if settings is None:",
                            "if configuration is None:",
                            "if options is None:",
                        ]
                        for check in fallback_checks:
                            if check in line_stripped:
                                violations.append(f"DI fallback block '{check}' found: {rel_path}:{line_num}")

                # Check for singleton class patterns
                if "class " in content:
                    lines = content.split("\n")
                    for line_num, line in enumerate(lines, 1):
                        if "class " in line and any(
                            pattern in line.lower() for pattern in ["singleton", "_instance", "metaclass"]
                        ):
                            violations.append(f"Singleton class pattern found: {rel_path}:{line_num}")

            except Exception:
                # Skip files that can't be read
                continue

    return len(violations) == 0, violations


def _uses_comprehensive_testing(package_dir: Path) -> bool:
    """Check if package uses comprehensive testing strategy (ADR-005)."""
    tests_dir = package_dir / "tests"
    if not tests_dir.exists():
        return False

    # Look for comprehensive testing indicators
    indicators = [
        tests_dir / "property_based",  # Property-based testing directory,
        tests_dir / "integration",  # Integration testing directory
    ]

    # Check for Hypothesis usage (property-based testing)
    for py_file in tests_dir.rglob("*.py"):
        # File-level scoping optimization
        if not _should_validate_file(py_file, scope_files):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                if "hypothesis" in content.lower() or "@given" in content:
                    return True
        except:
            continue

    # Check for comprehensive testing directories
    return any(indicator.exists() and indicator.is_dir() for indicator in indicators)


def _validate_comprehensive_testing(package_dir: Path, package_name: str) -> list[str]:
    """Validate comprehensive testing package (ADR-005)."""
    violations = []
    tests_dir = package_dir / "tests"

    # Check for minimum comprehensive testing requirements
    required_dirs = ["integration", "property_based"]
    existing_dirs = []

    for dir_name in required_dirs:
        test_subdir = tests_dir / dir_name
        if test_subdir.exists() and test_subdir.is_dir():
            existing_dirs.append(dir_name)

    # For comprehensive testing packages, require at least one advanced testing approach
    if not existing_dirs:
        violations.append(
            f"Package '{package_name}' uses comprehensive testing but lacks property_based/ ",
            "or integration/ test directories",
        )

    # Check for property-based testing quality
    if "property_based" in existing_dirs:
        property_dir = tests_dir / "property_based"
        has_hypothesis = False
        for py_file in property_dir.rglob("*.py"):
            # File-level scoping optimization
            if not _should_validate_file(py_file, scope_files):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                    if "hypothesis" in content.lower() and "@given" in content:
                        has_hypothesis = True
                        break
            except:
                continue

        if not has_hypothesis:
            violations.append(f"Package '{package_name}' has property_based/ directory but no Hypothesis tests found")

    # Check for integration test quality
    if "integration" in existing_dirs:
        integration_dir = tests_dir / "integration"
        py_files = list(integration_dir.rglob("*.py"))
        if len(py_files) == 0:
            violations.append(f"Package '{package_name}' has integration/ directory but no test files")

    return violations


def validate_test_coverage_mapping(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 17: Test-to-Source File Mapping

    Enforces 1:1 mapping between source files and unit test files to ensure
    comprehensive test coverage and maintainability.

    Rules:
    1. Every .py file in src/ should have a corresponding test file
    2. Test files should follow naming convention: test_<module_name>.py
    3. Test files should be in tests/unit/ directory relative to package
    4. Core modules must have unit tests (integration tests are separate)

    Args:
        project_root: Root directory of the project

    Returns:
        Tuple of (all_passed, violations_list)
    """
    violations = []

    # Find all packages with source code
    packages_dir = project_root / "packages"
    if not packages_dir.exists():
        return True, []  # No packages to validate

    for package_dir in packages_dir.iterdir():
        if not package_dir.is_dir() or package_dir.name.startswith("."):
            continue

        package_name = package_dir.name

        # Check if this package uses comprehensive testing (ADR-005)
        if _uses_comprehensive_testing(package_dir):
            # Apply comprehensive testing validation
            comprehensive_violations = _validate_comprehensive_testing(package_dir, package_name)
            violations.extend(comprehensive_violations)
            continue

        # Find src directory
        src_dir = package_dir / "src"
        if not src_dir.exists():
            continue

        # Find tests directory
        tests_dir = package_dir / "tests"
        unit_tests_dir = tests_dir / "unit" if tests_dir.exists() else None

        # Collect all Python source files
        source_files = []
        for py_file in src_dir.rglob("*.py"):
            # Skip __init__.py files and __pycache__
            # File-level scoping optimization
            if not _should_validate_file(py_file, scope_files):
                continue

            if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
                continue

            # Get relative path from src directory
            rel_path = py_file.relative_to(src_dir)
            source_files.append(rel_path)

        # Check for corresponding test files
        for src_file in source_files:
            package_name = package_dir.name

            # Convert source file path to expected test file path
            # e.g., hive_config/loader.py -> test_loader.py
            module_parts = src_file.with_suffix("").parts
            if len(module_parts) > 1:
                # Skip package namespace files for now (complex mapping)
                test_file_name = f"test_{'_'.join(module_parts[1:])}.py"
            else:
                test_file_name = f"test_{module_parts[0]}.py"

            # Check if test file exists
            test_file_found = False

            if unit_tests_dir and unit_tests_dir.exists():
                expected_test_path = unit_tests_dir / test_file_name
                if expected_test_path.exists():
                    test_file_found = True

            # Also check in tests directory directly (fallback)
            if not test_file_found and tests_dir and tests_dir.exists():
                fallback_test_path = tests_dir / test_file_name
                if fallback_test_path.exists():
                    test_file_found = True

            if not test_file_found:
                violations.append(
                    f"Missing test file for {package_name}:{src_file} - ",
                    f"expected {test_file_name} in tests/unit/ or tests/",
                )

    # Also check apps for core modules (optional but recommended)
    apps_dir = project_root / "apps"
    if apps_dir.exists():
        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir() or app_dir.name.startswith("."):
                continue

            # Look for core modules that should have tests
            core_dir = app_dir / "src" / app_dir.name / "core"
            if core_dir.exists():
                tests_dir = app_dir / "tests"

                for py_file in core_dir.rglob("*.py"):
                    # File-level scoping optimization
                    if not _should_validate_file(py_file, scope_files):
                        continue

                    if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
                        continue

                    # Core modules should have tests (business logic)
                    rel_path = py_file.relative_to(core_dir)
                    test_file_name = f"test_{rel_path.stem}.py"

                    test_exists = False
                    if tests_dir.exists():
                        for test_file in tests_dir.rglob(test_file_name):
                            test_exists = True
                            break

                    if not test_exists:
                        violations.append(
                            f"Missing test for core module {app_dir.name}:core/{rel_path} - ",
                            "core business logic should have unit tests",
                        )

    return len(violations) == 0, violations


def validate_test_file_quality(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 18: Test File Quality Standards

    Ensures test files follow quality standards and actually test the code.

    Rules:
    1. Test files should contain actual test functions (not just imports)
    2. Test classes should follow naming convention TestClassName
    3. Test functions should follow naming convention test_function_name
    4. Test files should import the modules they test

    Args:
        project_root: Root directory of the project

    Returns:
        Tuple of (all_passed, violations_list)
    """
    violations = []

    # Find all test files
    test_files = []
    for test_dir in ["tests", "test"]:
        for root in [project_root / "packages", project_root / "apps"]:
            if root.exists():
                for test_file in root.rglob(f"{test_dir}/**/*.py"):
                    if test_file.name.startswith("test_") and test_file.name.endswith(".py"):
                        test_files.append(test_file)

    for test_file in test_files:
        try:
            with open(test_file, encoding="utf-8") as f:
                content = f.read()

            # Check if file has actual test functions
            has_test_functions = False
            has_test_classes = False

            lines = content.split("\n")
            for line in lines:
                stripped = line.strip()

                # Check for test functions
                if stripped.startswith("def test_"):
                    has_test_functions = True

                # Check for test classes
                if stripped.startswith("class Test") and ":" in stripped:
                    has_test_classes = True

            # Test file should have either test functions or test classes
            if not has_test_functions and not has_test_classes:
                violations.append(
                    f"Test file {test_file.relative_to(project_root)} contains no test functions or test classes",
                )

            # Check for imports (test files should import something)
            if "import " not in content and "from " not in content:
                violations.append(f"Test file {test_file.relative_to(project_root)} contains no import statements")

        except Exception as e:
            violations.append(f"Failed to analyze test file {test_file.relative_to(project_root)}: {e}")

    return len(violations) == 0, violations


def validate_pyproject_dependency_usage(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 19: PyProject Dependency Usage Validation

    Validate that all packages declared in pyproject.toml dependencies
    are actually imported and used in the application code.

    This prevents dependency bloat and ensures clean package management.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Check all apps and packages
    for base_dir_name in ["apps", "packages"]:
        base_dir = project_root / base_dir_name
        if not base_dir.exists():
            continue

        for component_dir in base_dir.iterdir():
            if not component_dir.is_dir() or component_dir.name.startswith("."):
                continue

            pyproject_file = component_dir / "pyproject.toml"
            if not pyproject_file.exists():
                continue

            try:
                # Parse pyproject.toml
                config = toml.load(pyproject_file)
                dependencies = set()

                # Extract dependencies from [tool.poetry.dependencies]
                if "tool" in config and "poetry" in config["tool"]:
                    if "dependencies" in config["tool"]["poetry"]:
                        for dep_name, dep_config in config["tool"]["poetry"]["dependencies"].items():
                            if dep_name != "python":  # Skip python version
                                # Handle both string and dict dependency formats
                                if isinstance(dep_config, dict):
                                    # Local path dependencies
                                    if "path" in dep_config:
                                        # Extract package name from path
                                        dep_name = dep_name.replace("-", "_")
                                dependencies.add(dep_name)

                # Find all Python source files
                src_dir = component_dir / "src"
                python_files = []

                if src_dir.exists():
                    python_files = list(src_dir.rglob("*.py"))
                else:
                    # Fallback to checking the component directory
                    python_files = list(component_dir.rglob("*.py"))

                # Extract all imports from Python files
                imported_packages = set()
                for py_file in python_files:
                    try:
                        with open(py_file, encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        # Parse AST to find imports
                        tree = ast.parse(content, filename=str(py_file))

                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    # Get top-level package name
                                    package_name = alias.name.split(".")[0]
                                    imported_packages.add(package_name)

                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    # Get top-level package name
                                    package_name = node.module.split(".")[0]
                                    imported_packages.add(package_name)

                    except (SyntaxError, UnicodeDecodeError, PermissionError):
                        # Skip files with syntax errors or encoding issues
                        continue
                    except Exception as e:
                        logger.warning(f"Error analyzing {py_file}: {e}")
                        continue

                # Check for unused dependencies
                unused_deps = dependencies - imported_packages

                # Filter out common exceptions that might not be directly imported
                exceptions = {
                    "click",  # CLI tool, might be used via decorators,
                    "uvicorn",  # Server runner,
                    "pytest",  # Test framework,
                    "black",  # Code formatter,
                    "mypy",  # Type checker,
                    "ruff",  # Linter,
                    "isort",  # Import sorter
                }

                unused_deps = unused_deps - exceptions

                # Report violations
                component_name = f"{base_dir_name}/{component_dir.name}"
                for unused_dep in unused_deps:
                    violations.append(
                        f"{component_name}: Unused dependency '{unused_dep}' declared in pyproject.toml but not imported in code",
                    )

            except Exception as e:
                logger.warning(f"Error validating {component_dir}/pyproject.toml: {e}")

    return len(violations) == 0, violations


def validate_unified_tool_configuration(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 21: Unified Tool Configuration

    Enforces that all tool configurations (ruff, black, mypy, isort) are centralized
    in the root pyproject.toml. Sub-packages should NOT define their own tool configs.

    This prevents the config fragmentation that causes AI agents to generate
    inconsistent code and systematic syntax errors.

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # Check for forbidden tool sections in sub-package pyproject.toml files
    forbidden_sections = ["tool.ruff", "tool.black", "tool.mypy", "tool.isort"]

    for toml_path in project_root.rglob("pyproject.toml"):
        # Skip root pyproject.toml
        if toml_path == project_root / "pyproject.toml":
            continue

        # Skip venv and archive
        if ".venv" in str(toml_path) or "archive" in str(toml_path):
            continue

        try:
            config = toml.load(toml_path)

            # Check for forbidden tool sections
            if "tool" in config:
                for tool_name in ["ruff", "black", "mypy", "isort"]:
                    if tool_name in config["tool"]:
                        rel_path = toml_path.relative_to(project_root)
                        violations.append(
                            f"{rel_path} contains [tool.{tool_name}] section - "
                            f"tool configs must be unified in root pyproject.toml",
                        )
        except Exception as e:
            violations.append(f"Error reading {toml_path}: {e}")

    # Verify root pyproject.toml has the required sections
    root_toml = project_root / "pyproject.toml"
    if root_toml.exists():
        try:
            root_config = toml.load(root_toml)
            if "tool" not in root_config or "ruff" not in root_config["tool"]:
                violations.append("Root pyproject.toml missing [tool.ruff] configuration")
        except Exception as e:
            violations.append(f"Error reading root pyproject.toml: {e}")
    else:
        violations.append("Root pyproject.toml does not exist")

    return len(violations) == 0, violations


def validate_python_version_consistency(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, list[str]]:
    """
    Golden Rule 22: Python Version Consistency

    Enforces that ALL pyproject.toml files require the same Python version (3.11+).
    This prevents version drift that causes syntax incompatibilities and comma errors.

    The Python 3.10→3.11 migration revealed that version inconsistencies cause:
    - Different syntax parsing strictness
    - Comma-related syntax errors
    - Tool behavior differences (Ruff, Black)

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []
    expected_python_version = "3.11"

    root_toml = project_root / "pyproject.toml"
    root_python_version = None

    # Check root pyproject.toml for Python version
    if root_toml.exists():
        try:
            root_config = toml.load(root_toml)

            # Check for Python version in tool.poetry.dependencies or project.requires-python
            if "tool" in root_config and "poetry" in root_config["tool"]:
                deps = root_config["tool"]["poetry"].get("dependencies", {})
                if "python" in deps:
                    root_python_version = deps["python"]
            elif "project" in root_config:
                root_python_version = root_config["project"].get("requires-python")

            if not root_python_version:
                violations.append("Root pyproject.toml missing Python version requirement")
            elif expected_python_version not in str(root_python_version):
                violations.append(
                    f"Root pyproject.toml Python version '{root_python_version}' "
                    f"must require {expected_python_version}+",
                )
        except Exception as e:
            violations.append(f"Error reading root pyproject.toml: {e}")
    else:
        violations.append("Root pyproject.toml does not exist")

    # Check all sub-project pyproject.toml files
    for toml_path in project_root.rglob("pyproject.toml"):
        # Skip root
        if toml_path == root_toml:
            continue

        # Skip venv and archive
        if ".venv" in str(toml_path) or "archive" in str(toml_path):
            continue

        try:
            config = toml.load(toml_path)
            python_version = None

            # Check for Python version
            if "tool" in config and "poetry" in config["tool"]:
                deps = config["tool"]["poetry"].get("dependencies", {})
                if "python" in deps:
                    python_version = deps["python"]
            elif "project" in config:
                python_version = config["project"].get("requires-python")

            if not python_version:
                rel_path = toml_path.relative_to(project_root)
                violations.append(f"{rel_path} missing Python version requirement")
            elif expected_python_version not in str(python_version):
                rel_path = toml_path.relative_to(project_root)
                violations.append(
                    f"{rel_path} has Python '{python_version}' "
                    f"but should require {expected_python_version}+ (like root)",
                )
        except Exception as e:
            rel_path = toml_path.relative_to(project_root)
            violations.append(f"Error reading {rel_path}: {e}")

    return len(violations) == 0, violations


def run_all_golden_rules(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool, dict]:
    """
    Run all Golden Rules validation.

    Args:
        project_root: Root directory of the project
        scope_files: Optional list of specific files to validate (for incremental mode)

    Returns:
        Tuple of (all_passed, results_dict)
    """
    results = {}
    all_passed = True

    # Run all golden rule validators
    golden_rules = [
        ("Golden Rule 5: Package vs App Discipline", validate_package_app_discipline),
        ("Golden Rule 6: Dependency Direction", validate_dependency_direction),
        ("Golden Rule 7: Interface Contracts", validate_interface_contracts),
        ("Golden Rule 8: Error Handling Standards", validate_error_handling_standards),
        ("Golden Rule 9: Logging Standards", validate_logging_standards),
        ("Golden Rule 10: Service Layer Discipline", validate_service_layer_discipline),
        ("Golden Rule 11: Inherit to Extend Pattern", validate_inherit_extend_pattern),
        ("Golden Rule 12: Communication Patterns", validate_communication_patterns),
        ("Golden Rule 13: Package Naming Consistency", validate_package_naming_consistency),
        ("Golden Rule 14: Development Tools Consistency", validate_development_tools_consistency),
        ("Golden Rule 15: Async Pattern Consistency", validate_async_pattern_consistency),
        ("Golden Rule 16: CLI Pattern Consistency", validate_cli_pattern_consistency),
        ("Golden Rule 17: No Global State Access", validate_no_global_state_access),
        ("Golden Rule 18: Test-to-Source File Mapping", validate_test_coverage_mapping),
        ("Golden Rule 19: Test File Quality Standards", validate_test_file_quality),
        ("Golden Rule 20: PyProject Dependency Usage", validate_pyproject_dependency_usage),
        ("Golden Rule 21: Unified Tool Configuration", validate_unified_tool_configuration),
        ("Golden Rule 22: Python Version Consistency", validate_python_version_consistency),
    ]

    for rule_name, validator_func in golden_rules:
        try:
            passed, violations = validator_func(project_root, scope_files)
            results[rule_name] = {"passed": passed, "violations": violations}
            if not passed:
                all_passed = False
        except Exception as e:
            results[rule_name] = {"passed": False, "violations": [f"Validation error: {e}"]}
            all_passed = False

    return all_passed, results
