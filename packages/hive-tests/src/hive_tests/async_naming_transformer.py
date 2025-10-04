"""Enhanced AST-based Async Naming Transformer.

Provides robust async function renaming using AST transformation
instead of regex for accuracy and safety.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


@dataclass
class AsyncNamingFix:
    """Result of an async naming fix"""

    old_name: str
    new_name: str
    line_number: int
    occurrences: int


class AsyncNamingTransformer(ast.NodeTransformer):
    """AST transformer that renames async functions to have _async suffix.

    Handles:
    - Function definitions (async def)
    - All function calls throughout the code
    - Method calls (self.method, obj.method)
    - Decorated functions
    - Nested functions
    """

    def __init__(self):
        self.renames: dict[str, str] = {}  # old_name -> new_name
        self.fixes: list[AsyncNamingFix] = []

    def should_rename(self, func_name: str) -> bool:
        """Determine if an async function should be renamed.

        Args:
            func_name: Name of the async function

        Returns:
            True if function should be renamed

        """
        # Already has _async suffix
        if func_name.endswith("_async"):
            return False

        # Already starts with 'a' (convention for async)
        if func_name.startswith("a"):
            return False

        # Special methods (dunder methods)
        if func_name.startswith("__") and func_name.endswith("__"):
            return False

        # Private functions (single underscore)
        if func_name.startswith("_") and not func_name.startswith("__"):
            # Can still rename private async functions
            return True

        # Common async entry points that shouldn't be renamed
        no_rename = {"run", "main", "start", "stop", "close", "setup", "teardown"}
        if func_name in no_rename:
            return False

        # Context manager methods
        if func_name in {"__aenter__", "__aexit__"}:
            return False

        return True

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        """Visit async function definition and rename if needed"""
        old_name = node.name

        if self.should_rename(old_name):
            # Create new name
            if old_name.startswith("_") and not old_name.startswith("__"):
                # Private function: _func -> _func_async
                new_name = f"{old_name}_async"
            else:
                # Public function: func -> func_async
                new_name = f"{old_name}_async"

            # Record the rename
            self.renames[old_name] = new_name

            # Record the fix
            self.fixes.append(
                AsyncNamingFix(
                    old_name=old_name,
                    new_name=new_name,
                    line_number=node.lineno,
                    occurrences=0,  # Will be counted later
                ),
            )

            # Update the function name
            node.name = new_name

            logger.debug(f"Renamed async function '{old_name}' to '{new_name}' at line {node.lineno}")

        # Continue visiting child nodes
        self.generic_visit(node)
        return node

    def visit_Call(self, node: ast.Call) -> Any:
        """Visit function calls and rename if in our rename list"""
        # Handle direct function calls: func()
        if isinstance(node.func, ast.Name):
            old_name = node.func.id
            if old_name in self.renames:
                node.func.id = self.renames[old_name]
                # Increment occurrence count
                for fix in self.fixes:
                    if fix.old_name == old_name:
                        fix.occurrences += 1
                        break

        # Handle method calls: obj.method(), self.method()
        elif isinstance(node.func, ast.Attribute):
            old_name = node.func.attr
            if old_name in self.renames:
                node.func.attr = self.renames[old_name]
                # Increment occurrence count
                for fix in self.fixes:
                    if fix.old_name == old_name:
                        fix.occurrences += 1
                        break

        # Continue visiting child nodes
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        """Visit attribute access and rename if needed (for method references)"""
        # Handle cases like: callback = obj.method (without calling it)
        old_name = node.attr
        if old_name in self.renames:
            node.attr = self.renames[old_name]
            # Increment occurrence count
            for fix in self.fixes:
                if fix.old_name == old_name:
                    fix.occurrences += 1
                    break

        # Continue visiting child nodes
        self.generic_visit(node)
        return node


def fix_async_naming_ast(source_code: str) -> tuple[str, list[AsyncNamingFix]]:
    """Fix async function naming using AST transformation.

    Args:
        source_code: Python source code as string

    Returns:
        Tuple of (fixed_source_code, list_of_fixes_applied)

    Raises:
        SyntaxError: If source code is not valid Python

    """
    # Parse the source code
    tree = ast.parse(source_code)

    # Apply transformations
    transformer = (AsyncNamingTransformer(),)
    new_tree = transformer.visit(tree)

    # Fix missing locations
    ast.fix_missing_locations(new_tree)

    # Convert back to source code
    # Try ast.unparse first (Python 3.9+)
    if hasattr(ast, "unparse"):
        fixed_code = ast.unparse(new_tree)
        return fixed_code, transformer.fixes
    # Fall back to astor if available
    try:
        import astor

        fixed_code = astor.to_source(new_tree)
        return fixed_code, transformer.fixes
    except ImportError:
        logger.error("Neither ast.unparse nor astor available. Cannot transform AST back to source.")
        raise RuntimeError("AST to source conversion not available. Install astor or use Python 3.9+")


def analyze_async_naming_violations(source_code: str) -> list[AsyncNamingFix]:
    """Analyze source code for async naming violations without fixing.

    Args:
        source_code: Python source code as string

    Returns:
        List of violations found (with occurrences=0)

    """
    try:
        tree = (ast.parse(source_code),)
        transformer = AsyncNamingTransformer()

        # Just identify violations without transforming
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                if transformer.should_rename(node.name):
                    new_name = f"{node.name}_async"
                    transformer.fixes.append(
                        AsyncNamingFix(
                            old_name=node.name,
                            new_name=new_name,
                            line_number=node.lineno,
                            occurrences=0,
                        ),
                    )

        return transformer.fixes

    except SyntaxError as e:
        logger.warning(f"Syntax error analyzing async naming: {e}")
        return []


def get_async_naming_report(fixes: list[AsyncNamingFix]) -> str:
    """Generate a human-readable report of async naming fixes.

    Args:
        fixes: List of fixes applied

    Returns:
        Formatted report string

    """
    if not fixes:
        return "No async naming violations found."

    lines = [
        "Async Naming Fixes Applied:",
        "=" * 60,
    ]

    for fix in fixes:
        lines.append(f"Line {fix.line_number}: {fix.old_name} -> {fix.new_name}")
        if fix.occurrences > 0:
            lines.append(f"  Updated {fix.occurrences} call site(s)")

    lines.append("=" * 60)
    lines.append(f"Total functions renamed: {len(fixes)}")

    total_occurrences = sum(fix.occurrences for fix in fixes)
    lines.append(f"Total call sites updated: {total_occurrences}")

    return "\n".join(lines)
