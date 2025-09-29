#!/usr/bin/env python3
"""
Check current violations for commit readiness
"""
import sys
from collections import defaultdict
from pathlib import Path

# Add the hive-tests package to the path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "hive-tests" / "src"))

from hive_tests.ast_validator import EnhancedValidator


def main():
    project_root = Path(__file__).parent
    validator = EnhancedValidator(project_root)

    print("COMMIT READINESS CHECK")
    print("=" * 60)

    is_valid, violations_by_rule = validator.validate_all()

    if is_valid:
        print("ALL GOLDEN RULES PASSED! Ready to commit!")
        return 0

    total_violations = sum(len(violations) for violations in violations_by_rule.values())

    print(f"Total violations: {total_violations}")
    print()

    # Analyze violations by context
    false_positives = 0
    legitimate_issues = 0

    for rule_name, violations in violations_by_rule.items():
        print(f"{rule_name}: {len(violations)} violations")

        rule_false_positives = 0
        rule_legitimate = 0

        for violation in violations:
            # Check if this is likely a false positive
            is_false_positive = (
                "/tests/" in violation
                or "/scripts/" in violation
                or "test_" in violation
                or "demo_" in violation
                or "run_" in violation
                or "/archive/" in violation
                or ".backup" in violation
            )

            if is_false_positive:
                rule_false_positives += 1
                false_positives += 1
            else:
                rule_legitimate += 1
                legitimate_issues += 1

        if rule_false_positives > 0:
            print(f"  - False positives: {rule_false_positives}")
        if rule_legitimate > 0:
            print(f"  - Legitimate issues: {rule_legitimate}")

        # Show some examples of legitimate issues
        if rule_legitimate > 0:
            print("  Examples:")
            count = 0
            for violation in violations:
                if not (
                    "/tests/" in violation
                    or "/scripts/" in violation
                    or "test_" in violation
                    or "demo_" in violation
                    or "run_" in violation
                    or "/archive/" in violation
                    or ".backup" in violation
                ):
                    print(f"    - {violation}")
                    count += 1
                    if count >= 3:
                        break
        print()

    print("SUMMARY:")
    print(f"  Total violations: {total_violations}")
    print(f"  False positives: {false_positives}")
    print(f"  Legitimate issues: {legitimate_issues}")
    print()

    if false_positives > legitimate_issues:
        print("RECOMMENDATION: Update rules to eliminate false positives")
        print("Most violations are in test/script/demo files that should be exempt")
    elif legitimate_issues < 50:
        print("RECOMMENDATION: Fix the remaining legitimate issues")
        print("Small number of real issues that can be addressed quickly")
    else:
        print("RECOMMENDATION: Commit current state and address issues incrementally")
        print("Large number of legitimate issues - address over time")

    return 1


if __name__ == "__main__":
    sys.exit(main())
