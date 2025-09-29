#!/usr/bin/env python3
"""
Batch syntax error fixer for the Hive platform.
Handles the most common syntax patterns causing build failures.
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Set

from hive_logging import get_logger

logger = get_logger(__name__)


class BatchSyntaxFixer:
    """Comprehensive syntax error fixer with pattern matching."""

    def __init__(self):
        self.files_fixed = 0
        self.files_failed = 0
        self.total_fixes = 0

    def apply_all_fixes(self, content: str, filepath: str) -> str:
        """Apply all known fix patterns to content."""
        original_content = content

        # Fix 1: Missing commas in import statements
        content = self.fix_import_commas(content)

        # Fix 2: Missing commas in function calls
        content = self.fix_function_call_commas(content)

        # Fix 3: Misplaced __future__ imports
        content = self.fix_future_imports(content)

        # Fix 4: Missing commas in dictionary/list definitions
        content = self.fix_container_commas(content)

        # Fix 5: Incomplete identifier lines (common in malformed imports)
        content = self.fix_incomplete_lines(content)

        # Fix 6: Common typing imports
        content = self.fix_typing_imports(content)

        if content != original_content:
            self.total_fixes += 1

        return content

    def fix_import_commas(self, content: str) -> str:
        """Fix missing commas in import statements."""
        lines = content.split('\n')
        fixed_lines = []
        in_import_block = False
        import_lines = []

        for line in lines:
            stripped = line.strip()

            # Start of multi-line import
            if ('from ' in line and 'import (' in line) or (line.strip().endswith('import (')):
                in_import_block = True
                import_lines = [line]
                continue

            # Inside import block
            if in_import_block:
                if ')' in line:
                    # End of import block
                    import_lines.append(line)
                    fixed_import = self._fix_import_block(import_lines)
                    fixed_lines.extend(fixed_import)
                    in_import_block = False
                    import_lines = []
                else:
                    import_lines.append(line)
                continue

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)

    def _fix_import_block(self, import_lines: List[str]) -> List[str]:
        """Fix a multi-line import block."""
        if len(import_lines) < 2:
            return import_lines

        # Extract imports between ( and )
        full_text = '\n'.join(import_lines)
        match = re.search(r'import\s*\((.*?)\)', full_text, re.DOTALL)
        if not match:
            return import_lines

        imports_text = match.group(1).strip()
        if not imports_text:
            return import_lines

        # Split and clean import items
        import_items = []
        for line in imports_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # Remove existing comma and add to list
                line = line.rstrip(',').strip()
                if line:
                    import_items.append(line)

        if len(import_items) <= 1:
            return import_lines

        # Reconstruct with proper commas
        header = import_lines[0].split('(')[0] + '('
        footer = ')' if import_lines[-1].strip().endswith(')') else import_lines[-1]

        result = [header]
        for item in import_items[:-1]:
            result.append(f'    {item},')
        result.append(f'    {import_items[-1]},')  # Trailing comma
        result.append(footer)

        return result

    def fix_function_call_commas(self, content: str) -> str:
        """Fix missing commas in function calls."""
        # Pattern for function calls with missing commas
        # Look for parameter=value followed by parameter=value without comma
        pattern = r'(\w+\s*=\s*[^,\n)]+)(\s+)(\w+\s*=)'

        def add_comma(match):
            return match.group(1) + ',' + match.group(2) + match.group(3)

        return re.sub(pattern, add_comma, content, flags=re.MULTILINE)

    def fix_future_imports(self, content: str) -> str:
        """Move __future__ imports to the top of the file."""
        lines = content.split('\n')
        future_imports = []
        other_lines = []
        docstring_done = False
        first_import_seen = False

        for line in lines:
            stripped = line.strip()

            if 'from __future__ import' in line:
                if stripped not in [fi.strip() for fi in future_imports]:
                    future_imports.append(line)
                continue

            # Skip if it's just whitespace/comments at the top
            if not stripped or stripped.startswith('#'):
                other_lines.append(line)
                continue

            # Handle docstrings
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_done = True

            other_lines.append(line)

        # Reconstruct with __future__ imports at top (after docstring)
        if future_imports:
            result_lines = []
            docstring_lines = []
            code_lines = []
            in_docstring = False

            for line in other_lines:
                stripped = line.strip()
                if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                    in_docstring = True
                    docstring_lines.append(line)
                elif in_docstring:
                    docstring_lines.append(line)
                    if stripped.endswith('"""') or stripped.endswith("'''"):
                        in_docstring = False
                        # Add empty line after docstring
                        if not line.strip():
                            pass  # Already empty
                        else:
                            docstring_lines.append('')
                else:
                    code_lines.append(line)

            result_lines.extend(docstring_lines)
            result_lines.extend(future_imports)
            if future_imports and code_lines:
                result_lines.append('')  # Empty line after future imports
            result_lines.extend(code_lines)

            return '\n'.join(result_lines)

        return content

    def fix_container_commas(self, content: str) -> str:
        """Fix missing commas in dictionaries and lists."""
        # Pattern for dict entries: "key": value followed by "key":
        dict_pattern = r'(["\'][\w_]+["\']\s*:\s*[^,}\n]+)(\s+["\'][\w_]+["\']\s*:)'

        def add_dict_comma(match):
            return match.group(1) + ',' + match.group(2)

        return re.sub(dict_pattern, add_dict_comma, content, flags=re.MULTILINE)

    def fix_incomplete_lines(self, content: str) -> str:
        """Fix incomplete lines that are just identifiers."""
        lines = content.split('\n')
        fixed_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if line is just an identifier
            if (stripped and
                stripped.replace('_', 'a').replace('0', 'a').replace('1', 'a').replace('2', 'a').replace('3', 'a').replace('4', 'a').replace('5', 'a').replace('6', 'a').replace('7', 'a').replace('8', 'a').replace('9', 'a').isidentifier() and
                i > 0):

                prev_line = lines[i-1].strip()

                # This might be a continuation of an import or call
                if ('import' in prev_line or
                    prev_line.endswith('(') or
                    prev_line.endswith(',')):
                    # Add comma to previous line if missing
                    if not prev_line.endswith(',') and not prev_line.endswith('('):
                        fixed_lines[-1] = fixed_lines[-1].rstrip() + ','

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)

    def fix_typing_imports(self, content: str) -> str:
        """Fix common typing import issues."""
        # Fix ListTuple -> List, Tuple
        content = re.sub(r'\bListTuple\b', 'List, Tuple', content)

        # Fix DictList -> Dict, List
        content = re.sub(r'\bDictList\b', 'Dict, List', content)

        return content

    def fix_file(self, filepath: Path) -> bool:
        """Fix a single file and return whether it was successful."""
        try:
            # Read original content
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                original_content = f.read()

            # Check if already valid
            try:
                ast.parse(original_content, filename=str(filepath))
                logger.debug(f"SKIP: {filepath} - already valid")
                return True
            except SyntaxError:
                pass  # Continue with fixing

            # Apply fixes
            fixed_content = self.apply_all_fixes(original_content, str(filepath))

            # Test if fixes worked
            try:
                ast.parse(fixed_content, filename=str(filepath))

                # Only write if content changed
                if fixed_content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(fixed_content)
                    logger.info(f"FIXED: {filepath}")
                    self.files_fixed += 1
                    return True
                else:
                    logger.debug(f"SKIP: {filepath} - no changes needed")
                    return True

            except SyntaxError as e:
                logger.warning(f"FAILED: {filepath} - still has syntax error: {e.msg}")
                self.files_failed += 1
                return False

        except Exception as e:
            logger.error(f"ERROR: {filepath} - {e}")
            self.files_failed += 1
            return False

    def fix_directory(self, directory: Path, pattern: str = "**/*.py") -> None:
        """Fix all Python files in directory."""
        files = list(directory.glob(pattern))
        logger.info(f"Processing {len(files)} Python files in {directory}")

        for filepath in files:
            self.fix_file(filepath)

        logger.info(f"Summary: {self.files_fixed} fixed, {self.files_failed} failed, {self.total_fixes} total changes")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/batch_syntax_fix.py <directory_or_file>")
        print("Example: python scripts/batch_syntax_fix.py apps/ecosystemiser")
        sys.exit(1)

    target = Path(sys.argv[1])
    fixer = BatchSyntaxFixer()

    if target.is_file():
        success = fixer.fix_file(target)
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
        sys.exit(0 if success else 1)
    elif target.is_dir():
        fixer.fix_directory(target)
        print(f"Fixed {fixer.files_fixed} files, {fixer.files_failed} failures")
        sys.exit(0 if fixer.files_failed == 0 else 1)
    else:
        print(f"ERROR: {target} not found")
        sys.exit(1)


if __name__ == "__main__":
    main()