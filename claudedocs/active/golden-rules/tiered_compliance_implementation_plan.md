# Tiered Golden Rules Implementation Plan

**Timeline**: 2-3 hours total implementation
**Impact**: Enable flexible compliance across development phases

---

## Step 1: Add Severity Metadata (30 min)

### 1.1 Add Severity Enum to architectural_validators.py

```python
# At top of file after imports
from enum import Enum

class RuleSeverity(Enum):
    """Severity levels for Golden Rules."""
    CRITICAL = 1  # Never compromise - system breaks
    ERROR = 2     # Fix before merge - tech debt grows
    WARNING = 3   # Fix at milestones - quality issues
    INFO = 4      # Nice to have - best practices
```

### 1.2 Create Rule Registry with Severity Mappings

```python
# After RuleSeverity definition

GOLDEN_RULES_REGISTRY = [
    # CRITICAL (Level 1) - Never Compromise
    {
        "name": "No sys.path Manipulation",
        "validator": validate_no_syspath_hacks,
        "severity": RuleSeverity.CRITICAL,
        "description": "Prevents import system corruption"
    },
    {
        "name": "Single Config Source",
        "validator": validate_single_config_source,
        "severity": RuleSeverity.CRITICAL,
        "description": "Prevents setup.py/pyproject.toml conflicts"
    },
    {
        "name": "No Hardcoded Env Values",
        "validator": validate_no_hardcoded_env_values,
        "severity": RuleSeverity.CRITICAL,
        "description": "Security - no secrets in code"
    },
    {
        "name": "Package vs. App Discipline",
        "validator": validate_package_app_discipline,
        "severity": RuleSeverity.CRITICAL,
        "description": "Core architectural boundary"
    },
    {
        "name": "App Contracts",
        "validator": validate_app_contracts,
        "severity": RuleSeverity.CRITICAL,
        "description": "Application interface stability"
    },

    # ERROR (Level 2) - Fix Before Merge
    {
        "name": "Dependency Direction",
        "validator": validate_dependency_direction,
        "severity": RuleSeverity.ERROR,
        "description": "Packages cannot import apps"
    },
    {
        "name": "Error Handling Standards",
        "validator": validate_error_handling_standards,
        "severity": RuleSeverity.ERROR,
        "description": "Exceptions inherit from BaseError"
    },
    {
        "name": "Logging Standards",
        "validator": validate_logging_standards,
        "severity": RuleSeverity.ERROR,
        "description": "Use hive_logging, no print()"
    },
    {
        "name": "No Global State Access",
        "validator": validate_no_global_state_access,
        "severity": RuleSeverity.ERROR,
        "description": "Use DI pattern, not get_config()"
    },
    {
        "name": "Async Pattern Consistency",
        "validator": validate_async_pattern_consistency,
        "severity": RuleSeverity.ERROR,
        "description": "Async functions end with _async"
    },
    {
        "name": "Interface Contracts",
        "validator": validate_interface_contracts,
        "severity": RuleSeverity.ERROR,
        "description": "Type hints on public functions"
    },
    {
        "name": "Communication Patterns",
        "validator": validate_communication_patterns,
        "severity": RuleSeverity.ERROR,
        "description": "Event bus usage patterns"
    },
    {
        "name": "Service Layer Discipline",
        "validator": validate_service_layer_discipline,
        "severity": RuleSeverity.ERROR,
        "description": "Service layer separation"
    },

    # WARNING (Level 3) - Fix at Milestones
    {
        "name": "Test Coverage Mapping",
        "validator": validate_test_coverage_mapping,
        "severity": RuleSeverity.WARNING,
        "description": "Source files have test files"
    },
    {
        "name": "Test File Quality",
        "validator": validate_test_file_quality,
        "severity": RuleSeverity.WARNING,
        "description": "Tests follow standards"
    },
    {
        "name": "Inherit→Extend Pattern",
        "validator": validate_inherit_extend_pattern,
        "severity": RuleSeverity.WARNING,
        "description": "Infrastructure vs business logic"
    },
    {
        "name": "Package Naming Consistency",
        "validator": validate_package_naming_consistency,
        "severity": RuleSeverity.WARNING,
        "description": "Follow hive-* convention"
    },
    {
        "name": "Development Tools Consistency",
        "validator": validate_development_tools_consistency,
        "severity": RuleSeverity.WARNING,
        "description": "Standardized tooling"
    },
    {
        "name": "CLI Pattern Consistency",
        "validator": validate_cli_pattern_consistency,
        "severity": RuleSeverity.WARNING,
        "description": "CLI interface patterns"
    },
    {
        "name": "Pyproject Dependency Usage",
        "validator": validate_pyproject_dependency_usage,
        "severity": RuleSeverity.WARNING,
        "description": "No unused dependencies"
    },

    # INFO (Level 4) - Nice to Have
    {
        "name": "Unified Tool Configuration",
        "validator": validate_unified_tool_configuration,
        "severity": RuleSeverity.INFO,
        "description": "Consolidated config files"
    },
    {
        "name": "Python Version Consistency",
        "validator": validate_python_version_consistency,
        "severity": RuleSeverity.INFO,
        "description": "Single Python version"
    },
    {
        "name": "No Synchronous Calls in Async Code",
        "validator": validate_async_blocking_calls,
        "severity": RuleSeverity.INFO,
        "description": "Use aiofiles in async functions"
    },
    {
        "name": "Colocated Tests",
        "validator": validate_colocated_tests,
        "severity": RuleSeverity.INFO,
        "description": "Tests near source code"
    },
]
```

