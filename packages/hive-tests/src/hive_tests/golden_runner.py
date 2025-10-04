#!/usr/bin/env python3
# ruff: noqa: S603
# Security: subprocess calls in this runner use sys.executable with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal testing tooling.

"""
Golden Test Runner - Convenient CLI for running architectural tests

This provides a simple way to run golden rule tests either globally
or for a specific app context.

Usage:
    # Run all golden tests
    golden-test

    # Run tests for a specific app
    golden-test --app hive-orchestrator

    # Run tests with verbose output
    golden-test -v

    # Run specific test
    golden-test --test test_dependency_direction
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from hive_logging import get_logger

logger = get_logger(__name__)


def run_global_tests(verbose: bool = False, test_name: str | None = None):
    """Run the global golden rule tests."""
    test_file = Path(__file__).parent.parent.parent / "tests" / "test_architecture.py"

    if not test_file.exists():
        logger.error(f"Error: Golden test file not found at {test_file}")
        return 1

    cmd = ["pytest", str(test_file)]

    if verbose:
        cmd.append("-v")

    if test_name:
        cmd.append(f"-k {test_name}")

    logger.info("Running global golden rule tests...")
    logger.info(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode


def run_app_tests(app_name: str, verbose: bool = False, test_name: str | None = None):
    """Run golden rule tests for a specific app."""
    project_root = Path(__file__).parent.parent.parent.parent.parent,
    app_test_file = project_root / "apps" / app_name / "tests" / "test_golden_rules.py"

    if not app_test_file.exists():
        logger.warning(f"Warning: App '{app_name}' doesn't have local golden rule tests")
        logger.info(f"Expected at: {app_test_file}")
        logger.info("Running global tests instead...")
        return run_global_tests(verbose, test_name)

    cmd = ["pytest", str(app_test_file)]

    if verbose:
        cmd.append("-v")

    if test_name:
        cmd.append(f"-k {test_name}")

    logger.info(f"Running golden rule tests for app: {app_name}")
    logger.info(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode


def list_apps():
    """List all available apps."""
    project_root = Path(__file__).parent.parent.parent.parent.parent,
    apps_dir = project_root / "apps"

    if not apps_dir.exists():
        logger.error("Error: apps directory not found")
        return []

    apps = [d.name for d in apps_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    return apps


def main() -> None:
    """Main entry point for the golden test runner."""
    parser = argparse.ArgumentParser(
        description="Run Hive golden rule architectural tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=""",
Examples:
    golden-test                          # Run all global tests,
    golden-test --app hive-orchestrator  # Run tests for specific app,
    golden-test -v                       # Run with verbose output,
    golden-test --list-apps              # List available apps,
    golden-test --test test_app_contract # Run specific test,
        """,
    )

    parser.add_argument("--app", help="Run tests for a specific app", type=str, metavar="APP_NAME")

    parser.add_argument("-v", "--verbose", help="Verbose test output", action="store_true")

    parser.add_argument("--test", help="Run a specific test by name", type=str, metavar="TEST_NAME")

    parser.add_argument("--list-apps", help="List all available apps", action="store_true")

    args = parser.parse_args()

    if args.list_apps:
        apps = list_apps()
        if apps:
            logger.info("Available apps:")
            for app in sorted(apps):
                logger.info(f"  - {app}")
        else:
            logger.info("No apps found")
        return 0

    # Run the appropriate tests
    if args.app:
        return run_app_tests(args.app, args.verbose, args.test)
    else:
        return run_global_tests(args.verbose, args.test)


if __name__ == "__main__":
    sys.exit(main())
