#!/usr/bin/env python3
# ruff: noqa: S603
# Security: subprocess calls in this script use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal maintenance tooling.

"""
Unified Maintenance Runner - Consolidates All Maintenance Operations

Replaces 6 separate maintenance scripts with a single unified interface:
- automated_hygiene.py → maintain.py --hygiene
- documentation_analyzer.py → maintain.py --docs
- git_branch_analyzer.py → maintain.py --branches
- repository_hygiene.py → maintain.py --repo
- log_management.py → maintain.py --logs
- fixers/code_fixers.py → maintain.py --fix

Usage:
    python maintain.py --hygiene --analyze-branches
    python maintain.py --docs --check-links
    python maintain.py --branches --stale
    python maintain.py --repo --cleanup
    python maintain.py --logs --archive
    python maintain.py --fix --type-hints
    python maintain.py --all --dry-run
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Script directory
SCRIPTS_DIR = Path(__file__).parent
FIXERS_DIR = SCRIPTS_DIR / "fixers"

# Available maintenance operations
MAINTENANCE_SCRIPTS = {
    "hygiene": "automated_hygiene.py",
    "docs": "documentation_analyzer.py",
    "branches": "git_branch_analyzer.py",
    "repo": "repository_hygiene.py",
    "logs": "log_management.py",
    "fix": "fixers/code_fixers.py",
}


def run_script(script_name: str, args: list[str]) -> int:
    """Run a maintenance script with given arguments."""
    # Handle fixers subdirectory
    if script_name.startswith("fixers/"):
        script_path = SCRIPTS_DIR / script_name
    else:
        script_path = SCRIPTS_DIR / script_name

    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        return 1

    cmd = [sys.executable, str(script_path)] + args
    print(f"\n{'=' * 80}")
    print(f"Running: {script_name}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'=' * 80}\n")

    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Unified Maintenance Runner - One tool for all maintenance operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Automated hygiene (branch analysis, link checking, TODO scanning)
  python maintain.py --hygiene --analyze-branches
  python maintain.py --hygiene --check-links
  python maintain.py --hygiene --scan-todos
  python maintain.py --hygiene --all

  # Documentation analysis
  python maintain.py --docs --find-links
  python maintain.py --docs --find-todos
  python maintain.py --docs --find-redundant

  # Git branch analysis
  python maintain.py --branches --list-stale
  python maintain.py --branches --list-merged
  python maintain.py --branches --cleanup --dry-run

  # Repository hygiene
  python maintain.py --repo --cleanup
  python maintain.py --repo --optimize

  # Log management
  python maintain.py --logs --archive
  python maintain.py --logs --cleanup --days 30

  # Code fixing
  python maintain.py --fix --type-hints
  python maintain.py --fix --print-statements
  python maintain.py --fix --logging
  python maintain.py --fix --all

  # Run all maintenance checks (dry-run recommended)
  python maintain.py --all --dry-run

  # Get help for specific operation
  python maintain.py --hygiene --help
  python maintain.py --fix --help
""",
    )

    # Main operation flags
    parser.add_argument("--hygiene", action="store_true", help="Automated repository hygiene (branches, links, TODOs)")
    parser.add_argument("--docs", action="store_true", help="Documentation quality analysis")
    parser.add_argument("--branches", action="store_true", help="Git branch analysis and cleanup")
    parser.add_argument("--repo", action="store_true", help="Repository-wide hygiene and optimization")
    parser.add_argument("--logs", action="store_true", help="Log file management")
    parser.add_argument("--fix", action="store_true", help="Code fixing and modernization")
    parser.add_argument("--all", action="store_true", help="Run all maintenance operations (use with --dry-run)")

    # Common options
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--quick", action="store_true", help="Quick mode: run minimal checks")

    args, unknown_args = parser.parse_known_args()

    # Determine which operations to run
    operations = []
    if args.all:
        operations = list(MAINTENANCE_SCRIPTS.keys())
    else:
        if args.hygiene:
            operations.append("hygiene")
        if args.docs:
            operations.append("docs")
        if args.branches:
            operations.append("branches")
        if args.repo:
            operations.append("repo")
        if args.logs:
            operations.append("logs")
        if args.fix:
            operations.append("fix")

    # If no operation specified, show help
    if not operations:
        parser.print_help()
        print("\n" + "=" * 80)
        print("AVAILABLE MAINTENANCE SCRIPTS:")
        print("=" * 80)
        for op, script in MAINTENANCE_SCRIPTS.items():
            print(f"  --{op:10} → {script}")
        return 0

    # Dry run mode
    if args.dry_run:
        print("DRY RUN MODE - Would execute:")
        for op in operations:
            script = MAINTENANCE_SCRIPTS[op]
            print(f"  - {script} with args: {unknown_args}")
        return 0

    # Execute operations
    exit_codes = []
    for op in operations:
        script = MAINTENANCE_SCRIPTS[op]

        # Build arguments for this script
        script_args = unknown_args.copy()

        # Add --dry-run flag if requested
        if args.dry_run and "--dry-run" not in script_args:
            script_args.append("--dry-run")

        # Add --verbose if requested
        if args.verbose and "--verbose" not in script_args:
            script_args.append("--verbose")

        # Add --quick if requested
        if args.quick and "--quick" not in script_args:
            script_args.append("--quick")

        # Run the script
        exit_code = run_script(script, script_args)
        exit_codes.append(exit_code)

        if exit_code != 0:
            print(f"\n⚠️  Warning: {script} exited with code {exit_code}")

    # Summary
    print(f"\n{'=' * 80}")
    print("MAINTENANCE SUMMARY")
    print(f"{'=' * 80}")
    print(f"Operations run: {len(operations)}")
    print(f"Successful: {exit_codes.count(0)}")
    print(f"Failed: {len([c for c in exit_codes if c != 0])}")

    # Return non-zero if any operation failed
    return 0 if all(code == 0 for code in exit_codes) else 1


if __name__ == "__main__":
    sys.exit(main())
