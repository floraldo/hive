#!/usr/bin/env python3
"""
Aggressive syntax error fixer using AST parsing and line-by-line analysis.
"""

import re
import sys
from pathlib import Path
from typing import List


class AggressiveFixer:
    """More aggressive syntax fixing strategies."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent

    def fix_file(self, file_path: Path) -> bool:
        """Aggressively fix syntax errors in a file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            fixed_lines = self.fix_lines(lines)

            # Try to compile
            try:
                compile("".join(fixed_lines), str(file_path), "exec")
                # Write back if successful
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(fixed_lines)
                return True
            except SyntaxError:
                return False

        except Exception:
            return False

    def fix_lines(self, lines: List[str]) -> List[str]:
        """Fix common syntax issues line by line."""
        fixed_lines = []

        for i, line in enumerate(lines):
            # Get previous and next lines for context
            prev_line = lines[i - 1] if i > 0 else ""
            next_line = lines[i + 1] if i < len(lines) - 1 else ""

            fixed_line = line

            # Fix missing commas in function definitions
            if i > 0 and re.match(r"\s+\w+\s*:", line) and not prev_line.rstrip().endswith(","):
                if "def " in prev_line or "class " in prev_line:
                    # It's a function/class definition, don't add comma
                    pass
                elif prev_line.strip() and not prev_line.rstrip().endswith((":", "{", "[", "(", ",")):
                    # Add comma to previous line
                    if fixed_lines:
                        fixed_lines[-1] = fixed_lines[-1].rstrip() + ",\n"

            # Fix missing commas in dict/list items
            if (
                re.match(r'\s*["\'][\w_]+["\']\s*:', line)
                and i > 0
                and prev_line.strip()
                and not prev_line.rstrip().endswith((",", "{", "[", "("))
            ):
                # Add comma to previous line if it's a value
                if fixed_lines and not prev_line.strip().startswith("#"):
                    fixed_lines[-1] = fixed_lines[-1].rstrip() + ",\n"

            # Fix dict with comma after opening brace
            fixed_line = re.sub(r"(\{)\s*,", r"\1", fixed_line)

            # Fix missing commas in imports
            if "from " in line and " import (" in line:
                # Mark for multiline import fixing
                fixed_line = self.fix_multiline_import(lines, i)
                if fixed_line != line:
                    # Skip the lines that were part of the import
                    pass

            fixed_lines.append(fixed_line)

        return fixed_lines

    def fix_multiline_import(self, lines: List[str], start_idx: int) -> str:
        """Fix multiline import statements."""
        import_lines = [lines[start_idx]]
        i = start_idx + 1

        # Collect all lines of the import
        while i < len(lines) and ")" not in lines[i - 1]:
            import_lines.append(lines[i])
            i += 1

        # Fix missing commas
        fixed_import = []
        for j, line in enumerate(import_lines):
            if j < len(import_lines) - 1 and line.strip() and not line.rstrip().endswith(","):
                if ")" not in import_lines[j + 1]:
                    line = line.rstrip() + ",\n"
            fixed_import.append(line)

        return fixed_import[0]  # Return first line, rest will be handled

    def batch_fix(self, error_files: List[Path]) -> int:
        """Fix multiple files."""
        fixed_count = 0
        for file_path in error_files:
            if self.fix_file(file_path):
                print(f"FIXED: {file_path.relative_to(self.project_root)}")
                fixed_count += 1
            else:
                print(f"FAILED: {file_path.relative_to(self.project_root)}")
        return fixed_count


def main():
    """Find and fix syntax errors aggressively."""
    fixer = AggressiveFixer()

    # Get list of files with errors
    error_files = []
    for directory in ["packages", "apps"]:
        dir_path = fixer.project_root / directory
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        compile(f.read(), str(py_file), "exec")
                except SyntaxError:
                    error_files.append(py_file)
                except:
                    pass

    print(f"Found {len(error_files)} files with syntax errors")
    print("Applying aggressive fixes...")

    fixed_count = fixer.batch_fix(error_files)

    print(f"\nFixed {fixed_count} out of {len(error_files)} files")

    if fixed_count < len(error_files):
        print("\nRemaining files need manual intervention")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
