#!/usr/bin/env python3
"""
Code Red Stabilization Script
Systematically fixes all syntax errors in the Hive codebase.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


class CodeRedStabilizer:
    """Emergency codebase stabilization tool."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.error_count = 0
        self.fixed_count = 0
        self.error_files = []

    def scan_all_files(self) -> List[Tuple[Path, str]]:
        """Scan all Python files for syntax errors."""
        print("=" * 80)
        print("CODE RED: SCANNING FOR SYNTAX ERRORS")
        print("=" * 80)

        errors = []
        total_files = 0

        for directory in ["packages", "apps"]:
            dir_path = self.project_root / directory
            if dir_path.exists():
                for py_file in dir_path.rglob("*.py"):
                    # Skip migration files and __pycache__
                    if "__pycache__" in str(py_file) or "migration" in str(py_file):
                        continue

                    total_files += 1
                    error = self.check_syntax(py_file)
                    if error:
                        errors.append((py_file, error))
                        print(f"ERROR: {py_file.relative_to(self.project_root)}")
                        # Extract error details
                        if "line" in error:
                            line_match = re.search(r"line (\d+)", error)
                            if line_match:
                                print(f"   Line {line_match.group(1)}: {error.split('SyntaxError:')[-1].strip()}")

        print(f"\nTotal files scanned: {total_files}")
        print(f"Files with errors: {len(errors)}")
        return errors

    def check_syntax(self, file_path: Path) -> str:
        """Check if a file has syntax errors."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            compile(content, str(file_path), "exec")
            return None
        except SyntaxError as e:
            return f"line {e.lineno}: {e.msg}"
        except Exception as e:
            return str(e)

    def fix_common_patterns(self, content: str) -> str:
        """Fix common syntax error patterns."""
        original = content

        # Fix missing commas in multiline dicts
        # Pattern: "key": value\n    "nextkey":
        content = re.sub(r'("[\w_]+"\s*:\s*[^,\n}]+)(\n\s+"[\w_]+"\s*:)', r"\1,\2", content)

        # Fix missing commas in multiline lists
        # Pattern: item\n    item (where items don't end in comma)
        content = re.sub(r'([^,\[\{\(\n]+)(\n\s+["\'][\w_]+["\'])', r"\1,\2", content)

        # Fix missing commas in function parameters
        # Pattern: self\n    param:
        content = re.sub(r"(\bself\b)(\n\s+\w+\s*:)", r"\1,\2", content)

        # Fix missing commas after parameters with type hints
        # Pattern: param: Type\n    next_param:
        content = re.sub(r"(:\s*[\w\[\]|]+(?:\s*=\s*[^,\n)]+)?)(\n\s+\w+\s*:)", r"\1,\2", content)

        # Fix dict with extra comma after opening brace
        content = re.sub(r"\{\s*,", "{", content)

        # Fix missing commas in imports
        content = re.sub(r"from [\w.]+ import \(([\s\S]*?)\)", lambda m: self.fix_import_list(m.group(0)), content)

        return content

    def fix_import_list(self, import_str: str) -> str:
        """Fix missing commas in import statements."""
        # Extract the import list
        match = re.match(r"from ([\w.]+) import \(([\s\S]*?)\)", import_str)
        if not match:
            return import_str

        module = match.group(1)
        imports = match.group(2)

        # Split by newlines and clean
        lines = imports.strip().split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            line = line.strip()
            if line and not line.endswith(",") and i < len(lines) - 1:
                # Check if next line exists and isn't a closing paren
                if i + 1 < len(lines) and lines[i + 1].strip() and lines[i + 1].strip() != ")":
                    line += ","
            fixed_lines.append("    " + line if line else "")

        return f"from {module} import (\n{chr(10).join(fixed_lines)}\n)"

    def fix_file(self, file_path: Path) -> bool:
        """Fix syntax errors in a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original = content

            # Apply fixes
            content = self.fix_common_patterns(content)

            # Check if fixes worked
            try:
                compile(content, str(file_path), "exec")
                if content != original:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return True
            except SyntaxError:
                # Try more aggressive fixes
                content = self.aggressive_fix(content)
                try:
                    compile(content, str(file_path), "exec")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return True
                except:
                    pass

            return False
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")
            return False

    def aggressive_fix(self, content: str) -> str:
        """More aggressive fixes for stubborn syntax errors."""
        # Fix any line that ends with a value and next line starts with quotes
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            if i < len(lines) - 1:
                current_stripped = line.rstrip()
                next_line = lines[i + 1]

                # If current line doesn't end with comma/brace/bracket and next is a key
                if (
                    current_stripped
                    and not current_stripped.endswith((",", "{", "[", "(", ":", "\\"))
                    and re.match(r'\s*["\'][\w_]+["\']\s*:', next_line)
                ):
                    line = line.rstrip() + ","

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def run_stabilization(self):
        """Run the complete stabilization process."""
        print("\n*** CODE RED STABILIZATION INITIATED ***\n")

        # Phase 1: Scan for errors
        errors = self.scan_all_files()
        self.error_files = errors

        if not errors:
            print("\nSUCCESS: NO SYNTAX ERRORS FOUND!")
            return True

        # Phase 2: Attempt automatic fixes
        print("\n" + "=" * 80)
        print("ATTEMPTING AUTOMATIC FIXES")
        print("=" * 80)

        for file_path, error in errors:
            if self.fix_file(file_path):
                print(f"FIXED: {file_path.relative_to(self.project_root)}")
                self.fixed_count += 1
            else:
                print(f"FAILED: Could not auto-fix: {file_path.relative_to(self.project_root)}")
                print(f"   Error: {error}")

        # Phase 3: Re-scan to verify
        print("\n" + "=" * 80)
        print("VERIFICATION SCAN")
        print("=" * 80)

        remaining_errors = self.scan_all_files()

        # Summary
        print("\n" + "=" * 80)
        print("STABILIZATION REPORT")
        print("=" * 80)
        print(f"Initial errors: {len(errors)}")
        print(f"Files fixed: {self.fixed_count}")
        print(f"Remaining errors: {len(remaining_errors)}")

        if remaining_errors:
            print("\nWARNING: MANUAL INTERVENTION REQUIRED for:")
            for file_path, error in remaining_errors[:10]:  # Show first 10
                print(f"  - {file_path.relative_to(self.project_root)}")
                print(f"    {error}")

        return len(remaining_errors) == 0


def main():
    stabilizer = CodeRedStabilizer()
    success = stabilizer.run_stabilization()

    if success:
        print("\nSUCCESS: CODE RED RESOLVED - All syntax errors fixed!")
        sys.exit(0)
    else:
        print("\nWARNING: CODE RED CONTINUES - Manual fixes needed")
        sys.exit(1)


if __name__ == "__main__":
    main()