### 1.3 Update run_all_golden_rules() Function

```python
def run_all_golden_rules(
    project_root: Path,
    scope_files: list[Path] | None = None,
    engine: str = "ast",
    max_severity: RuleSeverity = RuleSeverity.INFO  # NEW parameter
) -> tuple[bool, dict]:
    """
    Run Golden Rules validation with severity filtering.

    Args:
        project_root: Root directory of the project
        scope_files: Optional list of specific files to validate
        engine: Validation engine ('ast', 'legacy', 'both')
        max_severity: Maximum severity level to enforce (default: INFO = all rules)

    Returns:
        Tuple of (all_passed, results_dict)
    """
    results = {}
    all_passed = True

    # Filter rules by severity
    rules_to_run = [
        rule for rule in GOLDEN_RULES_REGISTRY
        if rule["severity"].value <= max_severity.value
    ]

    logger.info(f"Enforcing {len(rules_to_run)} rules at {max_severity.name} level or higher")

    for rule in rules_to_run:
        try:
            passed, violations = _cached_validator(
                rule["name"],
                rule["validator"],
                project_root,
                scope_files
            )
            results[rule["name"]] = {
                "passed": passed,
                "violations": violations,
                "severity": rule["severity"].name,
                "description": rule["description"]
            }
            if not passed:
                all_passed = False
        except Exception as e:
            results[rule["name"]] = {
                "passed": False,
                "violations": [f"Validation error: {e}"],
                "severity": rule["severity"].name,
                "description": rule["description"]
            }
            all_passed = False

    return all_passed, results
```

---

## Step 2: Update validate_golden_rules.py CLI (30 min)

### 2.1 Add --level Argument

