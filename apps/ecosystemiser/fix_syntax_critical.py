#!/usr/bin/env python3
"""Fix critical syntax errors in Python files to make them parseable."""

import re
from pathlib import Path


def fix_syntax_errors(file_path: Path) -> int:
    """Fix syntax errors in a Python file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Pattern 1: Fix missing commas in function calls and definitions
        # Match: ident=value\n    ident=value -> ident=value,\n    ident=value
        pattern1 = r"(\w+\s*=\s*[^,\n]+)\n(\s+)(\w+\s*[:=])"
        content = re.sub(pattern1, r"\1,\n\2\3", content)

        # Pattern 2: Fix missing commas in dictionaries
        # Match: "key": value\n    "key": value -> "key": value,\n    "key": value
        pattern2 = r'(["\'][\w_]+["\']:\s*[^,\n\}]+)\n(\s+)(["\'][\w_]+["\']:|[}\)])'
        content = re.sub(pattern2, r"\1,\n\2\3", content)

        # Pattern 3: Fix function parameters without commas
        # Match:    param: type\n    param: type -> param: type,\n    param: type
        pattern3 = r"(\s+\w+\s*:\s*[^,\n\)]+)\n(\s+)(\w+\s*[:)])"
        content = re.sub(pattern3, r"\1,\n\2\3", content)

        # Pattern 4: Fix missing commas in tuples/lists
        pattern4 = r"([^,\n\[\(]+)\n(\s+)([^,\n\s\]\)].*[^,\]\)\n])\n(\s*[\]\)])"
        content = re.sub(pattern4, r"\1,\n\2\3\n\4", content)

        # Pattern 5: Fix extra commas (like "metadata": {, )
        content = re.sub(r"{\s*,", "{", content)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return 1

        return 0

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return 0


def main():
    """Fix syntax errors in critical files."""

    # Critical files needed for MILP test
    critical_files = [
        "src/ecosystemiser/system_model/components/energy/electric_boiler.py",
        "src/ecosystemiser/system_model/components/energy/heat_demand.py",
        "src/ecosystemiser/system_model/components/energy/grid.py",
        "src/ecosystemiser/system_model/components/energy/heat_buffer.py",
        "src/ecosystemiser/system_model/components/energy/power_demand.py",
        "src/ecosystemiser/system_model/components/energy/heat_pump.py",
        "src/ecosystemiser/system_model/components/energy/solar_pv.py",
        "src/ecosystemiser/solver/milp_solver.py",
        "src/ecosystemiser/solver/rule_based_engine.py",
        "src/ecosystemiser/services/results_io.py",
    ]

    total_fixes = 0

    for file_path_str in critical_files:
        file_path = Path(file_path_str)
        if file_path.exists():
            fixes = fix_syntax_errors(file_path)
            if fixes > 0:
                print(f"Fixed syntax in {file_path}")
                total_fixes += fixes

    print(f"\nTotal files fixed: {total_fixes}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
