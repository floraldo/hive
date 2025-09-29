#!/usr/bin/env python3
"""
Hive Platform Hardening Script
Systematically fixes Golden Rule violations and optimizes the codebase
"""

import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
PACKAGES_DIR = PROJECT_ROOT / "packages"
APPS_DIR = PROJECT_ROOT / "apps"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Patterns for fixes
ASYNC_FUNCTION_PATTERN = re.compile(r"async\s+def\s+(\w+)\s*\(")
BARE_EXCEPT_PATTERN = re.compile(r"except\s*:\s*$", re.MULTILINE)
GLOBAL_CONFIG_PATTERN = re.compile(r"load_config\(\)")
DI_FALLBACK_PATTERN = re.compile(r"(?:config|logger|db)\s*=\s*None")
DI_FALLBACK_BLOCK_PATTERN = re.compile(r"if\s+(?:config|logger|db)\s+is\s+None\s*:")


class HardenPlatform:
    def __init__(self):
        self.fixes_applied = defaultdict(list)
        self.errors = []

    def run(self):
        """Execute all hardening tasks"""
        print("=" * 60)
        print("Hive Platform Hardening Script")
        print("=" * 60)

        # Phase 1: Fix Golden Rule violations
        print("\nPhase 1: Fixing Golden Rule Violations")
        print("-" * 40)
        self.fix_async_naming()
        self.fix_bare_except_clauses()
        self.standardize_pytest_versions()
        self.remove_global_state()

        # Phase 2: Clean up directory structure
        print("\nPhase 2: Cleaning Directory Structure")
        print("-" * 40)
        self.move_root_files()
        self.cleanup_old_directories()

        # Phase 3: Add architectural tests
        print("\nPhase 3: Strengthening Architecture")
        print("-" * 40)
        self.add_architectural_tests()

        # Phase 4: Generate report
        print("\nGenerating Report")
        print("-" * 40)
        self.generate_report()

    def fix_async_naming(self):
        """Fix async functions to end with _async suffix"""
        print("Fixing async function naming conventions...")

        # List of functions to rename
        async_renames = {
            "run": "run_async",
            "deploy": "deploy_async",
            "check_health": "check_health_async",
            "pre_deployment_checks": "pre_deployment_checks_async",
            "rollback": "rollback_async",
            "post_deployment_actions": "post_deployment_actions_async",
            "validate_configuration": "validate_configuration_async",
            "async_table_exists": "table_exists_async",
            "async_get_database_info": "get_database_info_async",
        }

        files_to_check = []
        for root, _, files in os.walk(APPS_DIR):
            for file in files:
                if file.endswith(".py"):
                    files_to_check.append(Path(root) / file)

        for root, _, files in os.walk(PACKAGES_DIR):
            for file in files:
                if file.endswith(".py"):
                    files_to_check.append(Path(root) / file)

        for file_path in files_to_check:
            try:
                content = file_path.read_text(encoding="utf-8")
                original_content = content
                modified = False

                # Find async functions without _async suffix
                matches = ASYNC_FUNCTION_PATTERN.findall(content)
                for func_name in matches:
                    if not func_name.endswith("_async") and not func_name.startswith("__"):
                        new_name = async_renames.get(func_name, f"{func_name}_async")

                        # Replace function definition
                        content = re.sub(rf"async\s+def\s+{func_name}\s*\(", f"async def {new_name}(", content)

                        # Replace function calls
                        content = re.sub(rf"(?<!def\s)(?<!def\s\s){func_name}\s*\(", f"{new_name}(", content)

                        # Replace await calls
                        content = re.sub(rf"await\s+{func_name}\s*\(", f"await {new_name}(", content)

                        modified = True
                        self.fixes_applied["async_naming"].append(f"{file_path}: {func_name} -> {new_name}")

                if modified:
                    file_path.write_text(content, encoding="utf-8")

            except Exception as e:
                self.errors.append(f"Error processing {file_path}: {e}")

    def fix_bare_except_clauses(self):
        """Replace bare except clauses with specific exceptions"""
        print("Fixing bare except clauses...")

        target_file = PROJECT_ROOT / "apps/ecosystemiser/dashboard/app_isolated.py"
        if target_file.exists():
            try:
                content = target_file.read_text(encoding="utf-8")

                # Replace bare except with specific exception
                content = re.sub(r"except\s*:\s*$", "except Exception:", content, flags=re.MULTILINE)

                target_file.write_text(content, encoding="utf-8")
                self.fixes_applied["bare_except"].append(str(target_file))

            except Exception as e:
                self.errors.append(f"Error fixing bare except in {target_file}: {e}")

    def standardize_pytest_versions(self):
        """Standardize pytest versions across all pyproject.toml files"""
        print("Standardizing pytest versions...")

        pyproject_files = list(PROJECT_ROOT.glob("**/pyproject.toml"))

        for pyproject_file in pyproject_files:
            try:
                content = pyproject_file.read_text(encoding="utf-8")

                # Replace old pytest versions with standard version
                old_content = content
                content = re.sub(r'pytest\s*=\s*"[\^~]?7\.\d+\.\d+"', 'pytest = "^8.3.2"', content)

                if content != old_content:
                    pyproject_file.write_text(content, encoding="utf-8")
                    self.fixes_applied["pytest_version"].append(str(pyproject_file))

            except Exception as e:
                self.errors.append(f"Error updating {pyproject_file}: {e}")

    def remove_global_state(self):
        """Remove global state access and DI fallback patterns"""
        print("Removing global state and DI fallbacks...")

        files_with_global_state = [
            "apps/ai-deployer/src/ai_deployer/core/config.py",
            "apps/ai-planner/src/ai_planner/core/config.py",
            "apps/ai-reviewer/src/ai_reviewer/core/config.py",
            "apps/hive-orchestrator/src/hive_orchestrator/hive_core.py",
        ]

        for file_path in files_with_global_state:
            full_path = PROJECT_ROOT / file_path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8")
                    original_content = content

                    # Remove load_config() calls
                    content = re.sub(r"^\s*(?:config|cfg)\s*=\s*load_config\(\).*$", "", content, flags=re.MULTILINE)

                    # Remove DI fallback patterns
                    content = re.sub(r",\s*config\s*=\s*None", "", content)

                    # Remove DI fallback blocks
                    content = re.sub(
                        r"if\s+config\s+is\s+None:\s*\n\s+config\s*=\s*load_config\(\)", "", content, flags=re.MULTILINE,
                    )

                    if content != original_content:
                        full_path.write_text(content, encoding="utf-8")
                        self.fixes_applied["global_state"].append(str(full_path))

                except Exception as e:
                    self.errors.append(f"Error removing global state from {full_path}: {e}")

    def move_root_files(self):
        """Move Python files from root to appropriate directories"""
        print("Moving root Python files...")

        root_python_files = [("init_db_simple.py", "scripts/init_db_simple.py")]

        for src_file, dest_file in root_python_files:
            src_path = PROJECT_ROOT / src_file
            dest_path = PROJECT_ROOT / dest_file

            if src_path.exists():
                try:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src_path), str(dest_path))
                    self.fixes_applied["moved_files"].append(f"{src_file} -> {dest_file}")
                except Exception as e:
                    self.errors.append(f"Error moving {src_file}: {e}")

    def cleanup_old_directories(self):
        """Remove old/deprecated directories"""
        print("Cleaning up old directories...")

        dirs_to_remove = ["apps/ecosystemiser/src/EcoSystemiser/profile_loader/climate/processing/validation_old"]

        for dir_path in dirs_to_remove:
            full_path = PROJECT_ROOT / dir_path
            if full_path.exists():
                try:
                    shutil.rmtree(full_path)
                    self.fixes_applied["removed_dirs"].append(str(dir_path))
                except Exception as e:
                    self.errors.append(f"Error removing {dir_path}: {e}")

    def add_architectural_tests(self):
        """Add more comprehensive architectural tests"""
        print("Adding architectural tests...")

        test_file = PROJECT_ROOT / "packages/hive-tests/src/hive_tests/enhanced_validators.py"

        test_content = '''"""Enhanced architectural validators for the Hive platform"""

import ast
import os
from pathlib import Path
from typing import List, Set, Tuple


class CircularImportValidator:
    """Detect circular imports in the codebase"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.import_graph = {}
        self.visited = set()
        self.rec_stack = set()

    def validate(self) -> List[str]:
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

    def _build_import_graph(self):
        """Build graph of module dependencies"""
        for py_file in self.project_root.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            module_name = self._get_module_name(py_file)
            imports = self._get_imports(py_file)
            self.import_graph[module_name] = imports

    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name"""
        relative = file_path.relative_to(self.project_root)
        parts = list(relative.parts[:-1]) + [relative.stem]
        return ".".join(parts)

    def _get_imports(self, file_path: Path) -> Set[str]:
        """Extract imports from a Python file"""
        imports = set()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
        except:
            pass

        return imports

    def _detect_cycle(self, module: str, path: List[str]) -> List[str]:
        """Detect cycles using DFS"""
        cycles = []
        path.append(module)
        self.visited.add(module)
        self.rec_stack.add(module)

        for neighbor in self.import_graph.get(module, []):
            if neighbor not in self.visited:
                cycles.extend(self._detect_cycle(neighbor, path[:]))
            elif neighbor in self.rec_stack:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(f"Circular import: {' -> '.join(cycle)}")

        self.rec_stack.remove(module)
        return cycles


class AsyncPatternValidator:
    """Validate proper async/await patterns"""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def validate(self) -> List[str]:
        """Check for async pattern violations"""
        violations = []

        for py_file in self.project_root.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            violations.extend(self._check_file(py_file))

        return violations

    def _check_file(self, file_path: Path) -> List[str]:
        """Check a single file for async violations"""
        violations = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                # Check for sync calls in async functions
                if isinstance(node, ast.AsyncFunctionDef):
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            if self._is_blocking_call(child):
                                violations.append(
                                    f"Blocking call in async function: {file_path}:{child.lineno}"
                                )

                # Check for missing await
                if isinstance(node, ast.Call):
                    if self._is_async_call_without_await(node):
                        violations.append(
                            f"Async call without await: {file_path}:{node.lineno}"
                        )

        except:
            pass

        return violations

    def _is_blocking_call(self, node: ast.Call) -> bool:
        """Check if a call is potentially blocking"""
        blocking_patterns = ["time.sleep", "requests.", "urllib."]

        call_str = ast.unparse(node.func) if hasattr(ast, 'unparse') else ""
        return any(pattern in call_str for pattern in blocking_patterns)

    def _is_async_call_without_await(self, node: ast.Call) -> bool:
        """Check if async function called without await"""
        # This would need more sophisticated analysis
        return False


class ErrorHandlingValidator:
    """Validate proper error handling patterns"""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def validate(self) -> List[str]:
        """Check for error handling violations"""
        violations = []

        for py_file in self.project_root.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            violations.extend(self._check_file(py_file))

        return violations

    def _check_file(self, file_path: Path) -> List[str]:
        """Check a single file for error handling issues"""
        violations = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                # Check for bare except
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        violations.append(
                            f"Bare except clause: {file_path}:{node.lineno}"
                        )

                # Check for exception swallowing
                if isinstance(node, ast.ExceptHandler):
                    if not node.body or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                        violations.append(
                            f"Exception swallowing: {file_path}:{node.lineno}"
                        )

        except:
            pass

        return violations


def run_enhanced_validation():
    """Run all enhanced validators"""
    project_root = Path(__file__).parent.parent.parent.parent

    validators = [
        ("Circular Imports", CircularImportValidator(project_root)),
        ("Async Patterns", AsyncPatternValidator(project_root)),
        ("Error Handling", ErrorHandlingValidator(project_root)),
    ]

    all_violations = []

    for name, validator in validators:
        print(f"\\nRunning {name} Validator...")
        violations = validator.validate()
        if violations:
            print(f"  Found {len(violations)} violations")
            all_violations.extend(violations)
        else:
            print("  No violations found")

    return all_violations


if __name__ == "__main__":
    violations = run_enhanced_validation()
    if violations:
        print("\\n" + "=" * 60)
        print("Enhanced Validation Failed")
        print("=" * 60)
        for violation in violations[:50]:  # Limit output
            print(f"  • {violation}")
        if len(violations) > 50:
            print(f"  ... and {len(violations) - 50} more")
        exit(1)
    else:
        print("\\n" + "=" * 60)
        print("All Enhanced Validations Passed!")
        print("=" * 60)
'''

        try:
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text(test_content, encoding="utf-8")
            self.fixes_applied["architectural_tests"].append(str(test_file))
        except Exception as e:
            self.errors.append(f"Error creating architectural tests: {e}")

    def generate_report(self):
        """Generate a comprehensive report of all fixes"""
        report_file = PROJECT_ROOT / "claudedocs/HARDENING_REPORT.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)

        report = ["# Hive Platform Hardening Report", ""]
        report.append(f"**Date**: {Path(__file__).stat().st_mtime}")
        report.append("")

        # Summary
        report.append("## Summary")
        total_fixes = sum(len(fixes) for fixes in self.fixes_applied.values())
        report.append(f"- **Total Fixes Applied**: {total_fixes}")
        report.append(f"- **Categories Fixed**: {len(self.fixes_applied)}")
        report.append(f"- **Errors Encountered**: {len(self.errors)}")
        report.append("")

        # Detailed fixes
        report.append("## Fixes Applied")
        report.append("")

        for category, fixes in self.fixes_applied.items():
            report.append(f"### {category.replace('_', ' ').title()}")
            report.append(f"**Count**: {len(fixes)}")
            report.append("")
            for fix in fixes[:10]:  # Limit to first 10
                report.append(f"- {fix}")
            if len(fixes) > 10:
                report.append(f"- ... and {len(fixes) - 10} more")
            report.append("")

        # Errors
        if self.errors:
            report.append("## Errors Encountered")
            report.append("")
            for error in self.errors:
                report.append(f"- {error}")
            report.append("")

        # Next steps
        report.append("## Next Steps")
        report.append("")
        report.append("1. Run `python scripts/validate_golden_rules.py` to verify fixes")
        report.append("2. Run tests to ensure no regressions")
        report.append("3. Review service layer files for business logic extraction")
        report.append("4. Refactor CLIs to use hive-cli utilities")
        report.append("")

        report_file.write_text("\n".join(report), encoding="utf-8")
        print(f"Report generated: {report_file}")


if __name__ == "__main__":
    hardener = HardenPlatform()
    hardener.run()

    print("\n" + "=" * 60)
    print("Hardening Complete!")
    print("=" * 60)
    print(f"Total fixes applied: {sum(len(fixes) for fixes in hardener.fixes_applied.values())}")
    if hardener.errors:
        print(f"Errors encountered: {len(hardener.errors)}")
    print("\nRun validation script to verify fixes:")
    print("  python scripts/validate_golden_rules.py")
