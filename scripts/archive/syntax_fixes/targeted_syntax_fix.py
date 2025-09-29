#!/usr/bin/env python3
"""
Targeted Syntax Fix - Strategic Force Multiplier Initiative Phase 2

Specifically targets the most common syntax patterns causing failures:
1. Missing commas in function parameter lists
2. Missing commas in function call arguments
3. Trailing commas in single-element tuples
4. Missing commas in multiline imports

This is part of the systematic approach to fix the 135+ syntax errors
blocking platform stabilization.
"""

import ast
import re
import sys
from pathlib import Path

from hive_logging import get_logger

logger = get_logger(__name__)


class TargetedSyntaxFixer:
    """Targeted syntax fixer for specific high-frequency error patterns."""

    def __init__(self):
        self.fixes_applied = 0

    def fix_function_parameters(self, content: str) -> str:
        """Fix missing commas in function parameter definitions."""
        fixes = 0

        # Pattern: def function_name(\n    param1: type\n    param2: type\n...)
        def fix_param_block(match):
            nonlocal fixes
            header = match.group(1)  # "def function_name("
            params_block = match.group(2)  # parameter block
            footer = match.group(3)  # "):"

            # Split into lines and fix missing commas
            lines = params_block.split("\n")
            fixed_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue

                # If this line has a parameter and next line also has a parameter, add comma
                if i < len(lines) - 1 and ":" in stripped and not stripped.endswith(",") and not stripped.endswith(")"):

                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith(")")
                        and not next_line.startswith("#")
                        and (":" in next_line or next_line.startswith("**"))
                    ):
                        line = line.rstrip() + ","
                        fixes += 1

                fixed_lines.append(line)

            return header + "\n".join(fixed_lines) + footer

        # Match function definitions with multiline parameters
        pattern = r"(def\s+\w+\s*\(\s*\n)(.*?)(\n\s*\):)"
        content = re.sub(pattern, fix_param_block, content, flags=re.DOTALL)

        self.fixes_applied += fixes
        return content

    def fix_classmethod_parameters(self, content: str) -> str:
        """Fix missing commas in @classmethod parameters."""
        fixes = 0

        def fix_classmethod_block(match):
            nonlocal fixes
            decorator = match.group(1)  # @classmethod\n
            header = match.group(2)  # def method_name(
            params_block = match.group(3)  # parameter block
            footer = match.group(4)  # ):

            # Split into lines and fix missing commas
            lines = params_block.split("\n")
            fixed_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue

                # If this line has a parameter and next line also has a parameter, add comma
                if (
                    i < len(lines) - 1
                    and (":" in stripped or "cls" in stripped)
                    and not stripped.endswith(",")
                    and not stripped.endswith(")")
                ):

                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith(")")
                        and not next_line.startswith("#")
                        and (":" in next_line or "**" in next_line)
                    ):
                        line = line.rstrip() + ","
                        fixes += 1

                fixed_lines.append(line)

            return decorator + header + "\n".join(fixed_lines) + footer

        # Match @classmethod with multiline parameters
        pattern = r"(@classmethod\s*\n\s*)(def\s+\w+\s*\(\s*\n)(.*?)(\n\s*\):)"
        content = re.sub(pattern, fix_classmethod_block, content, flags=re.DOTALL)

        self.fixes_applied += fixes
        return content

    def fix_function_calls(self, content: str) -> str:
        """Fix missing commas in function call arguments."""
        fixes = 0

        def fix_call_block(match):
            nonlocal fixes
            header = match.group(1)  # "function_name("
            args_block = match.group(2)  # arguments block
            footer = match.group(3)  # ")"

            # Split into lines and fix missing commas
            lines = args_block.split("\n")
            fixed_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue

                # If this line has an argument and next line also has an argument, add comma
                if (
                    i < len(lines) - 1
                    and ("=" in stripped or stripped.isidentifier() or '"' in stripped)
                    and not stripped.endswith(",")
                    and not stripped.endswith(")")
                ):

                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith(")")
                        and not next_line.startswith("#")
                        and ("=" in next_line or next_line.isidentifier() or '"' in next_line)
                    ):
                        line = line.rstrip() + ","
                        fixes += 1

                fixed_lines.append(line)

            return header + "\n".join(fixed_lines) + footer

        # Match function calls with multiline arguments (return statements)
        pattern = r"(\w+\s*\(\s*\n)(.*?)(\n\s*\))"
        content = re.sub(pattern, fix_call_block, content, flags=re.DOTALL)

        self.fixes_applied += fixes
        return content

    def fix_tuple_trailing_commas(self, content: str) -> str:
        """Fix trailing commas in single-element tuples that cause syntax errors."""
        fixes = 0

        # Remove trailing commas that cause syntax errors
        patterns = [
            # Fix: (item,) when it should be (item)
            r"\(\s*([^,\(\)]+),\s*\)(?=\s*[=\)])",
            # Fix: constraints = ([],) should be constraints = []
            r"=\s*\(\s*\[\s*\]\s*,\s*\)",
        ]

        for pattern in patterns:
            if "constraints = " in pattern:
                content = re.sub(pattern, "= []", content)
            else:
                content = re.sub(pattern, r"(\1)", content)
            fixes += content.count("(") - content.count(")")  # Rough estimate

        self.fixes_applied += fixes
        return content

    def fix_import_commas(self, content: str) -> str:
        """Fix missing commas in multiline import statements."""
        fixes = 0

        def fix_import_block(match):
            nonlocal fixes
            header = match.group(1)  # "from module import ("
            imports_block = match.group(2)  # import items
            footer = match.group(3)  # ")"

            # Split into lines and fix missing commas
            lines = imports_block.split("\n")
            fixed_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue

                # If this line has an import and next line also has an import, add comma
                if i < len(lines) - 1 and stripped and not stripped.endswith(",") and not stripped.endswith(")"):

                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith(")") and not next_line.startswith("#"):
                        line = line.rstrip() + ","
                        fixes += 1

                fixed_lines.append(line)

            return header + "\n".join(fixed_lines) + footer

        # Match multiline imports
        pattern = r"(from\s+[\w\.]+\s+import\s+\(\s*\n)(.*?)(\n\s*\))"
        content = re.sub(pattern, fix_import_block, content, flags=re.DOTALL)

        self.fixes_applied += fixes
        return content

    def fix_all_patterns(self, content: str, filepath: str) -> str:
        """Apply all targeted syntax fixes to content."""
        original_content = content

        # Apply fixes in order of safety
        content = self.fix_import_commas(content)
        content = self.fix_function_parameters(content)
        content = self.fix_classmethod_parameters(content)
        content = self.fix_function_calls(content)
        content = self.fix_tuple_trailing_commas(content)

        if content != original_content:
            logger.info(f"Applied {self.fixes_applied} targeted fixes to {filepath}")

        return content


