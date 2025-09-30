#!/usr/bin/env python3
"""
Script to systematically update all validator function signatures
to include scope_files parameter and add file-level scoping checks.
"""
from pathlib import Path
import re

def update_validator_signatures():
    """Update all validator signatures to include scope_files parameter."""
    file_path = Path("packages/hive-tests/src/hive_tests/architectural_validators.py")
    content = file_path.read_text()

    # Pattern to match validator function definitions
    pattern = r'def (validate_\w+)\(project_root: Path\) -> tuple\[bool'
    replacement = r'def \1(project_root: Path, scope_files: list[Path] | None = None) -> tuple[bool'

    updated_content = re.sub(pattern, replacement, content)

    # Write back
    file_path.write_text(updated_content)
    print(f"Updated {len(re.findall(pattern, content))} validator signatures")

if __name__ == "__main__":
    update_validator_signatures()
    print("✅ All validator signatures updated with scope_files parameter")