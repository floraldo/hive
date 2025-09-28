#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate all Golden Rules for the Hive platform.

This script runs all architectural validation rules and reports
on compliance across the entire codebase.
"""

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows compatibility
if sys.platform == "win32":
    # Set console code page to UTF-8
    os.system("chcp 65001 > nul")
    # Reconfigure stdout if available (Python 3.7+)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

# Add the workspace root to path for imports
workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root / "packages" / "hive-tests" / "src"))

from hive_tests import run_all_golden_rules


def main():
    """Run all golden rules validation and report results."""
    print("Building - Running Hive Platform Golden Rules Validation")
    print("=" * 60)

    project_root = workspace_root
    all_passed, results = run_all_golden_rules(project_root)

    # Report results
    for rule_name, result in results.items():
        status = "PASS PASS" if result["passed"] else "FAIL FAIL"
        print(f"{status} {rule_name}")

        if not result["passed"] and result["violations"]:
            for violation in result["violations"]:
                # Use ASCII bullet for better compatibility
                try:
                    print(f"  • {violation}")
                except UnicodeEncodeError:
                    # Fallback to ASCII-safe output
                    safe_violation = violation.encode("ascii", "replace").decode("ascii")
                    print(f"  - {safe_violation}")
            print()

    print("=" * 60)
    if all_passed:
        print("PASS All Golden Rules validation passed!")
        return 0
    else:
        failed_count = sum(1 for r in results.values() if not r["passed"])
        print(f"FAIL {failed_count} Golden Rules failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