def fix_file(filepath: Path) -> bool:
    """Fix syntax errors in a single file using targeted patterns."""
    try:
        # Read file content
        with open(filepath, "r", encoding="utf-8") as f:
            original_content = f.read()

        # Apply targeted fixes
        fixer = TargetedSyntaxFixer()
        fixed_content = fixer.fix_all_patterns(original_content, str(filepath))

        # Check if syntax is valid after fixes
        try:
            ast.parse(fixed_content)
            syntax_valid = True
        except SyntaxError:
            syntax_valid = False

        # Write back if we made improvements
        if fixed_content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            if syntax_valid:
                logger.info(f"SUCCESS: Fixed {filepath}")
                return True
            else:
                logger.warning(f"PARTIAL: {filepath} - improved but still has syntax errors")

        return syntax_valid

    except Exception as e:
        logger.error(f"ERROR processing {filepath}: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/targeted_syntax_fix.py <directory_or_file>")
        print("Example: python scripts/targeted_syntax_fix.py apps/ecosystemiser")
        sys.exit(1)

    target_path = Path(sys.argv[1])

    if not target_path.exists():
        logger.error(f"Path does not exist: {target_path}")
        sys.exit(1)

    # Collect Python files
    if target_path.is_file():
        python_files = [target_path]
    else:
        python_files = list(target_path.rglob("*.py"))

    logger.info(f"Processing {len(python_files)} Python files in {target_path}")

    # Process files
    fixed_count = 0
    total_count = len(python_files)

    for filepath in python_files:
        if fix_file(filepath):
            fixed_count += 1

    logger.info(f"Summary: {fixed_count}/{total_count} files successfully fixed")

    return 0 if fixed_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
