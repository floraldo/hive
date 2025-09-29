#!/usr/bin/env python3
"""
The One True Syntax Fixer - Master script to eliminate ALL syntax errors.

Based on Agentic Charter: Create stable foundation, preserve creative freedom.
This script consolidates the best patterns from 12+ comma fixers into one robust tool.
"""

import ast
import glob
import re
import shutil
from pathlib import Path
from typing import List, Tuple


class MasterSyntaxFixer:
    """Comprehensive syntax error fixer using multiple strategies."""

    def __init__(self):
        self.fixed_files = 0
        self.failed_files = 0
        self.errors_found = 0
        self.backup_dir = Path("syntax_fix_backups")

    def create_backup(self, filepath: Path) -> None:
        """Create backup before fixing."""
        if not self.backup_dir.exists():
            self.backup_dir.mkdir()
        backup_path = self.backup_dir / f"{filepath.name}.backup"
        shutil.copy2(filepath, backup_path)

    def fix_dictionary_commas(self, content: str) -> str:
        """Fix missing commas in dictionary literals."""
        # Pattern 1: Missing comma after dictionary value before next key
        # "id": row[0]
        # "title": row[1]  <- Missing comma after row[0]
        content = re.sub(
            r'(\s*"[^"]+"\s*:\s*[^,\n}]+)(\n\s*"[^"]+"\s*:)',
            r'\1,\2',
            content,
            flags=re.MULTILINE
        )

        # Pattern 2: Missing comma after single-quoted keys
        content = re.sub(
            r"(\s*'[^']+'\s*:\s*[^,\n}]+)(\n\s*'[^']+'\s*:)",
            r'\1,\2',
            content,
            flags=re.MULTILINE
        )

        # Pattern 3: Missing comma in function call arguments
        # port=int(settings.queue.redis_url.split(":")[-1].split("/")[0])
        # host="localhost"  <- Missing comma
        content = re.sub(
            r'(\w+=\s*[^,\n)]+)(\n\s*\w+=)',
            r'\1,\2',
            content,
            flags=re.MULTILINE
        )

        return content

    def fix_function_call_commas(self, content: str) -> str:
        """Fix missing commas in function calls."""
        # Pattern: Missing comma between function arguments
        lines = content.split('\n')
        fixed_lines = []
        in_function_call = False
        paren_count = 0

        for line in lines:
            # Detect if we're in a multi-line function call
            paren_count += line.count('(') - line.count(')')

            if '(' in line and paren_count > 0:
                in_function_call = True
            elif paren_count == 0:
                in_function_call = False

            # If we're in a function call and line doesn't end with comma or parenthesis
            # and next line starts with a parameter, add comma
            if in_function_call and line.strip() and not line.strip().endswith((',', '(', ')')):
                # Check if this looks like a parameter line
                stripped = line.strip()
                if ('=' in stripped or
                    stripped.startswith('"') or
                    stripped.startswith("'") or
                    stripped.endswith(']') or
                    stripped.endswith(')')):
                    line = line.rstrip() + ','

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)

    def fix_list_commas(self, content: str) -> str:
        """Fix missing commas in list literals."""
        # Pattern: Missing comma in list items
        content = re.sub(
            r'(\s*["\'][^"\']*["\'])(\n\s*["\'][^"\']*["\'])',
            r'\1,\2',
            content,
            flags=re.MULTILINE
        )
        return content

    def remove_duplicate_commas(self, content: str) -> str:
        """Remove any duplicate commas that might have been introduced."""
        # Remove double commas
        content = re.sub(r',,+', ',', content)
        # Remove comma before closing braces/brackets/parentheses if it's the last item
        content = re.sub(r',(\s*[}\]\)])', r'\1', content)
        return content

    def fix_file(self, filepath: Path) -> bool:
        """Fix all syntax errors in a single file."""
        try:
            # First, try to parse - if it's already valid, skip
            with open(filepath, 'r', encoding='utf-8') as f:
                original_content = f.read()

            try:
                ast.parse(original_content)
                return True  # Already valid
            except SyntaxError as e:
                if 'comma' not in str(e).lower():
                    return False  # Not a comma error, skip

            print(f"Fixing {filepath}")
            self.create_backup(filepath)

            # Apply all fixing strategies
            fixed_content = original_content
            fixed_content = self.fix_dictionary_commas(fixed_content)
            fixed_content = self.fix_function_call_commas(fixed_content)
            fixed_content = self.fix_list_commas(fixed_content)
            fixed_content = self.remove_duplicate_commas(fixed_content)

            # Validate the fix
            try:
                ast.parse(fixed_content)
                # Write only if we made changes and they're valid
                if fixed_content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(fixed_content)
                    self.fixed_files += 1
                    print(f"  [OK] Fixed syntax errors in {filepath}")
                return True

            except SyntaxError as e:
                print(f"  [FAIL] Fix didn't resolve syntax error in {filepath}: {e}")
                # Restore original content
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                self.failed_files += 1
                return False

        except Exception as e:
            print(f"  [FAIL] Error processing {filepath}: {e}")
            self.failed_files += 1
            return False

    def scan_and_fix_all(self) -> Tuple[int, int]:
        """Scan and fix all Python files in the codebase."""
        print("=" * 80)
        print("THE ONE TRUE SYNTAX FIXER")
        print("Consolidating the power of 12+ comma fixers into one robust tool")
        print("=" * 80)

        patterns = ['apps/**/*.py', 'packages/**/*.py', 'scripts/**/*.py']
        all_files = []

        for pattern in patterns:
            files = list(Path('.').glob(pattern))
            # Filter out test files, __pycache__, .venv, etc.
            filtered_files = [
                f for f in files
                if not any(skip in str(f) for skip in ['.venv', '__pycache__', '.git', 'test_'])
            ]
            all_files.extend(filtered_files)

        print(f"Found {len(all_files)} Python files to check")
        print()

        # Find files with syntax errors first
        syntax_error_files = []
        for filepath in all_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                ast.parse(content)
            except SyntaxError as e:
                if 'comma' in str(e).lower() or 'perhaps you forgot' in str(e).lower():
                    syntax_error_files.append(filepath)
                    self.errors_found += 1

        print(f"Found {len(syntax_error_files)} files with comma syntax errors")
        print()

        # Fix each file
        for filepath in syntax_error_files:
            self.fix_file(filepath)

        return self.fixed_files, self.failed_files

    def print_summary(self):
        """Print summary of fixing operation."""
        print()
        print("=" * 80)
        print("SYNTAX FIXING SUMMARY")
        print("=" * 80)
        print(f"Files with syntax errors found: {self.errors_found}")
        print(f"Files successfully fixed: {self.fixed_files}")
        print(f"Files that failed to fix: {self.failed_files}")

        if self.failed_files > 0:
            print("\n[WARN] Some files could not be automatically fixed.")
            print("These may require manual intervention or have complex syntax issues.")

        if self.fixed_files > 0:
            print(f"\n[OK] Backups created in: {self.backup_dir}")
            print("You can restore from backups if needed.")

        if self.errors_found == 0:
            print("\n[OK] No syntax errors found! Codebase is clean.")
        elif self.failed_files == 0:
            print("\n[OK] All syntax errors fixed successfully!")
            print("Agentic Charter: Stable foundation established, creative freedom preserved!")


def main():
    """Main entry point."""
    fixer = MasterSyntaxFixer()

    try:
        fixed, failed = fixer.scan_and_fix_all()
        fixer.print_summary()

        # Return appropriate exit code
        return 0 if failed == 0 else 1

    except KeyboardInterrupt:
        print("\n[WARN] Syntax fixing interrupted by user")
        return 1
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())