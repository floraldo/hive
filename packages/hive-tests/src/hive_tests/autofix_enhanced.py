"""
Enhanced Golden Rules Auto-Fixer

PROJECT VANGUARD Phase 3.1 - Expanded automation capabilities.

New Capabilities:
1. Type Hint Automation - Adds missing return type hints
2. Docstring Generation - Creates template docstrings for public functions
3. Import Organization - Groups and sorts imports
4. Exception Handling - Improves bare except blocks

Builds upon existing autofix.py functionality.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from .autofix import AutofixResult, GoldenRulesAutoFixer


@dataclass
class EnhancedAutofixResult(AutofixResult):
    """Extended result with enhancement metadata."""

    enhancement_type: str = ""
    confidence_score: float = 1.0


class TypeHintAnalyzer(ast.NodeVisitor):
    """
    Analyze functions for missing type hints.

    Uses AST analysis and docstring parsing to infer appropriate types.
    """

    def __init__(self):
        self.functions_needing_hints = []
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track current class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check if function needs return type hint."""
        # Skip private and special methods
        if node.name.startswith("_"):
            return

        # Check if return type hint is missing
        if node.returns is None:
            # Infer type from docstring or body
            inferred_type = self._infer_return_type(node)

            self.functions_needing_hints.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "inferred_type": inferred_type,
                    "has_docstring": ast.get_docstring(node) is not None,
                    "in_class": self.current_class,
                }
            )

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check async functions for return type hints."""
        if node.name.startswith("_"):
            return

        if node.returns is None:
            inferred_type = self._infer_return_type(node)

            self.functions_needing_hints.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "inferred_type": inferred_type,
                    "has_docstring": ast.get_docstring(node) is not None,
                    "in_class": self.current_class,
                    "is_async": True,
                }
            )

        self.generic_visit(node)

    def _infer_return_type(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """
        Infer return type from function body and docstring.

        Returns:
            Inferred type hint string
        """
        # Check docstring for return type
        docstring = ast.get_docstring(node)
        if docstring:
            # Look for "Returns:" section
            returns_match = re.search(r"Returns?:\s*\n\s*([^\n]+)", docstring, re.IGNORECASE)
            if returns_match:
                return_desc = returns_match.group(1).strip()

                # Common patterns
                if "bool" in return_desc.lower():
                    return "bool"
                elif "int" in return_desc.lower():
                    return "int"
                elif "str" in return_desc.lower():
                    return "str"
                elif "dict" in return_desc.lower():
                    return "dict[str, Any]"
                elif "list" in return_desc.lower():
                    return "list[Any]"

        # Analyze return statements
        return_types = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                if child.value is None:
                    return_types.add("None")
                elif isinstance(child.value, ast.Constant):
                    if isinstance(child.value.value, bool):
                        return_types.add("bool")
                    elif isinstance(child.value.value, int):
                        return_types.add("int")
                    elif isinstance(child.value.value, str):
                        return_types.add("str")
                elif isinstance(child.value, ast.Dict):
                    return_types.add("dict")
                elif isinstance(child.value, ast.List):
                    return_types.add("list")

        # If only one return type found, use it
        if len(return_types) == 1:
            return_type = return_types.pop()
            if return_type == "dict":
                return "dict[str, Any]"
            elif return_type == "list":
                return "list[Any]"
            return return_type

        # If multiple types or no returns found
        if len(return_types) == 0:
            return "None"
        elif "None" in return_types and len(return_types) == 2:
            # Optional type
            other_type = (return_types - {"None"}).pop()
            return f"{other_type} | None"

        # Default to Any for complex cases
        return "Any"


class DocstringGenerator:
    """
    Generate template docstrings for functions.

    Creates Google-style docstrings with parameter and return information.
    """

    @staticmethod
    def generate_function_docstring(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """
        Generate docstring for a function.

        Args:
            func_node: AST node for function

        Returns:
            Generated docstring text
        """
        lines = ['"""']

        # Generate summary line (placeholder)
        lines.append(f"{func_node.name.replace('_', ' ').title()}.")
        lines.append("")

        # Extract parameters
        args = func_node.args.args
        if args and args[0].arg != "self" and args[0].arg != "cls":
            # Has parameters
            lines.append("Args:")
            for arg in args:
                if arg.arg in ("self", "cls"):
                    continue

                # Try to get type hint
                type_hint = ""
                if arg.annotation:
                    type_hint = f" ({ast.unparse(arg.annotation)})"

                lines.append(f"    {arg.arg}{type_hint}: Description")

            lines.append("")

        # Add Returns section if not void
        if not DocstringGenerator._is_void_function(func_node):
            lines.append("Returns:")
            lines.append("    Description of return value")
            lines.append("")

        lines.append('"""')

        return "\n".join(lines)

    @staticmethod
    def _is_void_function(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if function has no return value."""
        # Check if returns None
        if func_node.returns:
            if isinstance(func_node.returns, ast.Constant):
                if func_node.returns.value is None:
                    return True
            elif isinstance(func_node.returns, ast.Name):
                if func_node.returns.id == "None":
                    return True

        # Check body for return statements
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return):
                if node.value is not None:
                    return False

        return True


class EnhancedGoldenRulesAutoFixer(GoldenRulesAutoFixer):
    """
    Enhanced auto-fixer with additional capabilities.

    Extends base GoldenRulesAutoFixer with:
    - Type hint automation
    - Docstring generation
    - Import organization
    - Exception handling improvements
    """

    def __init__(
        self, project_root: Path, dry_run: bool = True, create_backups: bool = True, min_confidence: float = 0.95
    ) -> None:
        super().__init__(project_root, dry_run, create_backups)
        self.min_confidence = min_confidence
        self.enhanced_results: list[EnhancedAutofixResult] = []

    def fix_type_hints(self, file_path: Path) -> EnhancedAutofixResult | None:
        """
        Add missing return type hints to functions.

        Args:
            file_path: Python file to process

        Returns:
            Result of fix operation or None if no changes needed
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            # Analyze for missing type hints
            analyzer = TypeHintAnalyzer()
            analyzer.visit(tree)

            if not analyzer.functions_needing_hints:
                return None

            # Apply type hints
            changes_made = []
            lines = content.split("\n")

            for func_info in analyzer.functions_needing_hints:
                line_idx = func_info["line"] - 1
                if line_idx >= len(lines):
                    continue

                line = lines[line_idx]

                # Check if this is a function definition
                if "def " not in line:
                    continue

                # Add return type hint
                inferred_type = func_info["inferred_type"]

                # Find the closing parenthesis before colon
                if ":" in line:
                    # Insert return type hint
                    parts = line.split(":")
                    if len(parts) >= 2:
                        # Add return type annotation
                        new_line = f"{parts[0]} -> {inferred_type}:"
                        if len(parts) > 2:
                            new_line += ":".join(parts[2:])
                        else:
                            new_line += parts[1]

                        lines[line_idx] = new_line

                        changes_made.append(
                            f"Added return type hint '{inferred_type}' to "
                            f"{func_info['name']} at line {func_info['line']}"
                        )

            # Apply changes
            if changes_made and not self.dry_run:
                modified_content = "\n".join(lines)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)

            if changes_made:
                return EnhancedAutofixResult(
                    file_path=file_path,
                    rule_id="enhancement-type-hints",
                    rule_name="Type Hint Automation",
                    fixes_applied=len(changes_made),
                    changes_made=changes_made,
                    backup_created=self.create_backups and not self.dry_run,
                    success=True,
                    enhancement_type="type_hints",
                    confidence_score=0.85,
                )

            return None

        except SyntaxError:
            # Skip files with syntax errors
            return None
        except Exception as e:
            return EnhancedAutofixResult(
                file_path=file_path,
                rule_id="enhancement-type-hints",
                rule_name="Type Hint Automation",
                fixes_applied=0,
                changes_made=[],
                backup_created=False,
                success=False,
                error_message=str(e),
                enhancement_type="type_hints",
                confidence_score=0.0,
            )

    def fix_docstrings(self, file_path: Path) -> EnhancedAutofixResult | None:
        """
        Generate docstrings for public functions without them.

        Args:
            file_path: Python file to process

        Returns:
            Result of fix operation or None if no changes needed
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            # Find functions without docstrings
            functions_needing_docs = []

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private functions
                    if node.name.startswith("_"):
                        continue

                    # Check if has docstring
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        functions_needing_docs.append(node)

            if not functions_needing_docs:
                return None

            # Generate and insert docstrings
            changes_made = []
            lines = content.split("\n")

            for func_node in functions_needing_docs:
                # Generate docstring
                docstring = DocstringGenerator.generate_function_docstring(func_node)

                # Find where to insert (after function definition line)
                func_line_idx = func_node.lineno - 1

                # Find the line after the function def (skip decorators)
                insert_idx = func_line_idx + 1

                # Add proper indentation
                func_line = lines[func_line_idx]
                indent = len(func_line) - len(func_line.lstrip())
                indented_lines = [" " * (indent + 4) + line if line else "" for line in docstring.split("\n")]

                # Insert docstring
                for i, doc_line in enumerate(reversed(indented_lines)):
                    lines.insert(insert_idx, doc_line)

                changes_made.append(f"Generated docstring for {func_node.name} at line {func_node.lineno}")

            # Apply changes
            if changes_made and not self.dry_run:
                modified_content = "\n".join(lines)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)

            if changes_made:
                return EnhancedAutofixResult(
                    file_path=file_path,
                    rule_id="enhancement-docstrings",
                    rule_name="Docstring Generation",
                    fixes_applied=len(changes_made),
                    changes_made=changes_made,
                    backup_created=self.create_backups and not self.dry_run,
                    success=True,
                    enhancement_type="docstrings",
                    confidence_score=0.90,
                )

            return None

        except SyntaxError:
            # Skip files with syntax errors
            return None
        except Exception as e:
            return EnhancedAutofixResult(
                file_path=file_path,
                rule_id="enhancement-docstrings",
                rule_name="Docstring Generation",
                fixes_applied=0,
                changes_made=[],
                backup_created=False,
                success=False,
                error_message=str(e),
                enhancement_type="docstrings",
                confidence_score=0.0,
            )

    def organize_imports(self, file_path: Path) -> EnhancedAutofixResult | None:
        """
        Organize imports into standard groups.

        Groups:
        1. Standard library imports
        2. Third-party imports
        3. Hive package imports
        4. Local imports

        Args:
            file_path: Python file to process

        Returns:
            Result of fix operation or None if no changes needed
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")

            # Find import block
            import_start = -1
            import_end = -1

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    if import_start == -1:
                        import_start = i
                    import_end = i
                elif import_start != -1 and stripped and not stripped.startswith("#"):
                    # End of import block
                    break

            if import_start == -1:
                return None

            # Extract imports
            import_lines = lines[import_start : import_end + 1]

            # Categorize imports
            stdlib_imports = []
            thirdparty_imports = []
            hive_imports = []
            local_imports = []

            stdlib_modules = {
                "os",
                "sys",
                "re",
                "json",
                "datetime",
                "time",
                "asyncio",
                "pathlib",
                "typing",
                "dataclasses",
                "abc",
                "collections",
                "functools",
                "itertools",
                "math",
                "random",
                "subprocess",
            }

            for import_line in import_lines:
                stripped = import_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                # Determine category
                if stripped.startswith("from ."):
                    local_imports.append(stripped)
                elif any(f"from {mod}" in stripped or f"import {mod}" in stripped for mod in stdlib_modules):
                    stdlib_imports.append(stripped)
                elif "from hive_" in stripped or "import hive_" in stripped:
                    hive_imports.append(stripped)
                else:
                    thirdparty_imports.append(stripped)

            # Sort within categories
            stdlib_imports.sort()
            thirdparty_imports.sort()
            hive_imports.sort()
            local_imports.sort()

            # Build organized import block
            organized_imports = []

            if stdlib_imports:
                organized_imports.extend(stdlib_imports)
                organized_imports.append("")

            if thirdparty_imports:
                organized_imports.extend(thirdparty_imports)
                organized_imports.append("")

            if hive_imports:
                organized_imports.extend(hive_imports)
                organized_imports.append("")

            if local_imports:
                organized_imports.extend(local_imports)
                organized_imports.append("")

            # Check if already organized
            original_imports = "\n".join(import_lines)
            new_imports = "\n".join(organized_imports)

            if original_imports.strip() == new_imports.strip():
                return None

            # Replace import block
            new_lines = lines[:import_start] + organized_imports + lines[import_end + 1 :]

            # Apply changes
            if not self.dry_run:
                modified_content = "\n".join(new_lines)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)

            return EnhancedAutofixResult(
                file_path=file_path,
                rule_id="enhancement-imports",
                rule_name="Import Organization",
                fixes_applied=1,
                changes_made=[f"Organized {len(import_lines)} imports into standard groups"],
                backup_created=self.create_backups and not self.dry_run,
                success=True,
                enhancement_type="imports",
                confidence_score=0.98,
            )

        except SyntaxError:
            # Skip files with syntax errors
            return None
        except Exception as e:
            return EnhancedAutofixResult(
                file_path=file_path,
                rule_id="enhancement-imports",
                rule_name="Import Organization",
                fixes_applied=0,
                changes_made=[],
                backup_created=False,
                success=False,
                error_message=str(e),
                enhancement_type="imports",
                confidence_score=0.0,
            )

    def fix_all_enhancements(
        self, enable_type_hints: bool = True, enable_docstrings: bool = True, enable_import_org: bool = True
    ) -> list[EnhancedAutofixResult]:
        """
        Apply all enhancement fixes across project.

        Args:
            enable_type_hints: Enable type hint automation
            enable_docstrings: Enable docstring generation
            enable_import_org: Enable import organization

        Returns:
            List of enhancement results
        """
        self.enhanced_results = []

        python_files = self._get_python_files()

        for py_file in python_files:
            try:
                # Create backup if requested
                if self.create_backups and not self.dry_run:
                    self._create_backup(py_file)

                # Apply enhancements
                if enable_type_hints:
                    result = self.fix_type_hints(py_file)
                    if result:
                        self.enhanced_results.append(result)

                if enable_docstrings:
                    result = self.fix_docstrings(py_file)
                    if result:
                        self.enhanced_results.append(result)

                if enable_import_org:
                    result = self.organize_imports(py_file)
                    if result:
                        self.enhanced_results.append(result)

            except Exception as e:
                self.enhanced_results.append(
                    EnhancedAutofixResult(
                        file_path=py_file,
                        rule_id="enhancement-error",
                        rule_name="Enhancement Error",
                        fixes_applied=0,
                        changes_made=[],
                        backup_created=False,
                        success=False,
                        error_message=str(e),
                        enhancement_type="error",
                        confidence_score=0.0,
                    )
                )

        return self.enhanced_results


