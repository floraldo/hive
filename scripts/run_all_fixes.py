#!/usr/bin/env python3
"""Master script to run all Golden Rules fixes in order."""

import subprocess
import sys
from pathlib import Path


def run_script(script_name: str, description: str) -> bool:
    """Run a fix script and report results."""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Script: {script_name}")
    print(f"{'=' * 60}")

    script_path = Path(f"scripts/{script_name}")
    if not script_path.exists():
        print(f"Script not found: {script_path}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60
        )

        print(result.stdout)
        if result.stderr:
            print(f"Errors: {result.stderr}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print(f"Script timed out: {script_name}")
        return False
    except Exception as e:
        print(f"Error running script: {e}")
        return False


def run_validation() -> dict:
    """Run Golden Rules validation and return results."""
    print(f"\n{'=' * 60}")
    print("Running Golden Rules Validation")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(
            [sys.executable, "scripts/validate_golden_rules.py"],
            capture_output=True,
            text=True,
            timeout=120
        )

        output = result.stdout

        # Parse results
        failures = 0
        failed_rules = []

        for line in output.split('\n'):
            if 'FAIL' in line and 'Golden Rule' in line:
                # Extract rule number
                import re
                match = re.search(r'Golden Rule (\d+)', line)
                if match:
                    failed_rules.append(int(match.group(1)))
            if 'Golden Rules failed validation' in line:
                match = re.search(r'(\d+) Golden Rules', line)
                if match:
                    failures = int(match.group(1))

        return {
            'failures': failures,
            'failed_rules': failed_rules,
            'output': output
        }

    except Exception as e:
        print(f"Error running validation: {e}")
        return {'failures': -1, 'failed_rules': [], 'output': str(e)}


def main():
    """Run all fixes in order."""
    print("Hive Platform - Comprehensive Golden Rules Fix")
    print("=" * 60)

    # Initial validation
    print("\n1. INITIAL STATE")
    initial_results = run_validation()
    initial_failures = initial_results['failures']
    print(f"\nInitial failures: {initial_failures} rules")
    print(f"Failed rules: {initial_results['failed_rules']}")

    # Run fix scripts in order
    scripts = [
        ("fix_syntax_errors.py", "Fix syntax errors (commas, imports)"),
        ("fix_dict_commas.py", "Fix missing commas in dictionaries"),
        ("fix_type_hints.py", "Fix missing type hints (Rule 7)"),
        ("fix_print_statements.py", "Fix print statements in apps (Rule 9)"),
        ("fix_package_prints.py", "Fix print statements in packages (Rule 9)"),
        ("fix_global_state.py", "Fix global state access (Rule 16)"),
        ("fix_async_patterns.py", "Fix async pattern consistency (Rule 14)"),
        ("fix_service_layer.py", "Analyze service layer violations (Rule 10)"),
    ]

    successful_fixes = 0
    failed_fixes = []

    print("\n2. APPLYING FIXES")
    for script, description in scripts:
        if run_script(script, description):
            successful_fixes += 1
        else:
            failed_fixes.append(script)

    # Final validation
    print("\n3. FINAL STATE")
    final_results = run_validation()
    final_failures = final_results['failures']
    print(f"\nFinal failures: {final_failures} rules")
    print(f"Failed rules: {final_results['failed_rules']}")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Scripts executed: {len(scripts)}")
    print(f"Successful: {successful_fixes}")
    print(f"Failed: {len(failed_fixes)}")

    if failed_fixes:
        print(f"\nFailed scripts:")
        for script in failed_fixes:
            print(f"  - {script}")

    improvement = initial_failures - final_failures
    if improvement > 0:
        print(f"\nIMPROVEMENT: Reduced failures by {improvement} rules")
        print(f"Percentage improvement: {(improvement/initial_failures)*100:.1f}%")
    elif improvement == 0:
        print("\nNo change in Golden Rules compliance")
    else:
        print(f"\nWARNING: Failures increased by {-improvement} rules")

    # Recommendations
    if final_failures > 0:
        print(f"\n{'=' * 60}")
        print("RECOMMENDATIONS")
        print(f"{'=' * 60}")
        print("\n1. Review remaining violations manually")
        print("2. Some violations may require architectural changes")
        print("3. Run individual fix scripts with verbose output for details")
        print("4. Consider creating custom fix scripts for specific patterns")

        if 10 in final_results['failed_rules']:
            print("\nRule 10 (Service Layer):")
            print("  - Requires manual refactoring of business logic")
            print("  - Extract domain modules from service layers")
            print("  - Keep services as thin orchestration layers")

    else:
        print("\n🎉 ALL GOLDEN RULES PASSING! 🎉")

    return final_failures == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)