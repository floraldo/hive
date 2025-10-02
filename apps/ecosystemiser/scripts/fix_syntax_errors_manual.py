"""Manual syntax error fixer for specific patterns.

This script fixes the specific syntax errors introduced by aggressive comma fixing:
1. class Name:, -> class Name:
2. def method():, -> def method():
3. constraints = [], -> constraints = []
4. Trailing commas in comments
"""

import re
from pathlib import Path


def fix_content(content: str) -> tuple[str, list[str]]:
    """Fix syntax errors in content. Returns (fixed_content, issues_found)."""
    issues = []

    # Pattern 1: class definitions with trailing comma
    # class Foo:, -> class Foo:
    pattern1 = r"(class\s+\w+(?:\([^)]*\))?)\s*:\s*,"
    if re.search(pattern1, content):
        content = re.sub(pattern1, r"\1:", content)
        issues.append("Fixed class definition trailing commas")

    # Pattern 2: function/method definitions with trailing comma
    # def foo():, -> def foo():
    pattern2 = r"(def\s+\w+\([^)]*\)(?:\s*->\s*[^:]+)?)\s*:\s*,"
    if re.search(pattern2, content):
        content = re.sub(pattern2, r"\1:", content)
        issues.append("Fixed function definition trailing commas")

    # Pattern 3: async function definitions
    # async def foo():, -> async def foo():
    pattern3 = r"(async\s+def\s+\w+\([^)]*\)(?:\s*->\s*[^:]+)?)\s*:\s*,"
    if re.search(pattern3, content):
        content = re.sub(pattern3, r"\1:", content)
        issues.append("Fixed async function definition trailing commas")

    # Pattern 4: Assignment with empty list/dict and trailing comma
    # foo = [], -> foo = []
    pattern4 = r"=\s*\[\s*\]\s*,"
    if re.search(pattern4, content):
        content = re.sub(pattern4, "= []", content)
        issues.append("Fixed empty list assignment commas")

    # Pattern 5: Docstring lines with trailing commas
    # """Some text,""" -> """Some text"""
    pattern5 = r'(["\'])([^"\']*),\s*\1'
    if re.search(pattern5, content):
        content = re.sub(pattern5, r"\1\2\1", content)
        issues.append("Fixed docstring trailing commas")

    # Pattern 6: Comment-like trailing commas in strings
    # "text", -> "text"
    # But only in specific contexts like docstrings
    lines = (content.split("\n"),)
    fixed_lines = ([],)
    in_docstring = False

    for line in lines:
        # Track docstrings
        if '"""' in line or "'''" in line:
            in_docstring = not in_docstring

        # Fix trailing commas in docstrings
        if in_docstring and line.rstrip().endswith(","):
            # Remove trailing comma from docstring lines
            line = line.rstrip()[:-1]

        fixed_lines.append(line)

    content = "\n".join(fixed_lines)

    return content, issues


def process_file(file_path: Path) -> tuple[bool, list[str]]:
    """Process a single file. Returns (modified, issues)."""
    try:
        content = file_path.read_text(encoding="utf-8")
        fixed_content, issues = fix_content(content)

        if fixed_content != content:
            file_path.write_text(fixed_content, encoding="utf-8")
            return True, issues

        return False, []
    except Exception as e:
        return False, [f"ERROR: {e}"]


def main():
    """Main execution."""
    src_dir = Path(__file__).parent.parent / "src" / "ecosystemiser"

    if not src_dir.exists():
        print(f"ERROR: Source directory not found: {src_dir}")
        return

    print("Fixing specific syntax error patterns...")

    fixed_files = []

    for py_file in src_dir.rglob("*.py"):
        modified, issues = process_file(py_file)
        if modified:
            fixed_files.append((py_file.relative_to(src_dir), issues))
            print(f"  FIXED: {py_file.relative_to(src_dir)}")
            for issue in issues:
                print(f"    - {issue}")

    print(f"\nCompleted: {len(fixed_files)} files fixed")


if __name__ == "__main__":
    main()