```python
def main():
    """Main entry point for Golden Rules validation."""
    parser = argparse.ArgumentParser(
        description="Validate Hive Platform against Golden Rules with tiered severity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Rapid development - only critical rules (fast)
  python scripts/validate_golden_rules.py --level CRITICAL

  # Active development - critical + error rules
  python scripts/validate_golden_rules.py --level ERROR

  # Sprint cleanup - add warnings
  python scripts/validate_golden_rules.py --level WARNING

  # Production release - all rules (default)
  python scripts/validate_golden_rules.py --level INFO
  python scripts/validate_golden_rules.py  # same as INFO

  # Incremental validation (fast)
  python scripts/validate_golden_rules.py --incremental --level ERROR
        """
    )

    parser.add_argument(
        "--level",
        type=str,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO"],
        default="INFO",
        help="Severity level to enforce (default: INFO = all rules)"
    )

    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only validate changed files (git diff)"
    )

    parser.add_argument(
        "--app",
        type=str,
        help="Validate specific app only (e.g., 'ecosystemiser')"
    )

    parser.add_argument(
        "--engine",
        type=str,
        choices=["ast", "legacy", "both"],
        default="ast",
        help="Validation engine to use (default: ast)"
    )

    args = parser.parse_args()

    # Determine scope
    if args.incremental:
        scope_files = get_changed_files()
        if not scope_files:
            logger.info("No changed Python files found, running full validation")
            scope_files = None
    elif args.app:
        scope_files = get_app_files(args.app)
        if not scope_files:
            logger.error(f"No files found for app: {args.app}")
            sys.exit(1)
    else:
        scope_files = None

    # Convert level string to RuleSeverity enum
    from hive_tests.architectural_validators import RuleSeverity
    severity = RuleSeverity[args.level]

    # Run validation
    success = validate_platform_compliance(
        scope_files=scope_files,
        engine=args.engine,
        max_severity=severity
    )

    sys.exit(0 if success else 1)
```

### 2.2 Update validate_platform_compliance() Function

```python
def validate_platform_compliance(
    scope_files: list[Path] | None = None,
    engine: str = "ast",
    max_severity: RuleSeverity = RuleSeverity.INFO
) -> bool:
    """
    Run Golden Rules validation with severity filtering.

    Args:
        scope_files: Optional list of specific files to validate
        engine: Validation engine ('ast', 'legacy', 'both')
        max_severity: Maximum severity level to enforce

    Returns:
        bool: True if all rules pass, False otherwise
    """
    if scope_files:
        logger.info(f"VALIDATING {len(scope_files)} files")
        logger.info("Scope: Incremental validation")
    else:
        logger.info("VALIDATING Hive Platform")
        logger.info("Scope: Full platform")

    logger.info(f"Severity Level: {max_severity.name}")
    logger.info(f"Engine: {engine.upper()} validator")
    logger.info("=" * 80)

    # Run validation with severity filter
    all_passed, results = run_all_golden_rules(
        project_root,
        scope_files,
        engine=engine,
        max_severity=max_severity
    )

    # Display results grouped by severity
    logger.info("\nGOLDEN RULES VALIDATION RESULTS")
    logger.info("=" * 80)

    # Group by severity
    by_severity = {}
    for rule_name, result in results.items():
        severity = result["severity"]
        if severity not in by_severity:
            by_severity[severity] = []
        by_severity[severity].append((rule_name, result))

    # Display in severity order
    for severity_level in ["CRITICAL", "ERROR", "WARNING", "INFO"]:
        if severity_level not in by_severity:
            continue

        rules = by_severity[severity_level]
        logger.info(f"\n{severity_level} Rules ({len(rules)} rules)")
        logger.info("-" * 80)

        for rule_name, result in rules:
            status = "PASS" if result["passed"] else "FAIL"
            emoji = "✅" if result["passed"] else "❌"
            logger.info(f"{status:<10} {rule_name}")

            if not result["passed"]:
                # Show first 3 violations
                for violation in result["violations"][:3]:
                    logger.error(f"         > {violation}")

                if len(result["violations"]) > 3:
                    logger.error(f"         ... and {len(result['violations']) - 3} more")

    # Summary
    logger.info("\n" + "=" * 80)
    passed_count = sum(1 for r in results.values() if r["passed"])
    failed_count = len(results) - passed_count
    logger.info(f"SUMMARY: {passed_count} passed, {failed_count} failed")
    logger.info(f"Severity Level: {max_severity.name}")

    if all_passed:
        logger.info(f"SUCCESS: All {max_severity.name}-level rules passed!")
        return True
    else:
        logger.error(f"FAIL: {failed_count} rule violations at {max_severity.name} level")
        return False
```

---

## Step 3: Update .claude/CLAUDE.md (15 min)

Add new section after "Quality Gates":

