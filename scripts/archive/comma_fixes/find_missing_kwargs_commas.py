#!/usr/bin/env python3
"""
Script to find all instances of missing commas before **kwargs in events.py.

This script specifically looks for the pattern:
    }
    **kwargs
where a comma is missing after the closing brace.
"""

import re


def find_missing_kwargs_commas():
    """Find all missing commas before **kwargs."""

    file_path = r"C:\git\hive\apps\ecosystemiser\src\ecosystemiser\core\events.py"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        issues = []
        for i, line in enumerate(lines, 1):
            # Look for lines with just } followed by lines with **kwargs
            if line.strip() == "}" and i < len(lines):
                next_line = lines[i].strip()
                if next_line.startswith("**kwargs"):
                    issues.append((i, f"Line {i}: Missing comma after }} before **kwargs"))

        if issues:
            print(f"Found {len(issues)} missing comma issues:")
            for line_num, message in issues:
                print(f"  {message}")
            return issues
        else:
            print("No missing comma issues found")
            return []

    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return []


if __name__ == "__main__":
    find_missing_kwargs_commas()
