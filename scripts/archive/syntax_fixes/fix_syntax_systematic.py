#!/usr/bin/env python3
"""
Systematic syntax error fixer for Hive platform.
Addresses the most common syntax patterns causing errors.
"""

import ast
import re
import sys
from pathlib import Path
from typing import Tuple

from hive_logging import get_logger

logger = get_logger(__name__)


class SyntaxFixer:
    """Systematic syntax error fixing with pattern detection."""

    def __init__(self):
        self.fixes_applied = 0
        self.files_processed = 0

    def fix_missing_commas_in_imports(self, content: str) -> str:
        """Fix missing commas in import statements."""
        patterns = [
            # from module import (item1 item2) -> from module import (item1, item2)
            (r"from\s+[\w.]+\s+import\s*\(\s*([^)]+)\)", self._fix_import_list),
            # import statement with missing commas
            (r"import\s+([^;\n]+)", self._fix_import_simple),
        ]

        for pattern, fixer in patterns:
            content = re.sub(pattern, fixer, content, flags=re.MULTILINE)

        return content

    def _fix_import_list(self, match) -> str:
        """Fix comma-separated import list."""
        import_list = match.group(1).strip()
        if "," not in import_list and "\n" in import_list:
            # Split on whitespace/newlines and add commas
            items = [item.strip() for item in re.split(r"[\s\n]+", import_list) if item.strip()]
            if len(items) > 1:
                import_list = ",\n    ".join(items)
                self.fixes_applied += 1

        return f"from {match.group(0).split('import')[0].split('from')[1].strip()} import (\n    {import_list},\n)"

    def _fix_import_simple(self, match) -> str:
        """Fix simple import statements."""
        return match.group(0)  # Leave simple imports as-is for now

    def fix_missing_commas_in_dicts(self, content: str) -> str:
        """Fix missing commas in dictionary definitions."""
        # Pattern for dictionary entries missing commas
        pattern = r'(["\'][\w_]+["\']\s*:\s*[^,}\n]+)(\s+["\'][\w_]+["\']\s*:)'

        def add_comma(match):
            self.fixes_applied += 1
            return match.group(1) + "," + match.group(2)

        return re.sub(pattern, add_comma, content, flags=re.MULTILINE)

    def fix_missing_commas_in_calls(self, content: str) -> str:
        """Fix missing commas in function calls."""
        # Pattern for function call arguments missing commas
        pattern = r"(\w+\s*=\s*[^,\n)]+)(\s+\w+\s*=)"

        def add_comma(match):
            self.fixes_applied += 1
            return match.group(1) + "," + match.group(2)

        return re.sub(pattern, add_comma, content, flags=re.MULTILINE)

    def fix_incomplete_statements(self, content: str) -> str:
        """Fix incomplete statements that are just identifiers."""
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if line is just an identifier (potential incomplete import/statement)
            if stripped and stripped.isidentifier() and i > 0 and ("import" in lines[i - 1] or "from" in lines[i - 1]):

                # This might be a continuation of an import - check context
                if i > 0 and ("import" in lines[i - 1] or "," in lines[i - 1]):
                    # Add comma to previous line if missing
                    if not lines[i - 1].rstrip().endswith(","):
                        lines[i - 1] = lines[i - 1].rstrip() + ","
                        self.fixes_applied += 1

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def check_and_fix_file(self, filepath: Path) -> Tuple[bool, str]:
        """Check and fix a single file."""
        try:
            # Read original content
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                original_content = f.read()

            # Try parsing original - if it works, no fix needed
            try:
                ast.parse(original_content, filename=str(filepath))
                return True, "Already valid"
            except SyntaxError:
                pass  # Continue with fixing

            # Apply fixes
            content = original_content
            content = self.fix_missing_commas_in_imports(content)
            content = self.fix_missing_commas_in_dicts(content)
            content = self.fix_missing_commas_in_calls(content)
            content = self.fix_incomplete_statements(content)

            # Test if fixes worked
            try:
                ast.parse(content, filename=str(filepath))

                # Only write if we made changes
                if content != original_content:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    return True, f"Fixed ({self.fixes_applied} changes)"
                else:
                    return False, "No automatic fix available"

            except SyntaxError as e:
                return False, f"Fix failed - still has syntax error: {e.msg}"

        except Exception as e:
            return False, f"Error processing file: {e}"

    def fix_directory(self, directory: Path, pattern: str = "**/*.py") -> None:
        """Fix all Python files in directory matching pattern."""
        files = list(directory.glob(pattern))
        logger.info(f"Found {len(files)} Python files to check")

        fixed_count = 0
        failed_files = []

        for filepath in files:
            self.files_processed += 1
            success, message = self.check_and_fix_file(filepath)

            if success:
                if "Fixed" in message:
                    fixed_count += 1
                    logger.info(f"FIXED: {filepath.relative_to(directory)}: {message}")
                else:
                    logger.debug(f"OK: {filepath.relative_to(directory)}: {message}")
            else:
                failed_files.append((filepath, message))
                logger.warning(f"FAILED: {filepath.relative_to(directory)}: {message}")

        logger.info(f"Summary: {fixed_count} files fixed, {len(failed_files)} still have errors")

        if failed_files:
            logger.info("Files still needing manual attention:")
            for filepath, message in failed_files[:10]:  # Show first 10
                logger.info(f"  {filepath.relative_to(directory)}: {message}")
            if len(failed_files) > 10:
                logger.info(f"  ... and {len(failed_files) - 10} more")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/fix_syntax_systematic.py <directory_or_file>")
        sys.exit(1)

    target = Path(sys.argv[1])
    fixer = SyntaxFixer()

    if target.is_file():
        success, message = fixer.check_and_fix_file(target)
        print(f"{'FIXED' if success else 'FAILED'}: {target}: {message}")
        sys.exit(0 if success else 1)
    elif target.is_dir():
        fixer.fix_directory(target)
        print(f"Processed {fixer.files_processed} files, applied {fixer.fixes_applied} fixes total")
    else:
        print(f"ERROR: {target} is not a valid file or directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
