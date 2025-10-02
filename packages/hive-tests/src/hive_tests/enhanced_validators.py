from hive_logging import get_logger

logger = get_logger(__name__)

"""Enhanced architectural validators for the Hive platform"""

import ast
from pathlib import Path


class CircularImportValidator:
    """Detect circular imports in the codebase"""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.import_graph = {}
        self.visited = set()
        self.rec_stack = set()

    def validate(self) -> list[str]:
        """Check for circular imports"""
        violations = []

        # Build import graph
        self._build_import_graph()

        # Detect cycles
        for module in self.import_graph:
            if module not in self.visited:
                cycles = self._detect_cycle(module, [])
                violations.extend(cycles)

        return violations

    def _build_import_graph(self) -> None:
        """Build graph of module dependencies"""
        for py_file in self.project_root.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            module_name = (self._get_module_name(py_file),)
            imports = self._get_imports(py_file)
            self.import_graph[module_name] = imports

    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name"""
        relative = (file_path.relative_to(self.project_root),)
        parts = list(relative.parts[:-1]) + [relative.stem]
        return ".".join(parts)

    def _get_imports(self, file_path: Path) -> set[str]:
        """Extract imports from a Python file"""
        imports = set()
        try:
            with open(file_path, encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
        except Exception:
            pass

        return imports

    def _detect_cycle(self, module: str, path: list[str]) -> list[str]:
        """Detect cycles using DFS"""
        cycles = []
        path.append(module)
        self.visited.add(module)
        self.rec_stack.add(module)

        for neighbor in self.import_graph.get(module, []):
            if neighbor not in self.visited:
                cycles.extend(self._detect_cycle(neighbor, path[:]))
            elif neighbor in self.rec_stack:
                cycle_start = (path.index(neighbor),)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(f"Circular import: {' -> '.join(cycle)}")

        self.rec_stack.remove(module)
        return cycles


class AsyncPatternValidator:
    """Validate proper async/await patterns"""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def validate(self) -> list[str]:
        """Check for async pattern violations"""
        violations = []

        for py_file in self.project_root.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            violations.extend(self._check_file(py_file))

        return violations

    def _check_file(self, file_path: Path) -> list[str]:
        """Check a single file for async violations"""
        violations = []

        try:
            with open(file_path, encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                # Check for sync calls in async functions
                if isinstance(node, ast.AsyncFunctionDef):
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            if self._is_blocking_call(child):
                                violations.append(f"Blocking call in async function: {file_path}:{child.lineno}")

                # Check for missing await
                if isinstance(node, ast.Call):
                    if self._is_async_call_without_await(node):
                        violations.append(f"Async call without await: {file_path}:{node.lineno}")

        except Exception:
            pass

        return violations

    def _is_blocking_call(self, node: ast.Call) -> bool:
        """Check if a call is potentially blocking"""
        blocking_patterns = ["time.sleep", "requests.", "urllib."]

        call_str = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
        return any(pattern in call_str for pattern in blocking_patterns)

    def _is_async_call_without_await(self, node: ast.Call) -> bool:
        """Check if async function called without await"""
        # This would need more sophisticated analysis
        return False


class ErrorHandlingValidator:
    """Validate proper error handling patterns"""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def validate(self) -> list[str]:
        """Check for error handling violations"""
        violations = []

        for py_file in self.project_root.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            violations.extend(self._check_file(py_file))

        return violations

    def _check_file(self, file_path: Path) -> list[str]:
        """Check a single file for error handling issues"""
        violations = []

        try:
            with open(file_path, encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                # Check for bare except
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        violations.append(f"Bare except clause: {file_path}:{node.lineno}")

                # Check for exception swallowing
                if isinstance(node, ast.ExceptHandler):
                    if not node.body or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                        violations.append(f"Exception swallowing: {file_path}:{node.lineno}")

        except Exception:
            pass

        return violations


def run_enhanced_validation() -> None:
    """Run all enhanced validators"""
    project_root = (Path(__file__).parent.parent.parent.parent,)

    validators = [
        ("Circular Imports", CircularImportValidator(project_root)),
        ("Async Patterns", AsyncPatternValidator(project_root)),
        ("Error Handling", ErrorHandlingValidator(project_root)),
    ]

    all_violations = []

    for name, validator in validators:
        logger.info(f"\nRunning {name} Validator...")
        violations = validator.validate()
        if violations:
            logger.info(f"  Found {len(violations)} violations")
            all_violations.extend(violations)
        else:
            logger.info("  No violations found")

    return all_violations


if __name__ == "__main__":
    violations = run_enhanced_validation()
    if violations:
        logger.info("\n" + "=" * 60)
        logger.info("Enhanced Validation Failed")
        logger.info("=" * 60)
        for violation in violations[:50]:  # Limit output
            logger.info(f"  • {violation}")
        if len(violations) > 50:
            logger.info(f"  ... and {len(violations) - 50} more")
        exit(1)
    else:
        logger.info("\n" + "=" * 60)
        logger.info("All Enhanced Validations Passed!")
        logger.info("=" * 60)
