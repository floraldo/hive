#!/usr/bin/env python
"""
SAFE version of print statement fixer with dry-run and backup capabilities.

Features:
1. Dry-run mode by default
2. Creates backups before modifying
3. Validates syntax before and after
4. Detailed reporting
"""

import re
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple


def is_test_file(filepath: Path) -> bool:
    """Check if file is a test file."""
    path_str = str(filepath).replace("\\", "/")
    return (
        "test" in filepath.parts
        or filepath.name.startswith("test_")
        or filepath.name.endswith("_test.py")
        or "/tests/" in path_str
        or "/test/" in path_str
    )


def validate_syntax(content: str, filepath: str = "<string>") -> bool:
    """Validate Python syntax."""
    try:
        compile(content, filepath, "exec")
        return True
    except SyntaxError:
        return False


def analyze_print_statement(line: str) -> Optional[Tuple[str, str, str]]:
    """Analyze a print statement and return indent, content, and log level."""
    match = re.match(r"(\s*)print\s*\((.*)\)", line)
    if not match:
        return None

    indent = match.group(1)
    content = match.group(2).strip()

    # Determine log level based on content
    log_level = "info"
    if "error" in content.lower() or "fail" in content.lower():
        log_level = "error"
    elif "warn" in content.lower():
        log_level = "warning"
    elif "debug" in content.lower():
        log_level = "debug"

    return indent, content, log_level


def fix_print_statements_safe(filepath: Path, dry_run: bool = True, backup: bool = True) -> Tuple[bool, str]:
    """
    Fix print statements in a file safely.

    Returns:
        (success, message)
    """
    if is_test_file(filepath):
        return False, "Test file - skipped"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original_content = f.read()
    except Exception as e:
        return False, f"Error reading: {e}"

    # Skip if no print statements
    if "print(" not in original_content:
        return False, "No print statements found"

    # Validate original syntax
    if not validate_syntax(original_content, str(filepath)):
        return False, "Original file has syntax errors - skipping"

    # Create backup if requested
    if not dry_run and backup:
        backup_path = filepath.with_suffix(".py.bak")
        try:
            shutil.copy2(filepath, backup_path)
        except Exception as e:
            return False, f"Failed to create backup: {e}"

    # Check existing imports
    has_logger_import = "from hive_logging import get_logger" in original_content
    has_logger_init = "logger = get_logger(__name__)" in original_content

    lines = original_content.split("\n")
    new_lines = []
    modified = False
    changes = []

    # Process each line
    for line_num, line in enumerate(lines, 1):
        # Skip comment lines
        stripped = line.strip()
        if stripped.startswith("#"):
            new_lines.append(line)
            continue

        # Look for print statements
        if re.match(r"\s*print\s*\(", line):
            analysis = analyze_print_statement(line)
            if analysis:
                indent, content, log_level = analysis
                new_line = f"{indent}logger.{log_level}({content})"
                new_lines.append(new_line)
                changes.append(f"  Line {line_num}: print() → logger.{log_level}()")
                modified = True
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if not modified:
        return False, "No valid print statements to fix"

    # Add imports if needed
    if not has_logger_import:
        # Find import position
        import_index = 0
        has_docstring = False

        for i, line in enumerate(new_lines):
            if i == 0 and (line.startswith('"""') or line.startswith("'''")):
                has_docstring = True
            if has_docstring and (line.endswith('"""') or line.endswith("'''")):
                import_index = i + 1
                break
            if line.startswith("import ") or line.startswith("from "):
                import_index = i + 1

        # Add imports
        new_lines.insert(import_index, "from hive_logging import get_logger")
        if not has_logger_init:
            new_lines.insert(import_index + 1, "logger = get_logger(__name__)")
            new_lines.insert(import_index + 2, "")

    new_content = "\n".join(new_lines)

    # Validate new syntax
    if not validate_syntax(new_content, str(filepath)):
        return False, "Modified file would have syntax errors - aborting"

    # Report changes
    change_report = "\n".join(changes)

    # Apply changes if not dry run
    if not dry_run:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True, f"Fixed {len(changes)} print statements:\n{change_report}"
        except Exception as e:
            return False, f"Error writing file: {e}"
    else:
        return True, f"Would fix {len(changes)} print statements:\n{change_report}"


