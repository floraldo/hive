#!/usr/bin/env python3
"""Fix missing type hints for Rule 7 compliance."""

import ast
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def fix_type_hints(file_path: Path) -> bool:
    """Fix missing type hints in a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse the AST
        tree = ast.parse(content)

        # Track if we made changes
        modified = False
        lines = content.splitlines()

        # Process each function
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if return type is missing for non-test, non-private functions
                if node.returns is None and not node.name.startswith("_"):
                    # Add -> None for functions that likely don't return anything
                    if node.name in [
                        "main",
                        "run",
                        "validate_architecture",
                        "generate_reports",
                        "print_summary",
                        "save_profiles_and_config",
                        "create_weather_enhanced_profiles",
                        "process_climate_data",
                        "fix_unicode_in_file",
                        "test_milp_flow_extraction",
                        "debug_objective",
                    ]:
                        # Find the line with the function definition
                        func_line_idx = node.lineno - 1
                        if func_line_idx < len(lines):
                            line = lines[func_line_idx]
                            # Add -> None before the colon
                            if ":" in line and "->" not in line:
                                lines[func_line_idx] = line.replace(":", " -> None:", 1)
                                modified = True

        if modified:
            # Write back the modified content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main() -> None:
    """Main function to fix type hints."""
    # Files with missing type hints from the validation report
    files_to_fix = [
        "apps/ecosystemiser/debug_milp_extraction.py",
        "apps/ecosystemiser/debug_objective.py",
        "apps/ecosystemiser/validate_enhanced_architecture.py",
        "apps/ecosystemiser/examples/parametric_sweep_example.py",
        "apps/ecosystemiser/examples/run_full_demo.py",
        "apps/ecosystemiser/scripts/create_thermal_profiles.py",
        "apps/ecosystemiser/scripts/extract_golden_profiles.py",
        "apps/ecosystemiser/scripts/extract_yearly_profiles.py",
        "apps/ecosystemiser/scripts/integrate_climate_data.py",
        "apps/ecosystemiser/scripts/archive/fix_unicode.py",
        "apps/ecosystemiser/scripts/archive/generate_golden_simplified.py",
        "apps/ecosystemiser/scripts/archive/validate_fidelity_differences.py",
    ]

    fixed_count = 0
    for file_path in files_to_fix:
        full_path = Path(file_path)
        if full_path.exists():
            if fix_type_hints(full_path):
                print(f"Fixed type hints in {file_path}")
                fixed_count += 1
        else:
            print(f"File not found: {file_path}")

    print(f"\nFixed type hints in {fixed_count} files")


if __name__ == "__main__":
    main()
