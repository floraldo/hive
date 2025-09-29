#!/usr/bin/env python3
"""
Golden Rules Validation Script for Hive Platform.

Validates compliance with all 19 Golden Rules for architectural governance
across the entire platform.
"""

import sys
from pathlib import Path

# Add hive packages to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages" / "hive-tests" / "src"))

from hive_logging import get_logger
from hive_tests.architectural_validators import run_all_golden_rules

logger = get_logger(__name__)


def validate_platform_compliance() -> bool:
    """
    Run Golden Rules validation across entire Hive platform.

    Returns:
        bool: True if all rules pass, False otherwise
    """
    logger.info("VALIDATING Hive Platform against all Golden Rules...")
    logger.info("=" * 80)

    # Run all golden rules validation
    all_passed, results = run_all_golden_rules(project_root)

    # Display results
    logger.info("\nGOLDEN RULES VALIDATION RESULTS")
    logger.info("=" * 80)

    passed_count = 0
    failed_count = 0

    for rule_name, result in results.items():
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
    else:
        logger.error("FAIL: GOLDEN RULES VIOLATIONS DETECTED - Platform needs attention")
        logger.error("Please fix the violations above to maintain architectural integrity")
        return False


def main():
    """Main entry point."""
    try:
        success = validate_platform_compliance()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Golden Rules validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
