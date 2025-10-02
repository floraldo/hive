#!/usr/bin/env python3
"""
Security-focused Golden Rules validation for CI/CD
"""
import sys
from pathlib import Path

# Add the hive-tests package to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-tests" / "src"))

from hive_tests.ast_validator import EnhancedValidator


def main():
    validator = EnhancedValidator(Path(__file__).parent.parent)
    is_valid, violations_by_rule = validator.validate_all()

    security_violations = []
    performance_violations = []

    for rule_name, violations in violations_by_rule.items():
        if "Unsafe" in rule_name or "Security" in rule_name:
            security_violations.extend(violations)
        elif "Synchronous Calls in Async" in rule_name:
            performance_violations.extend(violations)

    print(f"Security violations: {len(security_violations)}")
    print(f"Performance violations: {len(performance_violations)}")

    if security_violations:
        print("CRITICAL SECURITY VIOLATIONS FOUND:")
        for violation in security_violations[:10]:
            print(f"  - {violation}")
        if len(security_violations) > 10:
            print(f"  ... and {len(security_violations) - 10} more")
        print("ZERO TOLERANCE: Security violations must be fixed immediately!")
        sys.exit(1)

    if performance_violations:
        print("WARNING: Performance violations detected!")
        for violation in performance_violations[:5]:
            print(f"  - {violation}")
        print("These should be addressed for optimal async performance.")

    print("Security scan passed!")


if __name__ == "__main__":
    main()