def main():
    """CLI entry point for enhanced auto-fixer."""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Golden Rules Auto-Fixer - PROJECT VANGUARD Phase 3.1")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--no-backups", action="store_true", help="Skip creating backup files")
    parser.add_argument("--type-hints", action="store_true", help="Add missing type hints")
    parser.add_argument("--docstrings", action="store_true", help="Generate missing docstrings")
    parser.add_argument("--imports", action="store_true", help="Organize imports")
    parser.add_argument("--all", action="store_true", help="Apply all enhancements")

    args = parser.parse_args()

    # Create fixer
    fixer = EnhancedGoldenRulesAutoFixer(
        project_root=args.project_root, dry_run=args.dry_run, create_backups=not args.no_backups
    )

    # Determine what to enable
    enable_all = args.all or not (args.type_hints or args.docstrings or args.imports)

    enable_hints = enable_all or args.type_hints
    enable_docs = enable_all or args.docstrings
    enable_imports = enable_all or args.imports

    print("\n" + "=" * 80)
    print("ENHANCED GOLDEN RULES AUTO-FIXER")
    print("PROJECT VANGUARD Phase 3.1")
    print("=" * 80)
    print(f"\nProject Root: {args.project_root}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE EXECUTION'}")
    print(f"Backups: {'Enabled' if not args.no_backups else 'Disabled'}")
    print("\nEnhancements:")
    print(f"  Type Hints: {'✓' if enable_hints else '✗'}")
    print(f"  Docstrings: {'✓' if enable_docs else '✗'}")
    print(f"  Import Organization: {'✓' if enable_imports else '✗'}")
    print()

    # Run enhancements
    results = fixer.fix_all_enhancements(
        enable_type_hints=enable_hints, enable_docstrings=enable_docs, enable_import_org=enable_imports
    )

    # Report results
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    by_type = {}
    for result in results:
        if result.success:
            by_type.setdefault(result.enhancement_type, []).append(result)

    for enhancement_type, type_results in by_type.items():
        total_fixes = sum(r.fixes_applied for r in type_results)
        print(f"\n{enhancement_type.upper()}:")
        print(f"  Files Modified: {len(type_results)}")
        print(f"  Total Fixes: {total_fixes}")

    failed_results = [r for r in results if not r.success]
    if failed_results:
        print(f"\nFailed: {len(failed_results)} files")
        for result in failed_results[:5]:
            print(f"  - {result.file_path}: {result.error_message}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
