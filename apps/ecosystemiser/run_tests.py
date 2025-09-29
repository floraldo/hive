#!/usr/bin/env python
"""
Comprehensive test runner for EcoSystemiser v3.0

Consolidates all testing infrastructure into a single entry point.
"""

import argparse

from hive_logging import get_logger

logger = get_logger(__name__)
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def run_command(cmd: list[str], description: str) -> dict[str, Any]:
    """Run a command and return results."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Running: {description}")
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info("=" * 60)

    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start_time

    if result.returncode == 0:
        logger.info(f"✅ PASSED ({duration:.1f}s)")
        if result.stdout:
            logger.info(f"Output: {result.stdout.strip()}")
    else:
        logger.info(f"❌ FAILED ({duration:.1f}s)")
        if result.stderr:
            logger.info(f"Error: {result.stderr.strip()}")
        if result.stdout:
            logger.info(f"Output: {result.stdout.strip()}")

    return {
        "success": result.returncode == 0,
        "duration": duration,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_unit_tests() -> dict[str, Any]:
    """Run unit tests with pytest."""
    return run_command(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        "Unit Tests (pytest)",
    )


def run_integration_tests() -> dict[str, Any]:
    """Run integration tests."""
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_discovery_engine_e2e.py",
            "tests/test_ga_golden_datasets.py",
            "tests/test_mc_golden_datasets.py",
            "-v",
        ],
        "Discovery Engine Integration Tests",
    )


def run_all_tests(args: argparse.Namespace) -> None:
    """Run all test suites and generate summary."""

    logger.info("\n🧪 EcoSystemiser v3.0 - Comprehensive Test Suite")
    logger.info(f"Working directory: {Path.cwd()}")
    logger.info(f"Python: {sys.executable}")

    test_suites = []

    if args.unit or args.all:
        test_suites.append(("Unit Tests", run_unit_tests))

    if args.integration or args.all:
        test_suites.append(("Integration Tests", run_integration_tests))

    # Run all selected test suites
    results = {}
    start_time = time.time()

    for name, test_func in test_suites:
        try:
            results[name] = test_func()
        except Exception as e:
            results[name] = {"success": False, "duration": 0, "error": str(e)}

    total_duration = time.time() - start_time

    # Generate summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")

    passed = failed = 0
    total_test_time = 0

    for name, result in results.items():
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        duration = result.get("duration", 0)
        total_test_time += duration

        logger.info(f"{name:30s} {status:10s} ({duration:.1f}s)")

        if result["success"]:
            passed += 1
        else:
            failed += 1
            if "error" in result:
                logger.info(f"   Error: {result['error']}")

    logger.info(f"\n📊 Results: {passed} passed, {failed} failed")
    logger.info(f"⏱️  Total time: {total_duration:.1f}s (tests: {total_test_time:.1f}s)")

    if failed == 0:
        logger.info("\n🎉 All tests passed! EcoSystemiser v3.0 is ready for deployment.")
        sys.exit(0)
    else:
        logger.info(f"\n⚠️  {failed} test suite(s) failed. Please review the output above.")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="EcoSystemiser v3.0 Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --all              # Run all tests
  python run_tests.py --unit             # Unit tests only
  python run_tests.py --integration      # Integration tests only
        """,
    )

    parser.add_argument("--all", action="store_true", help="Run all test suites")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")

    args = parser.parse_args()

    # Default to all if no specific tests requested
    if not any([args.unit, args.integration]):
        args.all = True

    run_all_tests(args)


if __name__ == "__main__":
    main()
