"""Master codebase restoration script.

Executes all fixer scripts in the correct order and validates results.
"""

import subprocess
import sys
from pathlib import Path


def run_script(script_name: str) -> bool:
    """Run a Python script and return success status."""
    script_path = Path(__file__).parent / script_name

    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}")
        return False

    print(f"\n{'='*60}")
    print(f"Running: {script_name}")
    print('='*60)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=script_path.parent.parent,
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"ERROR running {script_name}: {e}")
        return False


def run_syntax_check() -> bool:
    """Run Python syntax check on all files."""
    src_dir = Path(__file__).parent.parent / 'src' / 'ecosystemiser'

    print(f"\n{'='*60}")
    print("Running syntax validation...")
    print('='*60)

    errors = []

    for py_file in src_dir.rglob('*.py'):
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', str(py_file)],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                errors.append((py_file.relative_to(src_dir), result.stderr))
        except Exception as e:
            errors.append((py_file.relative_to(src_dir), str(e)))

    if errors:
        print(f"\nFOUND {len(errors)} files with syntax errors:")
        for file, error in errors[:10]:  # Show first 10
            print(f"  - {file}")
            print(f"    {error[:200]}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        return False

    print("All files passed syntax validation")
    return True


def main():
    """Main execution."""
    print("="*60)
    print("ECOSYSTEMISER CODEBASE RESTORATION")
    print("="*60)

    # Step 1: Fix missing Optional imports
    if not run_script('fix_missing_optional_imports.py'):
        print("\nERROR: Optional import fixer failed")
        return 1

    # Step 2: Fix comma issues
    if not run_script('fix_field_commas_ast.py'):
        print("\nERROR: Comma fixer failed")
        return 1

    # Step 3: Validate syntax
    if not run_syntax_check():
        print("\nERROR: Syntax validation failed")
        print("Some files still have syntax errors")
        return 1

    print("\n" + "="*60)
    print("RESTORATION COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("  1. Run: ruff . --fix")
    print("  2. Run: black .")
    print("  3. Verify: ruff . && black --check .")
    print("  4. Test: pytest tests/")

    return 0


if __name__ == '__main__':
    sys.exit(main())