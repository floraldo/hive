"""Configuration Consistency Validator

Golden Rules 31-33: Configuration file consistency validation
"""

import sys
from pathlib import Path


def validate_config_consistency(project_root: Path | None = None) -> int:
    """Validate configuration consistency across all pyproject.toml files."""
    if project_root is None:
        project_root = Path.cwd()

    violations = []
    pyproject_files = []
    pyproject_files.extend(project_root.glob("packages/*/pyproject.toml"))
    pyproject_files.extend(project_root.glob("apps/*/pyproject.toml"))

    for pyproject_file in pyproject_files:
        try:
            content = pyproject_file.read_text(encoding="utf-8")
            relative_path = pyproject_file.relative_to(project_root)

            # Rule 31: Check for [tool.ruff] section
            if "[tool.ruff]" not in content:
                violations.append(f"FAIL {relative_path}: Missing [tool.ruff] configuration (Rule 31)")

            # Rule 32: Check for python = "^3.11"
            if 'python = "^3.11"' not in content:
                violations.append(f"FAIL {relative_path}: Missing python = \"^3.11\" (Rule 32)")

        except Exception as e:
            violations.append(f"FAIL {relative_path}: Error reading file: {e}")

    if violations:
        print("Configuration consistency violations found:")
        print()
        for violation in violations:
            print(violation)
        print()
        print(f"Total violations: {len(violations)}")
        return 1
    else:
        print("PASS: All configuration files are consistent")
        return 0

if __name__ == "__main__":
    sys.exit(validate_config_consistency())
