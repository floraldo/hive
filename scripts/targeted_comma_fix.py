#!/usr/bin/env python3
"""
Targeted comma fixer for specific patterns in Python code.
"""

from pathlib import Path


def fix_argparse_pattern(content: str) -> str:
    """Fix missing commas in argparse add_argument calls."""
    lines = content.split("\n")
    fixed_lines = []
    in_add_argument = False

    for i, line in enumerate(lines):
        # Check if we're in an add_argument call
        if "add_argument(" in line or r"add_argument\(" in line:
            in_add_argument = True

        if in_add_argument:
            # If line contains parameter assignments and doesn't end with comma or paren
            stripped = line.rstrip()
            if (
                stripped
                and not stripped.endswith((",", "(", ")", "[", "]", "{", "}", ":"))
                and not stripped.strip().startswith("#")
                and ("=" in line or line.strip().startswith('"') or line.strip().startswith("'"))
            ):
                # Check if next line suggests we need a comma
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith(")"):
                        line = stripped + ","

            # Check if add_argument call ends
            if ")" in line and line.count("(") < line.count(")"):
                in_add_argument = False

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_dict_pattern(content: str) -> str:
    """Fix missing commas in dictionary literals."""
    lines = content.split("\n")
    fixed_lines = []
    in_dict = 0

    for i, line in enumerate(lines):
        # Track dictionary depth
        in_dict += line.count("{") - line.count("}")

        if in_dict > 0:
            stripped = line.rstrip()
            # Check if line has key: value pattern without trailing comma
            if (
                ":" in stripped
                and not stripped.endswith((",", "{", "}", "[", "]", "(", ")"))
                and not stripped.strip().startswith("#")
            ):
                # Check next line
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith("}"):
                        line = stripped + ","

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_file(file_path: Path) -> bool:
    """Fix missing commas in a Python file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            original = f.read()

        fixed = fix_argparse_pattern(original)
        fixed = fix_dict_pattern(fixed)

        if fixed != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed)
            print(f"FIXED: {file_path}")
            return True
        return False

    except Exception as e:
        print(f"ERROR: {file_path} - {e}")
        return False


def main():
    """Main function."""
    print("=" * 80)
    print("TARGETED COMMA FIXER")
    print("=" * 80)

    project_root = Path(__file__).parent.parent
    fixed_count = 0

    # Get files with syntax errors from ruff
    import subprocess

    result = subprocess.run(
        ["python", "-m", "ruff", "check", "."],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    # Parse files with errors
    error_files = set()
    for line in result.stdout.split("\n"):
        if "-->" in line:
            # Extract file path
            parts = line.split("-->")
            if len(parts) > 1:
                file_path = parts[1].strip().split(":")[0]
                error_files.add(file_path)

    print(f"Found {len(error_files)} files with syntax errors")
    print("\nFixing targeted patterns...")

    for file_path_str in error_files:
        file_path = project_root / file_path_str
        if file_path.exists():
            if fix_file(file_path):
                fixed_count += 1

    print("\n" + "=" * 80)
    print(f"Files fixed: {fixed_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
