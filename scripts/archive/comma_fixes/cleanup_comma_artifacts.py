#!/usr/bin/env python3
"""
Cleanup script to fix artifacts left by the comprehensive comma fixer.

This script addresses over-aggressive comma additions and other artifacts
from the automated fixing process.
"""

import os
import re
import glob


def fix_artifacts(content):
    """Fix specific patterns that the main script created incorrectly."""

    # Fix patterns like "field", -> "field"
    content = re.sub(r'(\w+["\'])\s*,{2,}', r"\1,", content)

    # Fix patterns like payload={, -> payload={
    content = re.sub(r"=\{\s*,", r"={", content)

    # Fix patterns like field,,,, -> field,
    content = re.sub(r",{2,}", r",", content)

    # Fix patterns like (,, -> (
    content = re.sub(r"\(\s*,+", r"(", content)

    # Fix patterns like method(field, -> method(field,
    content = re.sub(r"(\w+\([^)]*),\s*,+", r"\1,", content)

    # Fix array/dict issues like [,, or {,,
    content = re.sub(r"([{\[])\s*,+", r"\1", content)

    # Fix patterns like "recovery_suggestions"[, -> "recovery_suggestions": [
    content = re.sub(r'"recovery_suggestions"\s*\[\s*,', r'"recovery_suggestions": [', content)

    # Fix over-aggressive class/function parameter corrections
    content = re.sub(r"(\w+):\s*([^,\n]+),,,,", r"\1: \2,", content)

    # Fix list/dict separators
    content = re.sub(r"(\w+)\s*,{2,}\s*\n", r"\1,\n", content)

    return content


def fix_file(file_path):
    """Fix artifacts in a single file."""

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        content = fix_artifacts(content)

        # Only write if content changed
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Cleaned: {file_path}")
            return True
        else:
            return False

    except Exception as e:
        print(f"Error cleaning {file_path}: {e}")
        return False


def main():
    """Main execution - clean up comma artifacts."""

    # Target patterns - focus on files that were just modified
    target_patterns = ["apps/ecosystemiser/src/**/*.py", "packages/*/src/**/*.py"]

    files_cleaned = 0
    total_files = 0

    for pattern in target_patterns:
        for file_path in glob.glob(pattern, recursive=True):
            if file_path.endswith(".py"):
                total_files += 1
                if fix_file(file_path):
                    files_cleaned += 1

    print(f"\nComma artifact cleanup complete:")
    print(f"Files processed: {total_files}")
    print(f"Files cleaned: {files_cleaned}")
    print(f"Success rate: {files_cleaned/total_files*100:.1f}%" if total_files > 0 else "No files found")


if __name__ == "__main__":
    main()
