#!/usr/bin/env python3
"""Clean up excess commas created by the comprehensive fix."""

import re
from pathlib import Path


def clean_over_commas(file_path):
    """Remove excess commas that shouldn't be there."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Remove trailing commas at end of statements/lines that shouldn't have them
        content = re.sub(r",(\s*)\n(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*[=:])", r"\1\n\2", content)

        # Remove commas before closing brackets/parens at end of line
        content = re.sub(r",(\s*[\)\]]\s*)$", r"\1", content, flags=re.MULTILINE)

        # Remove commas before "else:", "except:", "finally:", etc.
        content = re.sub(r",(\s*)\n(\s*(?:else|except|finally|elif):)", r"\1\n\2", content)

        # Fix docstring comma issues - remove commas after triple quotes
        content = re.sub(r'("""[^"]*?"""),(\s*)', r"\1\2", content, flags=re.DOTALL)

        # Fix import statement commas - remove trailing commas before closing )
        content = re.sub(r",(\s*)\n(\s*\))", r"\1\n\2", content)

        # Fix class/function definition commas
        content = re.sub(r"(class\s+[a-zA-Z_][a-zA-Z0-9_]*[^:]*):,", r"\1:", content)
        content = re.sub(r"(def\s+[a-zA-Z_][a-zA-Z0-9_]*[^:]*):,", r"\1:", content)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Clean up over-comma issues."""
    src_dir = Path("src")

    if not src_dir.exists():
        print("Error: src directory not found")
        return

    fixed_count = 0
    total_files = 0

    print("Cleaning up over-comma issues...")

    for py_file in src_dir.rglob("*.py"):
        total_files += 1
        if clean_over_commas(py_file):
            fixed_count += 1
            print(f"Cleaned: {py_file}")

    print(f"Processed {total_files} files, cleaned {fixed_count} files")


if __name__ == "__main__":
    main()
