#!/usr/bin/env python3
"""
Aggressive Missing Comma Fixer

Fixes missing commas in Python multi-line constructs using regex patterns.
Handles cases where AST parsing fails due to syntax errors.
"""

import re
from pathlib import Path


def fix_missing_commas_aggressive(content: str) -> str:
    """Fix missing commas using aggressive regex patterns."""
    lines = content.split("\n")
    fixed_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Pattern 1: function/import statement with missing commas
        # Example: "def __init__(\n    self\n    param: type"
        if i + 1 < len(lines):
            next_line = lines[i + 1]

            # Check if current line is inside parentheses and next line continues
            if (
                line.strip()
                and not line.rstrip().endswith((",", "(", "[", "{", ":", ")", "]", "}"))
                and not line.strip().startswith("#")
                and next_line.strip()
                and not next_line.strip().startswith((")", "]", "}", "#"))
            ):
                # Check if we're in a multi-line construct
                # Count unclosed brackets
                open_count = line.count("(") + line.count("[") + line.count("{")
                close_count = line.count(")") + line.count("]") + line.count("}")

                # Also check previous lines for context
                total_open = 0
                total_close = 0
                for j in range(max(0, i - 5), i + 1):
                    total_open += lines[j].count("(") + lines[j].count("[") + lines[j].count("{")
                    total_close += lines[j].count(")") + lines[j].count("]") + lines[j].count("}")

                # If we're inside unclosed brackets
                if total_open > total_close:
                    # Pattern-based comma insertion
                    stripped = line.rstrip()

                    # Skip control flow keywords
                    if not any(
                        stripped.lstrip().startswith(kw)
                        for kw in [
                            "def ",
                            "class ",
                            "if ",
                            "elif ",
                            "else:",
                            "for ",
                            "while ",
                            "with ",
                            "try:",
                            "except",
                            "finally:",
                            "return ",
                            "yield ",
                            "raise ",
                            "assert ",
                            "import ",
                            "from ",
                        ]
                    ):
                        # Check if line looks like it needs a comma
                        # Patterns: param: type, "string", number, identifier, etc.
                        patterns = [
                            r"\w+\s*:\s*\w+",  # param: type
                            r"\w+\s*:\s*.+\|",  # param: Type | None
                            r"\w+\s*=\s*.+",  # param=value
                            r'["\'].+["\']$',  # "string"
                            r"\d+(\.\d+)?$",  # number
                            r"\w+\s*$",  # identifier
                            r".+\)$",  # expression(...)
                            r".+\]$",  # expression[...]
                        ]

                        for pattern in patterns:
                            if re.search(pattern, stripped):
                                line = stripped + ","
                                break

        fixed_lines.append(line)
        i += 1

    return "\n".join(fixed_lines)


def fix_file(file_path: Path) -> bool:
    """Fix missing commas in a Python file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            original = f.read()

        fixed = fix_missing_commas_aggressive(original)

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
    print("AGGRESSIVE COMMA FIXER")
    print("=" * 80)

    project_root = Path(__file__).parent.parent
    fixed_count = 0

    # Find all Python files
    python_files = []
    for directory in ["apps", "packages"]:
        dir_path = project_root / directory
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                if ".venv" not in str(py_file) and "archive" not in str(py_file) and "__pycache__" not in str(py_file):
                    python_files.append(py_file)

    print(f"Found {len(python_files)} Python files")
    print("\nFixing syntax errors...")

    for py_file in python_files:
        if fix_file(py_file):
            fixed_count += 1

    print("\n" + "=" * 80)
    print(f"Files fixed: {fixed_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
