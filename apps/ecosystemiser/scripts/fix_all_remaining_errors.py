# Security: subprocess calls in this script use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess.

"""Comprehensive fix for all remaining syntax errors."""

import re
import subprocess
import sys
from pathlib import Path


def fix_dict_key_issues(content: str) -> tuple[str, list[str]]:
    """Fix dictionary key syntax errors."""
    issues = ([],)
    lines = (content.split("\n"),)
    fixed_lines = []

    for i, line in enumerate(lines):
        # Pattern: "key": value"next_key" -> "key": value, "next_key"
        if re.search(r'"\s*["\']', line):
            # Check if this looks like missing comma in dict
            if ":" in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and (next_line.startswith('"') or next_line.startswith("'")):
                    if not line.rstrip().endswith((",", "{", "(")):
                        line = line.rstrip() + ","
                        if "Fixed missing comma in dictionary" not in issues:
                            issues.append("Fixed missing comma in dictionary")

        # Pattern: hasattr(obj"attr") -> hasattr(obj, "attr")
        line = re.sub(r'hasattr\((\w+)"', r'hasattr(\1, "', line)
        if "hasattr" in line and ', "' in line:
            if "Fixed hasattr missing comma" not in issues:
                issues.append("Fixed hasattr missing comma")

        # Pattern: getattr(obj"attr" -> getattr(obj, "attr"
        line = re.sub(r'getattr\((\w+)"', r'getattr(\1, "', line)
        if "getattr" in line and ', "' in line:
            if "Fixed getattr missing comma" not in issues:
                issues.append("Fixed getattr missing comma")

        fixed_lines.append(line)

    return "\n".join(fixed_lines), issues


def process_file(file_path: Path) -> tuple[bool, list[str]]:
    """Process a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        fixed_content, issues = fix_dict_key_issues(content)

        if fixed_content != content:
            file_path.write_text(fixed_content, encoding="utf-8")
            return True, issues

        return False, []
    except Exception as e:
        return False, [f"ERROR: {e}"]


def validate_syntax(file_path: Path) -> tuple[bool, str]:
    """Validate Python syntax of a file."""
    try:
        result = subprocess.run([sys.executable, "-m", "py_compile", str(file_path)], check=False, capture_output=True, text=True)
        if result.returncode == 0:
            return True, ""
        return False, result.stderr
    except Exception as e:
        return False, str(e)


def main():
    """Main execution."""
    src_dir = Path(__file__).parent.parent / "src" / "ecosystemiser"

    if not src_dir.exists():
        print(f"ERROR: Source directory not found: {src_dir}")
        return 1

    print("Fixing all remaining syntax errors...")

    # First pass: Fix known patterns
    fixed_files = []
    for py_file in src_dir.rglob("*.py"):
        modified, issues = process_file(py_file)
        if modified:
            fixed_files.append((py_file.relative_to(src_dir), issues))
            print(f"  FIXED: {py_file.relative_to(src_dir)}")
            for issue in issues:
                print(f"    - {issue}")

    print(f"\nFirst pass completed: {len(fixed_files)} files fixed")

    # Second pass: Validate all files
    print("\nValidating syntax...")
    errors = []
    for py_file in src_dir.rglob("*.py"):
        valid, error = validate_syntax(py_file)
        if not valid:
            errors.append((py_file.relative_to(src_dir), error))

    if errors:
        print(f"\nFOUND {len(errors)} files with syntax errors:")
        for file, error in errors[:10]:
            print(f"  - {file}")
            # Extract just the error line
            error_lines = error.split("\n")
            for line in error_lines:
                if "SyntaxError" in line or "line" in line:
                    print(f"    {line}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        return 1

    print("\nAll files validated successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
