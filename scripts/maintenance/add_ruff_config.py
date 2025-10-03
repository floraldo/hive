"""Add standardized ruff configuration to all pyproject.toml files.

This script adds the standard Hive platform ruff configuration to all
packages and apps that are missing it.

Usage:
    python scripts/maintenance/add_ruff_config.py [--dry-run] [--target <path>]
"""

import argparse
import sys
from pathlib import Path


RUFF_CONFIG_TEMPLATE = '''
# ========================================
# Ruff Configuration (Linter & Formatter)
# ========================================
[tool.ruff]
line-length = 120
target-version = "py311"
exclude = [
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "archive",
]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "S"]
ignore = ["E501", "B008", "C901", "COM812", "COM818", "COM819"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = true
line-ending = "auto"

[tool.ruff.lint.isort]
known-first-party = [
    "hive_logging", "hive_config", "hive_db", "hive_cache", "hive_errors",
    "hive_bus", "hive_async", "hive_performance", "hive_ai", "hive_deployment",
    "hive_service_discovery", "hive_tests", "hive_models", "hive_algorithms",
    "hive_cli", "hive_app_toolkit", "hive_orchestration", "hive_graph",
]
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]
split-on-trailing-comma = false

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S602", "S604"]
"scripts/**" = ["S602", "S604"]
"archive/**" = ["S"]
'''


def has_ruff_config(content: str) -> bool:
    """Check if pyproject.toml already has [tool.ruff] section."""
    return "[tool.ruff]" in content


def add_ruff_config(filepath: Path, dry_run: bool = False) -> bool:
    """Add ruff configuration to a pyproject.toml file.

    Args:
        filepath: Path to pyproject.toml
        dry_run: If True, don't actually modify the file

    Returns:
        True if config was added, False if already present or error
    """
    try:
        content = filepath.read_text(encoding="utf-8")

        # Check if ruff config already exists
        if has_ruff_config(content):
            print(f"✓ {filepath.relative_to(Path.cwd())} - Already has ruff config")
            return False

        # Find insertion point (after [tool.poetry.group.dev.dependencies] if it exists)
        # Otherwise, append to end of file
        lines = content.split("\n")
        insertion_idx = len(lines)

        # Look for good insertion point
        for i, line in enumerate(lines):
            if line.startswith("[tool.poetry.group.dev.dependencies]"):
                # Find the end of this section
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith("[") and not lines[j].startswith("[tool.poetry.group.dev.dependencies"):
                        insertion_idx = j
                        break
                break

        # Insert ruff config
        new_lines = lines[:insertion_idx] + [RUFF_CONFIG_TEMPLATE.strip()] + [""] + lines[insertion_idx:]
        new_content = "\n".join(new_lines)

        if dry_run:
            print(f"[DRY RUN] Would add ruff config to: {filepath.relative_to(Path.cwd())}")
            return True

        # Write updated content
        filepath.write_text(new_content, encoding="utf-8")
        print(f"✓ {filepath.relative_to(Path.cwd())} - Added ruff config")
        return True

    except Exception as e:
        print(f"✗ {filepath.relative_to(Path.cwd())} - Error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Add ruff config to pyproject.toml files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without modifying files")
    parser.add_argument("--target", type=Path, help="Specific pyproject.toml file or directory to process")
    args = parser.parse_args()

    project_root = Path.cwd()

    # Determine which files to process
    if args.target:
        if args.target.is_file() and args.target.name == "pyproject.toml":
            pyproject_files = [args.target]
        elif args.target.is_dir():
            pyproject_files = list(args.target.glob("**/pyproject.toml"))
        else:
            print(f"Error: {args.target} is not a valid pyproject.toml file or directory", file=sys.stderr)
            return 1
    else:
        # Process all packages and apps (exclude root)
        pyproject_files = []
        pyproject_files.extend(project_root.glob("packages/*/pyproject.toml"))
        pyproject_files.extend(project_root.glob("apps/*/pyproject.toml"))

    if not pyproject_files:
        print("No pyproject.toml files found to process")
        return 0

    print(f"Found {len(pyproject_files)} pyproject.toml files to check")
    print()

    modified_count = 0
    for filepath in sorted(pyproject_files):
        if add_ruff_config(filepath, dry_run=args.dry_run):
            modified_count += 1

    print()
    print(f"Summary: {modified_count} files {'would be' if args.dry_run else 'were'} modified")

    return 0


if __name__ == "__main__":
    sys.exit(main())
