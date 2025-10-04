#!/usr/bin/env python3
"""Auto-tag tests with pytest markers based on directory structure.

Core and Crust Strategy:
- packages/ → @pytest.mark.core (strict quality standards)
- apps/, integration_tests/ → @pytest.mark.crust (lenient standards)

Usage:
    python scripts/testing/auto_tag_tests.py
    python scripts/testing/auto_tag_tests.py --dry-run
    python scripts/testing/auto_tag_tests.py --verify
"""

import ast
import sys
from pathlib import Path
from typing import Literal

# Marker definitions
CORE_MARKER = "pytest.mark.core"
CRUST_MARKER = "pytest.mark.crust"


class TestMarkerAdder(ast.NodeTransformer):
    """AST transformer to add pytest markers to test functions/classes."""

    def __init__(self, marker_name: str):
        self.marker_name = marker_name
        self.modified = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Add marker to test functions (always tag functions, not just top-level)."""
        if node.name.startswith("test_"):
            if not self._has_marker(node):
                node.decorator_list.insert(0, self._create_marker())
                self.modified = True
        # Continue traversal for nested classes
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        """Add marker to async test functions (always tag functions, not just top-level)."""
        if node.name.startswith("test_"):
            if not self._has_marker(node):
                node.decorator_list.insert(0, self._create_marker())
                self.modified = True
        # Continue traversal for nested classes
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Add marker to test classes AND their methods."""
        if node.name.startswith("Test"):
            if not self._has_marker(node):
                node.decorator_list.insert(0, self._create_marker())
                self.modified = True
        # Continue traversal for methods inside class
        self.generic_visit(node)
        return node

    def _has_marker(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
        """Check if node already has the marker."""
        for decorator in node.decorator_list:
            marker_str = ast.unparse(decorator)
            if self.marker_name in marker_str:
                return True
        return False

    def _create_marker(self) -> ast.Attribute:
        """Create AST node for pytest.mark.X decorator."""
        # Parse the marker string to get proper AST structure
        marker_parts = self.marker_name.split(".")
        if len(marker_parts) == 3:  # pytest.mark.core
            return ast.Attribute(
                value=ast.Attribute(value=ast.Name(id=marker_parts[0], ctx=ast.Load()), attr=marker_parts[1], ctx=ast.Load()),
                attr=marker_parts[2],
                ctx=ast.Load(),
            )
        raise ValueError(f"Invalid marker format: {self.marker_name}")


def get_marker_for_path(test_file: Path) -> str | None:
    """Determine which marker to add based on file path."""
    parts = test_file.parts

    if "packages" in parts:
        return CORE_MARKER
    elif "apps" in parts or "integration_tests" in parts:
        return CRUST_MARKER
    return None


def add_pytest_import(tree: ast.Module) -> tuple[ast.Module, bool]:
    """Add 'import pytest' if not present."""
    has_pytest = any(
        isinstance(node, ast.Import) and any(alias.name == "pytest" for alias in node.names)
        or isinstance(node, ast.ImportFrom) and node.module == "pytest"
        for node in tree.body
    )

    if has_pytest:
        return tree, False

    # Add import pytest at the top (after module docstring if present)
    import_node = ast.Import(names=[ast.alias(name="pytest", asname=None)])

    # Find insertion point (after docstring if present)
    insert_idx = 0
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        insert_idx = 1

    tree.body.insert(insert_idx, import_node)
    return tree, True


def process_test_file(test_file: Path, marker_name: str, dry_run: bool = False) -> tuple[bool, str]:
    """Add pytest marker to all test functions/classes in file.

    Returns:
        (modified, status_message)
    """
    try:
        content = test_file.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # Add pytest import if needed
        tree, import_added = add_pytest_import(tree)

        # Add markers
        transformer = TestMarkerAdder(marker_name)
        new_tree = transformer.visit(tree)

        if not transformer.modified and not import_added:
            return False, "already tagged"

        # Convert back to source code
        new_content = ast.unparse(new_tree)

        if not dry_run:
            test_file.write_text(new_content, encoding="utf-8")

        status = []
        if import_added:
            status.append("added pytest import")
        if transformer.modified:
            status.append("added markers")

        return True, ", ".join(status)

    except SyntaxError as e:
        return False, f"syntax error: {e}"
    except Exception as e:
        return False, f"error: {e}"


def find_test_files(root: Path) -> list[Path]:
    """Find all test files in packages/, apps/, integration_tests/."""
    test_files = []

    for directory in ["packages", "apps", "integration_tests"]:
        dir_path = root / directory
        if dir_path.exists():
            test_files.extend(dir_path.rglob("test_*.py"))
            test_files.extend(dir_path.rglob("*_test.py"))

    return sorted(set(test_files))


def verify_tagging(root: Path) -> dict[str, int]:
    """Verify that all tests are properly tagged."""
    stats = {"core": 0, "crust": 0, "untagged": 0, "errors": 0}

    test_files = find_test_files(root)

    for test_file in test_files:
        try:
            content = test_file.read_text(encoding="utf-8")
            tree = ast.parse(content)

            expected_marker = get_marker_for_path(test_file)
            if not expected_marker:
                continue

            # Check all test functions/classes
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if isinstance(node, ast.ClassDef) and node.name.startswith("Test") or node.name.startswith("test_"):
                        has_marker = any(expected_marker in ast.unparse(dec) for dec in node.decorator_list)

                        if has_marker:
                            if "core" in expected_marker:
                                stats["core"] += 1
                            else:
                                stats["crust"] += 1
                        else:
                            stats["untagged"] += 1

        except Exception:
            stats["errors"] += 1

    return stats


def main():
    """Auto-tag all test files with appropriate pytest markers."""
    import argparse

    parser = argparse.ArgumentParser(description="Auto-tag tests with pytest markers")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    parser.add_argument("--verify", action="store_true", help="Verify tagging is complete")
    args = parser.parse_args()

    root = Path(__file__).parent.parent.parent

    if args.verify:
        print("Verifying test tagging...")
        stats = verify_tagging(root)
        print(f"\nCore tests: {stats['core']}")
        print(f"Crust tests: {stats['crust']}")
        print(f"Untagged tests: {stats['untagged']}")
        print(f"Errors: {stats['errors']}")

        if stats["untagged"] > 0:
            print("\n[FAIL] Some tests are not tagged. Run without --verify to fix.")
            return 1
        else:
            print("\n[OK] All tests are properly tagged!")
            return 0

    print("Auto-tagging test files...")
    if args.dry_run:
        print("(DRY RUN - no files will be modified)")

    test_files = find_test_files(root)
    print(f"Found {len(test_files)} test files\n")

    modified_count = 0
    skipped_count = 0
    error_count = 0

    for test_file in test_files:
        marker = get_marker_for_path(test_file)
        if not marker:
            continue

        rel_path = test_file.relative_to(root)
        modified, status = process_test_file(test_file, marker, dry_run=args.dry_run)

        if modified:
            print(f"[MODIFIED] {rel_path}: {status}")
            modified_count += 1
        elif "error" in status:
            print(f"[ERROR] {rel_path}: {status}")
            error_count += 1
        else:
            skipped_count += 1

    print(f"\nSummary:")
    print(f"  Modified: {modified_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")

    if args.dry_run:
        print("\n(DRY RUN - run without --dry-run to apply changes)")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
