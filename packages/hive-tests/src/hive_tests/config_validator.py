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

            # Rule 32: Check for python version specification
            # Supports both Poetry format (python = "^3.11") and PEP 621 format (requires-python = ">=3.11")
            has_poetry_format = 'python = "^3.11"' in content
            has_pep621_format = 'requires-python = ">=3.11"' in content or 'requires-python = ">= 3.11"' in content

            if not has_poetry_format and not has_pep621_format:
                violations.append(
                    f"FAIL {relative_path}: Missing python version specification (Rule 32) - "
                    f"Expected 'python = \"^3.11\"' (Poetry) or 'requires-python = \">=3.11\"' (PEP 621)"
                )

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
