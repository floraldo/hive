#!/usr/bin/env python3
# Security: subprocess calls in this script use system tools (git) with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal validation tooling.

"""Golden Rules Validation Script for Hive Platform.

Validates compliance with 24 Golden Rules for architectural governance
across the entire platform with tiered severity enforcement.

Severity Levels:
- CRITICAL (5 rules): System breaks, security, deployment failures
- ERROR (13 rules): Technical debt, maintainability issues
- WARNING (20 rules): Quality issues, test coverage
- INFO (24 rules): All rules, best practices

Supports multiple validation modes:
- Full validation: Entire codebase (~5-30s depending on level)
- Incremental: Only changed files (~2-5s)
- App-scoped: Specific app only (~5-15s)
- Severity filtering: Choose enforcement level for development phase
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Add hive packages to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages" / "hive-tests" / "src"))

from hive_logging import get_logger
from hive_tests.architectural_validators import RuleSeverity, run_all_golden_rules

logger = get_logger(__name__)


def _get_rule_count(severity: RuleSeverity) -> int:
    """Get the number of rules enforced at a given severity level."""
    rule_counts = {
        RuleSeverity.CRITICAL: 5,
        RuleSeverity.ERROR: 13,
        RuleSeverity.WARNING: 20,
        RuleSeverity.INFO: 24,
    }
    return rule_counts.get(severity, 24)


def get_changed_files() -> list[Path]:
    """Get list of changed Python files using git.

    Returns list of changed/staged Python files relative to HEAD.
    Falls back to all files if not in git repo.
    """
    try:
        # Get staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=True,
        )
        staged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Get unstaged changes
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=True,
        )
        unstaged = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Combine and filter for Python files
        all_changed = set(staged + unstaged)
        python_files = [project_root / f for f in all_changed if f.endswith(".py") and Path(project_root / f).exists()]

        return python_files

    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("Not in git repo or git not available, using full validation")
        return []


def get_app_files(app_name: str) -> list[Path]:
    """Get all Python files for a specific app.

    Args:
        app_name: Name of the app (e.g., 'ecosystemiser', 'hive-orchestrator')

    Returns:
        List of Python files in the app directory

    """
    app_dir = project_root / "apps" / app_name
    if not app_dir.exists():
        logger.error(f"App directory not found: {app_dir}")
        return []

    return list(app_dir.rglob("*.py"))


def validate_platform_compliance(
    scope_files: list[Path] | None = None,
    quick: bool = False,
    engine: str = "ast",
    severity_level: RuleSeverity = RuleSeverity.INFO,
) -> bool:
    """Run Golden Rules validation across Hive platform.

    Args:
        scope_files: Optional list of specific files to validate
        quick: If True, only validate critical rules (deprecated, use severity_level instead)
        engine: Validation engine ('ast', 'legacy', 'registry', 'both')
        severity_level: Maximum severity level to enforce (CRITICAL, ERROR, WARNING, INFO)

    Returns:
        bool: True if all rules pass, False otherwise

    """
    if scope_files:
        logger.info(f"VALIDATING {len(scope_files)} files against Golden Rules...")
        logger.info("Scope: Incremental validation")
    else:
        logger.info("VALIDATING Hive Platform against all Golden Rules...")
        logger.info("Scope: Full platform")

    # Legacy quick flag support
    if quick:
        logger.info("Mode: Quick (critical rules only) - [DEPRECATED: use --level CRITICAL]")
        severity_level = RuleSeverity.CRITICAL

    logger.info(f"Engine: {engine.upper()} validator")
    logger.info(f"Severity Level: {severity_level.name} (enforcing {_get_rule_count(severity_level)} rules)")
    logger.info("=" * 80)

    # Run all golden rules validation with file-level scoping and severity filtering
    all_passed, results = run_all_golden_rules(
        project_root,
        scope_files,
        engine=engine,
        max_severity=severity_level,
    )

    # Display results grouped by severity
    logger.info("\nGOLDEN RULES VALIDATION RESULTS")
    logger.info("=" * 80)

    passed_count = 0
    failed_count = 0

    # Group results by severity for better readability
    results_by_severity = {}
    for rule_name, result in results.items():
        severity = result.get("severity", "INFO")
        if severity not in results_by_severity:
            results_by_severity[severity] = []
        results_by_severity[severity].append((rule_name, result))

    # Display in severity order
    for severity in ["CRITICAL", "ERROR", "WARNING", "INFO"]:
        if severity not in results_by_severity:
            continue

        severity_results = results_by_severity[severity]
        logger.info(f"\n[{severity}] - {len(severity_results)} rules")
        logger.info("-" * 80)

        for rule_name, result in severity_results:
            status = "PASS" if result["passed"] else "FAIL"
            logger.info(f"{status:<10} {rule_name}")

            if result["passed"]:
                passed_count += 1
            else:
                failed_count += 1
                # Show violations for failed rules
                for violation in result["violations"][:5]:  # Show first 5 violations
                    logger.error(f"         > {violation}")

                if len(result["violations"]) > 5:
                    logger.error(f"         ... and {len(result['violations']) - 5} more violations")

    # Summary
    logger.info("=" * 80)
    logger.info(f"SUMMARY: {passed_count} passed, {failed_count} failed")

    if all_passed:
        logger.info("SUCCESS: ALL GOLDEN RULES PASSED - Platform is architecturally sound!")
        return True
    logger.error("FAIL: GOLDEN RULES VIOLATIONS DETECTED - Platform needs attention")
    logger.error("Please fix the violations above to maintain architectural integrity")
    return False


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Validate Hive platform compliance with Golden Rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full validation with all rules (default)
  python scripts/validation/validate_golden_rules.py

  # Fast development - only critical rules
  python scripts/validation/validate_golden_rules.py --level CRITICAL

  # Before PR merge - critical and error rules
  python scripts/validation/validate_golden_rules.py --level ERROR

  # Sprint boundaries - include warnings
  python scripts/validation/validate_golden_rules.py --level WARNING

  # Incremental validation with error level
  python scripts/validation/validate_golden_rules.py --incremental --level ERROR

  # App-scoped validation
  python scripts/validation/validate_golden_rules.py --app ecosystemiser --level ERROR

Severity Levels:
  CRITICAL:  5 rules  (~5s)  - System breaks, security, deployment
  ERROR:     13 rules (~15s) - Technical debt, maintainability
  WARNING:   20 rules (~25s) - Quality issues, tests
  INFO:      24 rules (~30s) - All rules (default)

Performance:
  Full validation:    ~30s (INFO), ~5s (CRITICAL)
  Incremental:        ~2-5s (5-20 files)
  App-scoped:         ~5-15s (150-200 files)
        """,
    )

    parser.add_argument(
        "--incremental",
        "-i",
        action="store_true",
        help="Validate only changed files (git diff)",
    )

    parser.add_argument(
        "--app",
        "-a",
        type=str,
        help="Validate specific app only (e.g., ecosystemiser, hive-orchestrator)",
    )

    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Quick validation (critical rules only)",
    )

    parser.add_argument(
        "--clear-cache",
        "-c",
        action="store_true",
        help="Clear validation cache before running",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all violations (not just first 5)",
    )

    parser.add_argument(
        "--engine",
        "-e",
        type=str,
        choices=["ast", "legacy", "registry", "both"],
        default="registry",
        help="Validation engine: registry (default, with severity filtering), ast (full AST), legacy (deprecated), both (comparison)",
    )

    parser.add_argument(
        "--level",
        "-l",
        type=str,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO"],
        default="INFO",
        help="Severity level: CRITICAL (5 rules, ~5s), ERROR (13 rules, ~15s), WARNING (20 rules, ~25s), INFO (24 rules, ~30s, default)",
    )

    args = parser.parse_args()

    try:
        scope_files = None
        # Handle cache clearing
        if args.clear_cache:
            from validation_cache import ValidationCache

            cache = ValidationCache()
            deleted = cache.clear_cache()
            logger.info(f"Cleared {deleted} cached validation results")

        # Determine scope
        if args.incremental:
            scope_files = get_changed_files()
            if not scope_files:
                logger.warning("No changed files detected, running full validation")
                scope_files = None
            else:
                logger.info(f"Found {len(scope_files)} changed Python files")

        elif args.app:
            scope_files = get_app_files(args.app)
            if not scope_files:
                logger.error(f"No files found for app: {args.app}")
                sys.exit(1)
            logger.info(f"Found {len(scope_files)} files in app: {args.app}")

        # Convert level string to RuleSeverity enum
        severity_map = {
            "CRITICAL": RuleSeverity.CRITICAL,
            "ERROR": RuleSeverity.ERROR,
            "WARNING": RuleSeverity.WARNING,
            "INFO": RuleSeverity.INFO,
        }
        severity_level = severity_map[args.level]

        # Run validation
        success = validate_platform_compliance(
            scope_files=scope_files,
            quick=args.quick,
            engine=args.engine,
            severity_level=severity_level,
        )

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Golden Rules validation failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
