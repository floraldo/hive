#!/usr/bin/env python3
"""
Comprehensive syntax error fixer for remaining patterns.
Fixes dictionary entries, function calls, and import statements missing commas.
"""

import re
import sys
from pathlib import Path


def comprehensive_comma_fix(file_path):
    """Fix comprehensive missing comma patterns in a Python file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Pattern 1: Fix dictionary entries missing commas
        # "key": value\n    "other_key": other_value -> "key": value,\n    "other_key": other_value
        content = re.sub(r'("[\w_]+"\s*:\s*[^,\n}]*)\n(\s*"[\w_]+"\s*:)', r"\1,\n\2", content)

        # Pattern 2: Fix list items missing commas
        # item\n    other_item -> item,\n    other_item
        content = re.sub(r"([a-zA-Z_][a-zA-Z0-9_\[\]]*)\n(\s+[a-zA-Z_][a-zA-Z0-9_\[\]]*)", r"\1,\n\2", content)

        # Pattern 3: Fix function call arguments missing commas
        # arg_name=value\n    other_arg_name=value -> arg_name=value,\n    other_arg_name=value
        content = re.sub(
            r"([a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[^,\n\)]*)\n(\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=)", r"\1,\n\2", content
        )

        # Pattern 4: Fix SQL query tuples missing commas
        # VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n    (\n        event.event_id
        content = re.sub(r"(\) VALUES \([^)]*\))\n(\s*\(\n)", r"\1,\n\2", content)

        # Pattern 5: Fix tuple elements missing commas
        # value\n        other_value in tuples/function calls
        content = re.sub(r'([^,\(\n]+)\n(\s+[a-zA-Z_"\'\.][a-zA-Z0-9_"\'\.\[\]]*(?:\([^)]*\))?)', r"\1,\n\2", content)

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def fix_specific_errors(src_dir):
    """Fix specific known errors."""
    fixes_applied = []

    # Fix plot_factory.py dict entries
    plot_factory = src_dir / "ecosystemiser" / "datavis" / "plot_factory.py"
    if plot_factory.exists():
        try:
            with open(plot_factory, encoding="utf-8") as f:
                content = f.read()

            # Fix dictionary missing commas
            content = re.sub(r'("source": flow_info\["source"\])\n(\s*"target":)', r"\1,\n\2", content)
            content = re.sub(r'("target": flow_info\["target"\])\n(\s*"value":)', r"\1,\n\2", content)
            content = re.sub(r'("value": [^,\n}]*)\n(\s*"label":)', r"\1,\n\2", content)

            with open(plot_factory, "w", encoding="utf-8") as f:
                f.write(content)
            fixes_applied.append("plot_factory.py dict entries")
        except Exception as e:
            print(f"Error fixing plot_factory.py: {e}")

    # Fix __init__.py imports
    for init_file in src_dir.rglob("__init__.py"):
        try:
            with open(init_file, encoding="utf-8") as f:
                content = f.read()

            original = content
            # Fix import statements missing commas
            content = re.sub(r"([a-zA-Z_][a-zA-Z0-9_]*)\n(\s+[a-zA-Z_][a-zA-Z0-9_]*)\n\)", r"\1,\n\2\n)", content)

            if content != original:
                with open(init_file, "w", encoding="utf-8") as f:
                    f.write(content)
                fixes_applied.append(f"{init_file.name} imports")
        except Exception as e:
            print(f"Error fixing {init_file}: {e}")

    # Fix bus.py SQL tuple
    bus_file = src_dir / "ecosystemiser" / "core" / "bus.py"
    if bus_file.exists():
        try:
            with open(bus_file, encoding="utf-8") as f:
                content = f.read()

            # Fix SQL VALUES tuple
            content = re.sub(r"(\) VALUES \(\?, \?, \?, \?, \?, \?, \?, \?, \?, \?\))\n(\s*\()", r"\1,\n\2", content)

            with open(bus_file, "w", encoding="utf-8") as f:
                f.write(content)
            fixes_applied.append("bus.py SQL tuple")
        except Exception as e:
            print(f"Error fixing bus.py: {e}")

    return fixes_applied


def main():
    """Fix syntax errors across the entire src directory."""
    src_dir = Path("src")

    if not src_dir.exists():
        print("Error: src directory not found")
        sys.exit(1)

    print("Applying comprehensive syntax fixes...")

    # Apply specific known fixes first
    specific_fixes = fix_specific_errors(src_dir)
    print(f"Applied specific fixes: {specific_fixes}")

    # Then apply general comma fixes
    fixed_count = 0
    total_files = 0

    for py_file in src_dir.rglob("*.py"):
        total_files += 1
        if comprehensive_comma_fix(py_file):
            fixed_count += 1
            print(f"Fixed: {py_file}")

    print(f"\nProcessed {total_files} Python files")
    print(f"Applied comprehensive fixes to {fixed_count} files")
    print("Running syntax validation check...")

    # Quick syntax check
    import subprocess

    try:
        result = subprocess.run(
            ["python", "-m", "py_compile", "src/ecosystemiser/__init__.py"], capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✓ Basic syntax validation passed")
        else:
            print(f"✗ Syntax validation failed: {result.stderr}")
    except Exception as e:
        print(f"Could not run syntax validation: {e}")


if __name__ == "__main__":
    main()