```markdown
## 🎚️ Tiered Compliance System

### Development Phase Strategy

**Philosophy**: "Fast in development, tight at milestones"

#### 🚀 Rapid Development (Prototyping)
```bash
python scripts/validate_golden_rules.py --level CRITICAL
```
- Enforces: 5 critical rules only
- Speed: ~5 seconds
- Use when: Building PoC, exploring ideas

#### 🏗️ Active Development (Feature Work)
```bash
python scripts/validate_golden_rules.py --level ERROR
```
- Enforces: 13 rules (CRITICAL + ERROR)
- Speed: ~15 seconds
- Use when: Building features, before PR

#### 📦 Sprint Boundaries (Cleanup)
```bash
python scripts/validate_golden_rules.py --level WARNING
```
- Enforces: 20 rules (+ WARNING level)
- Speed: ~25 seconds
- Use when: End of sprint, before merge to main

#### 🎯 Production Releases (Zero Tolerance)
```bash
python scripts/validate_golden_rules.py --level INFO
# OR (default)
python scripts/validate_golden_rules.py
```
- Enforces: All 24 rules
- Speed: ~30 seconds
- Use when: Before v1.0, v2.0, major releases

### Severity Levels Explained

**🔴 CRITICAL**: System breaks, security issues, deployment failures
**🟠 ERROR**: Technical debt, maintainability issues
**🟡 WARNING**: Quality issues, fix at milestones
**🟢 INFO**: Best practices, nice to have

See `claudedocs/golden_rules_tiered_compliance_system.md` for complete guide.
```

---

## Step 4: Update CI/CD Workflows (15 min)

### 4.1 Update .github/workflows/golden-rules.yml

```yaml
name: Golden Rules Validation

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Validate Golden Rules (ERROR level for PRs)
        if: github.event_name == 'pull_request'
        run: |
          python scripts/validate_golden_rules.py --level ERROR --incremental

      - name: Validate Golden Rules (WARNING level for main)
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: |
          python scripts/validate_golden_rules.py --level WARNING
```

### 4.2 Create release validation workflow

```yaml
# .github/workflows/release-validation.yml
name: Release Validation

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  full-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Full Golden Rules Validation (INFO level)
        run: |
          python scripts/validate_golden_rules.py --level INFO

      - name: Fail if any violations
        if: failure()
        run: |
          echo "❌ Release validation failed - fix all violations before releasing"
          exit 1
```

---

## Testing Plan

### Test 1: Verify Severity Filtering
```bash
# Should show only 5 rules
python scripts/validate_golden_rules.py --level CRITICAL

# Should show 13 rules
python scripts/validate_golden_rules.py --level ERROR

# Should show 20 rules
python scripts/validate_golden_rules.py --level WARNING

# Should show all 24 rules
python scripts/validate_golden_rules.py --level INFO
```

### Test 2: Verify Output Format
```bash
# Check that output shows severity grouping
python scripts/validate_golden_rules.py --level ERROR | grep "CRITICAL Rules"
python scripts/validate_golden_rules.py --level ERROR | grep "ERROR Rules"
```

### Test 3: Verify CI/CD Integration
```bash
# Create test PR, verify ERROR level enforcement
git checkout -b test/tiered-compliance
# Make changes
git commit -m "test: verify tiered compliance"
git push
# Check GitHub Actions runs with --level ERROR
```

---

## Rollout Timeline

**Week 1: Implementation**
- Day 1-2: Add severity metadata and registry
- Day 3: Update CLI with --level flag
- Day 4: Update documentation
- Day 5: Test and validate

**Week 2: Team Adoption**
- Day 1: Team demo and training
- Day 2-3: Update CI/CD workflows
- Day 4-5: Monitor and adjust

**Week 3: Optimization**
- Gather feedback
- Tune severity assignments
- Refine enforcement strategy

---

## Success Criteria

✅ All developers can run `--level CRITICAL` in < 10 seconds
✅ PR validation runs at ERROR level automatically
✅ Sprint reviews check WARNING level
✅ Release process enforces INFO level (all rules)
✅ Zero Code Red syntax errors (CRITICAL level working)
✅ Team reports improved development velocity
✅ Technical debt visibility improved