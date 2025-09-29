#!/usr/bin/env python3
"""
Golden Rules Validation Script for hive-ai package.

Validates compliance with all 18 Golden Rules for architectural governance.
"""

import sys
from pathlib import Path

# Add project root to path for importing validators
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root / "packages" / "hive-tests" / "src"))

from hive_tests.architectural_validators import run_all_golden_rules


def validate_hive_ai_compliance() -> bool:
    """
    Run Golden Rules validation specifically for hive-ai package.

    Returns:
        bool: True if all rules pass, False otherwise
    """
    print("VALIDATING hive-ai package against Golden Rules...")
    print("=" * 60)

    # Run all golden rules validation
    all_passed, results = run_all_golden_rules(project_root)

    # Filter results to focus on hive-ai specific violations
    hive_ai_violations = {}
    total_violations = 0

    for rule_name, result in results.items():
        if not result["passed"]:
            # Filter violations related to hive-ai
            ai_violations = [v for v in result["violations"] if "hive-ai" in v or "hive_ai" in v]

            if ai_violations:
                hive_ai_violations[rule_name] = ai_violations
                total_violations += len(ai_violations)

    # Report results
    if not hive_ai_violations:
        print("PASS: All Golden Rules compliance checks PASSED for hive-ai package!")
        print(f"INFO: Validated against {len(results)} rules")
        return True

    print(f"FAIL: Found {total_violations} Golden Rules violations in hive-ai package:")
    print()

    for rule_name, violations in hive_ai_violations.items():
        print(f"RULE: {rule_name}")
        for violation in violations:
            print(f"   - {violation}")
        print()

    return False


def generate_compliance_report() -> None:
    """Generate detailed compliance report for hive-ai package."""
    report_path = project_root / "packages" / "hive-ai" / "GOLDEN_RULES_COMPLIANCE.md"

    print(f"INFO: Generating compliance report: {report_path}")

    # Run validation
    all_passed, results = run_all_golden_rules(project_root)

    # Generate markdown report
    report_content = f"""# Golden Rules Compliance Report - hive-ai Package

Generated on: {Path(__file__).stat().st_mtime}

## Summary

**Overall Status**: {'COMPLIANT' if all_passed else 'NON-COMPLIANT'}

**Rules Evaluated**: {len(results)}
**Rules Passed**: {sum(1 for r in results.values() if r['passed'])}
**Rules Failed**: {sum(1 for r in results.values() if not r['passed'])}

## Rule-by-Rule Analysis

"""

    for rule_name, result in results.items():
        status = "PASS" if result["passed"] else "FAIL"
        report_content += f"### {rule_name}\n\n"
        report_content += f"**Status**: {status}\n\n"

        if not result["passed"]:
            # Filter for hive-ai specific violations
            ai_violations = [v for v in result["violations"] if "hive-ai" in v or "hive_ai" in v]

            if ai_violations:
                report_content += "**hive-ai Specific Violations**:\n\n"
                for violation in ai_violations:
                    report_content += f"- {violation}\n"
                report_content += "\n"
            else:
                report_content += "*No hive-ai specific violations found.*\n\n"

    report_content += f"""
## Architecture Compliance

The hive-ai package has been designed to strictly follow the Hive platform's
architectural principles:

1. **Inherit -> Extend Pattern**: Builds upon existing hive platform packages
2. **Dependency Direction**: Apps -> Packages, no reverse dependencies
3. **Service Layer Discipline**: Clean interfaces in core modules
4. **Interface Contracts**: Type hints and documentation throughout
5. **Error Handling**: Uses hive-error-handling base classes
6. **Logging Standards**: Integrates with hive-logging
7. **Configuration Management**: Uses hive-config patterns
8. **Async Patterns**: Leverages hive-async utilities
9. **Testing Standards**: Comprehensive test coverage with property-based testing

## Implementation Highlights

- **Multi-Provider AI Abstraction**: Unified interface for Anthropic, OpenAI, local models
- **Vector Database Integration**: ChromaDB provider with caching and circuit breakers
- **Property-Based Testing**: Mathematical property verification using Hypothesis
- **Cost Management**: Real-time budget tracking and optimization
- **Agentic Workflows**: Framework for autonomous AI agent orchestration
- **Type Safety**: Complete type annotations throughout codebase
- **Resilience Patterns**: Circuit breakers, retries, graceful degradation

## Validation Commands

To validate compliance:

```bash
# Run full Golden Rules validation
python packages/hive-ai/scripts/validate_golden_rules.py

# Run hive-ai specific tests
cd packages/hive-ai && python -m pytest tests/ -v

# Check type annotations
cd packages/hive-ai && mypy src/
```
"""

    # Write report with UTF-8 encoding
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"SUCCESS: Compliance report generated: {report_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate hive-ai Golden Rules compliance")
    parser.add_argument("--report", action="store_true", help="Generate detailed compliance report")

    args = parser.parse_args()

    if args.report:
        generate_compliance_report()

    # Always run validation
    success = validate_hive_ai_compliance()

    if success:
        print("\nSUCCESS: hive-ai package is fully compliant with Golden Rules!")
        sys.exit(0)
    else:
        print("\nWARNING: Please fix violations before proceeding.")
        sys.exit(1)