def main():
    """Main function with safety features."""
    # Parse arguments
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv or len(sys.argv) == 1
    no_backup = "--no-backup" in sys.argv
    specific_file = None

    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            specific_file = Path(arg)
            break

    if dry_run:
        print("=" * 70)
        print("DRY RUN MODE - No files will be modified")
        print("To apply changes, run with: python safe_fix_print_statements.py --apply")
        print("=" * 70)
    else:
        print("=" * 70)
        print("LIVE MODE - Files will be modified")
        if not no_backup:
            print("Backups will be created with .bak extension")
        print("=" * 70)

    base_path = Path("C:/git/hive")

    # Process specific file or scan directories
    if specific_file:
        files_to_process = [specific_file] if specific_file.exists() else []
    else:
        dirs_to_process = [base_path / "apps", base_path / "packages"]

        files_to_process = []
        for dir_path in dirs_to_process:
            if dir_path.exists():
                files_to_process.extend(dir_path.rglob("*.py"))

    # Analyze files
    print(f"\nAnalyzing {len(files_to_process)} Python files...")

    fixable = []
    skipped = []
    errors = []

    for filepath in files_to_process:
        if is_test_file(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                if "print(" in content:
                    if validate_syntax(content, str(filepath)):
                        # Count actual print statements
                        count = len([l for l in content.split("\n") if re.match(r"\s*print\s*\(", l)])
                        if count > 0:
                            fixable.append((filepath, count))
                    else:
                        errors.append(filepath)
        except Exception:
            pass

    # Report findings
    print(f"\nFound {len(fixable)} files with print statements")
    print(f"Skipped {len(errors)} files with existing syntax errors")

    if not fixable:
        print("No files to fix!")
        return

    # Show sample
    print("\nFiles to process (showing first 10):")
    for filepath, count in fixable[:10]:
        rel_path = filepath.relative_to(base_path) if filepath.is_relative_to(base_path) else filepath
        print(f"  {rel_path}: {count} print statement(s)")

    if len(fixable) > 10:
        print(f"  ... and {len(fixable) - 10} more files")

    total_prints = sum(count for _, count in fixable)
    print(f"\nTotal print statements to fix: {total_prints}")

    if not dry_run:
        # Confirm before proceeding
        response = input(f"\nProceed with fixing {len(fixable)} files? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            return

    # Process files
    print("\n" + "=" * 70)
    success_count = 0
    fail_count = 0

    for filepath, _ in fixable:
        rel_path = filepath.relative_to(base_path) if filepath.is_relative_to(base_path) else filepath
        success, message = fix_print_statements_safe(filepath, dry_run, not no_backup)

        if success:
            if dry_run:
                print(f"[OK] {rel_path}")
            else:
                print(f"[FIXED] {rel_path}")
            success_count += 1
        else:
            if "No valid print statements" not in message:
                print(f"[FAIL] {rel_path} - {message}")
                fail_count += 1

    # Summary
    print("\n" + "=" * 70)
    if dry_run:
        print(f"Dry run complete: {success_count} files would be fixed")
        print("Run with --apply to actually fix the files")
    else:
        print(f"Complete: {success_count} files fixed")
        if fail_count:
            print(f"Failed: {fail_count} files")


if __name__ == "__main__":
    # Handle --apply flag as opposite of dry-run
    if "--apply" in sys.argv:
        sys.argv.remove("--apply")
        # Remove dry-run flags if present
        sys.argv = [arg for arg in sys.argv if arg not in ["--dry-run", "-n"]]

    main()
