#!/usr/bin/env python3
"""
Remove conflicting tool configurations from sub-package pyproject.toml files.

This script removes [tool.ruff], [tool.black], [tool.isort], and [tool.mypy]
sections from all sub-package pyproject.toml files, leaving only the root
configuration as the single source of truth.
"""

import re
from pathlib import Path


def remove_tool_sections(content: str, tools: list[str]) -> str:
    """Remove specified [tool.X] sections from TOML content."""
    lines = content.split("\n")
    result = []
    skip_until_next_section = False

    for line in lines:
        # Check if this is a section header
        if line.strip().startswith("["):
            # Check if we should skip this section
            skip_until_next_section = False
            for tool in tools:
                if line.strip().startswith(f"[tool.{tool}"):
                    skip_until_next_section = True
                    break

            # If not skipping, add the line
            if not skip_until_next_section:
                result.append(line)
        elif not skip_until_next_section:
            # Only add line if we're not currently skipping a section
            result.append(line)

    return "\n".join(result)


def clean_pyproject_file(file_path: Path) -> bool:
    """Remove tool configs from a pyproject.toml file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            original = f.read()

        # Remove tool sections
        tools_to_remove = ["ruff", "black", "isort", "mypy"]
        cleaned = remove_tool_sections(original, tools_to_remove)

        # Remove excessive blank lines (more than 2 consecutive)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        if cleaned != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cleaned)
            print(f"CLEANED: {file_path}")
            return True
        else:
            print(f"SKIPPED: {file_path} (no changes needed)")
            return False

    except Exception as e:
        print(f"ERROR: {file_path} - {e}")
        return False


def main():
    """Main function."""
    print("=" * 80)
    print("Removing Conflicting Tool Configurations")
    print("=" * 80)

    project_root = Path(__file__).parent.parent
    cleaned_count = 0

    # Find all pyproject.toml files except root
    for toml_file in project_root.rglob("pyproject.toml"):
        # Skip root, venv, and archive
        if toml_file == project_root / "pyproject.toml" or ".venv" in str(toml_file) or "archive" in str(toml_file):
            continue

        if clean_pyproject_file(toml_file):
            cleaned_count += 1

    print("\n" + "=" * 80)
    print(f"Cleaned {cleaned_count} pyproject.toml files")
    print("=" * 80)


if __name__ == "__main__":
    main()
