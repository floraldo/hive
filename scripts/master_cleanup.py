#!/usr/bin/env python3
"""
Master Cleanup Script - One command to fix everything.

Usage:
    python scripts/master_cleanup.py           # Full cleanup
    python scripts/master_cleanup.py --check   # Check only, no fixes
    python scripts/master_cleanup.py --quick   # Quick fixes only (ruff + black)
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str, check_only: bool = False) -> bool:
    """Run a command and return success status."""
    if check_only and any(word in cmd for word in ["--fix", "format", "black"]):
        # Skip fix commands in check-only mode
        cmd = cmd.replace("--fix", "").replace("black", "ruff check")

    print(f"\n{'[CHECK]' if check_only else '[RUN]'} {description}...")
    print(f"  Command: {cmd}")

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print("  [OK] Success")
            return True
        else:
            print(f"  [FAIL] Failed (exit code: {result.returncode})")
            if result.stderr:
                print(f"  Error: {result.stderr[:500]}")
            return False
    except Exception as e:
        print(f"  [FAIL] Exception: {e}")
        return False


def main():
    """Run the master cleanup process."""
    parser = argparse.ArgumentParser(description="Master cleanup for Hive platform")
    parser.add_argument("--check", action="store_true", help="Check only, don't fix")
    parser.add_argument("--quick", action="store_true", help="Quick fixes only (ruff + black)")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent

    print("=" * 60)
    print("HIVE PLATFORM MASTER CLEANUP")
    print("=" * 60)

    success_count = 0
    total_count = 0

    # Step 1: Syntax validation
    if not args.quick:
        total_count += 1
        if run_command(
            f"cd {project_root} && python -m py_compile {project_root}/apps/**/*.py",
            "Python syntax validation",
            check_only=True,
        ):
            success_count += 1

    # Step 2: Ruff auto-fixes
    total_count += 1
    if run_command(
        f"cd {project_root} && python -m ruff check {'--fix' if not args.check else ''} .",
        "Ruff linting and auto-fixes",
        check_only=args.check,
    ):
        success_count += 1

    # Step 3: Black formatting
    total_count += 1
    if run_command(
        f"cd {project_root} && python -m black {'--check' if args.check else ''} .",
        "Black code formatting",
        check_only=args.check,
    ):
        success_count += 1

    # Step 4: Test collection (quick validation)
    if not args.quick:
        total_count += 1
        if run_command(
            f"cd {project_root} && python -m pytest --collect-only -q", "Test collection validation", check_only=True,
        ):
            success_count += 1

    # Step 5: Golden Rules validation
    if not args.quick and not args.check:
        total_count += 1
        if run_command(
            f"cd {project_root} && python scripts/validate_golden_rules.py 2>&1 | grep -E '(PASS|FAIL)' | head -5",
            "Golden Rules validation summary",
            check_only=True,
        ):
            success_count += 1

    # Summary
    print("\n" + "=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"[OK] Successful steps: {success_count}/{total_count}")

    if args.check:
        print("\nRun without --check to apply fixes")
    elif success_count == total_count:
        print("\n[OK] All cleanup steps completed successfully!")
    else:
        print(f"\n[WARN] {total_count - success_count} steps failed - review output above")

    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
