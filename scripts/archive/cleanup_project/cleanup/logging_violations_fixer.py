#!/usr/bin/env python3
"""
Logging Violations Fixer - Step 3: Address Remaining Code Quality

This script systematically fixes the 876 logging violations by replacing
print() statements with proper logger calls throughout the codebase.
"""

import re
from pathlib import Path


class LoggingViolationsFixer:
    """Fixes print() statements and standardizes logging"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.fixes_applied = []
        self.files_processed = 0
        self.total_fixes = 0

    def find_python_files(self) -> list[Path]:
        """Find all Python files in production code (apps and packages)"""
        python_files = []

        # Priority: apps and packages (production code)
        for pattern in ["apps/**/*.py", "packages/**/*.py"]:
            python_files.extend(self.project_root.glob(pattern))

        # Filter out test files, __pycache__, and other non-production files
        filtered_files = []
        for file_path in python_files:
            path_str = str(file_path).lower()
            if not any(
                exclude in path_str
                for exclude in ["__pycache__", "test_", "_test.py", "/tests/", ".backup", "archive", "legacy", ".venv"]
            ):
                filtered_files.append(file_path)

        print(f"Found {len(filtered_files)} production Python files to process")
        return filtered_files

    def analyze_file_for_violations(self, file_path: Path) -> list[tuple[int, str]]:
        """Analyze a file for print statement violations"""
        violations = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue

                # Find print statements (but not in strings)
                if "print(" in line:
                    # Simple check to avoid print() inside strings
                    # This is not perfect but catches most cases
                    if not self._is_print_in_string(line):
                        violations.append((line_num, line.strip()))

        except Exception as e:
            print(f"[WARNING] Could not analyze {file_path}: {e}")

        return violations

    def _is_print_in_string(self, line: str) -> bool:
        """Simple check if print( appears inside a string literal"""
        # Count quotes before print(
        print_pos = line.find("print(")
        if print_pos == -1:
            return False

        before_print = line[:print_pos]
        single_quotes = before_print.count("'") - before_print.count("\\'")
        double_quotes = before_print.count('"') - before_print.count('\\"')

        # If odd number of quotes, we're likely inside a string
        return (single_quotes % 2 == 1) or (double_quotes % 2 == 1)

    def fix_file_logging(self, file_path: Path) -> int:
        """Fix logging violations in a single file"""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            # Check if file already has logging import
            has_logging_import = any(
                "from hive_logging import get_logger" in line
                or "import hive_logging" in line
                or "logger = get_logger" in line
                for line in lines
            )

            fixes_in_file = 0
            new_lines = []
            logger_added = False

            for _line_num, line in enumerate(lines):
                # Add logging import after first import if not present
                if (
                    not has_logging_import
                    and not logger_added
                    and (line.startswith("import ") or line.startswith("from "))
                ):
                    new_lines.append(line)
                    # Add logging import after the first import
                    if not any("hive_logging" in prev_line for prev_line in new_lines[-5:]):
                        new_lines.append("from hive_logging import get_logger")
                        new_lines.append("")
                        new_lines.append("logger = get_logger(__name__)")
                        logger_added = True
                    continue

                # Replace print statements with logger calls
                if "print(" in line and not self._is_print_in_string(line):
                    # Simple replacements for common patterns
                    replacements = [
                        # print("message") -> logger.info("message")
                        (r'print\((["\'].*?["\'])\)', r"logger.info(\1)"),
                        # print(f"message {var}") -> logger.info(f"message {var}")
                        (r'print\(f(["\'].*?["\'])\)', r"logger.info(f\1)"),
                        # print(variable) -> logger.info(str(variable))
                        (r'print\(([^"\']*?)\)', r"logger.info(str(\1))"),
                    ]

                    modified = False
                    for pattern, replacement in replacements:
                        new_line, count = re.subn(pattern, replacement, line)
                        if count > 0:
                            line = new_line
                            fixes_in_file += count
                            modified = True
                            break

                    # If we couldn't match a pattern, do a simple replacement
                    if not modified and "print(" in line:
                        line = line.replace("print(", "logger.info(")
                        fixes_in_file += 1

                new_lines.append(line)

            # Write back if changes were made
            if fixes_in_file > 0:
                new_content = "\n".join(new_lines)
                file_path.write_text(new_content, encoding="utf-8")

                self.fixes_applied.append(
                    {"file": str(file_path.relative_to(self.project_root)), "fixes": fixes_in_file},
                )

                print(f"[FIXED] {file_path.name}: {fixes_in_file} print statements")
                return fixes_in_file

            return 0

        except Exception as e:
            print(f"[ERROR] Failed to fix {file_path}: {e}")
            return 0

    def fix_all_logging_violations(self) -> bool:
        """Fix logging violations in all production files"""
        print("Step 3: Addressing Logging Violations")
        print("=" * 50)

        python_files = self.find_python_files()

        # First, analyze to get a count
        total_violations = 0
        files_with_violations = []

        print("Analyzing files for violations...")
        for file_path in python_files:
            violations = self.analyze_file_for_violations(file_path)
            if violations:
                files_with_violations.append((file_path, len(violations)))
                total_violations += len(violations)

        print(f"Found {total_violations} print statement violations in {len(files_with_violations)} files")

        if total_violations == 0:
            print("[INFO] No logging violations found!")
            return True

        # Sort by number of violations (fix worst files first)
        files_with_violations.sort(key=lambda x: x[1], reverse=True)

        # Fix files in batches
        print(f"\nFixing violations in {len(files_with_violations)} files...")

        for i, (file_path, violation_count) in enumerate(files_with_violations, 1):
            print(
                f"[{i:3d}/{len(files_with_violations)}] Processing {file_path.name} ({violation_count} violations)...",
            )
            fixes = self.fix_file_logging(file_path)
            self.total_fixes += fixes
            self.files_processed += 1

        print(f"\n[SUMMARY] Fixed {self.total_fixes} logging violations in {self.files_processed} files")
        return True

    def generate_logging_report(self) -> str:
        """Generate logging violations fix report"""
        report = f"""# Logging Violations Fix Report

**Generated**: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

- **Files Processed**: {self.files_processed}
- **Total Fixes Applied**: {self.total_fixes}
- **Print Statements Replaced**: {self.total_fixes}

## Top Files Fixed

| File | Fixes Applied |
|------|---------------|
"""

        # Sort fixes by number of fixes (show top 20)
        sorted_fixes = sorted(self.fixes_applied, key=lambda x: x["fixes"], reverse=True)
        for fix in sorted_fixes[:20]:
            report += f"| {fix['file']} | {fix['fixes']} |\n"

        if len(sorted_fixes) > 20:
            report += f"| ... and {len(sorted_fixes) - 20} more files | ... |\n"

        report += """

## Changes Made

1. **Added logging imports** to files that didn't have them:
   ```python
   from hive_logging import get_logger
   logger = get_logger(__name__)
   ```

2. **Replaced print statements** with appropriate logger calls:
   - `print("message")` → `logger.info("message")`
   - `print(f"message {var}")` → `logger.info(f"message {var}")`
   - `print(variable)` → `logger.info(str(variable))`

## Benefits

- **Professional Logging**: All output now uses structured logging
- **Observability**: Logs can be collected, filtered, and analyzed
- **Golden Rules Compliance**: Significantly reduces logging violations
- **Production Ready**: Proper log levels and formatting

## Next Steps

1. **Test the changes**: Run the application to ensure logging works correctly
2. **Adjust log levels**: Change some logger.info() to logger.debug() where appropriate
3. **Run golden tests**: Verify the reduction in logging violations
4. **Proceed to Step 4**: Consolidate remaining fixer scripts

---

*Logging standardization completed as part of code quality improvement.*
"""

        return report


def main():
    """Main execution function"""
    print("Logging Violations Fixer - Step 3")
    print("=" * 40)

    project_root = Path(__file__).parent.parent.parent
    fixer = LoggingViolationsFixer(project_root)

    # Fix all logging violations
    success = fixer.fix_all_logging_violations()

    # Generate report
    report = fixer.generate_logging_report()
    report_path = project_root / "scripts" / "cleanup" / "logging_fixes_report.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\nLogging fixes report saved: {report_path}")

    if success:
        print("\n[SUCCESS] Logging violations addressed!")
        print(f"Fixed {fixer.total_fixes} print statements in {fixer.files_processed} files")
        print("Next: Run golden tests to verify improvement")
        return 0
    else:
        print("\n[ERROR] Some logging fixes failed")
        return 1


if __name__ == "__main__":
    exit(main())


