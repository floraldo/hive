#!/usr/bin/env python3
"""
Validate all Golden Rules for the Hive platform.

This script runs all architectural validation rules and reports
on compliance across the entire codebase.
"""

import sys
from pathlib import Path

# Add the workspace root to path for imports
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root / "packages" / "hive-tests" / "src"))

from hive_tests import run_all_golden_rules


def main():
    """Run all golden rules validation and report results."""
    print("🏗️  Running Hive Platform Golden Rules Validation")
    print("=" * 60)

    project_root = workspace_root
    all_passed, results = run_all_golden_rules(project_root)

    # Report results
    for rule_name, result in results.items():
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"{status} {rule_name}")

        if not result["passed"] and result["violations"]:
            for violation in result["violations"]:
                print(f"  • {violation}")
            print()

    print("=" * 60)
    if all_passed:
        print("✅ All Golden Rules validation passed!")
        return 0
    else:
        failed_count = sum(1 for r in results.values() if not r["passed"])
        print(f"❌ {failed_count} Golden Rules failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())