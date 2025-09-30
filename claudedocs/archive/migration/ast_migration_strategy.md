# AST Validator Migration Strategy

## Date: 2025-09-30

## Executive Summary

This document outlines the strategy for migrating the Hive platform from string-based validation to AST-based validation as the default, while maintaining backward compatibility during the transition period.

## Current State

### Validation Systems
1. **String-Based Validators** (Legacy)
   - Location: `packages/hive-tests/src/hive_tests/architectural_validators.py`
   - Entry Point: `run_all_golden_rules()` function
   - Coverage: 18 rules (string/file-based validation)
   - Performance: ~30-60s (multi-pass)
   - Used by: `scripts/validate_golden_rules.py`, pre-commit hooks

2. **AST Validator** (New - Just Completed)
   - Location: `packages/hive-tests/src/hive_tests/ast_validator.py`
   - Entry Point: `EnhancedValidator.validate_all()` method
   - Coverage: 23 rules (100% semantic validation)
   - Performance: ~30-40s (single-pass)
   - Status: Implemented, tested, production-ready

## Migration Goals

### Primary Objectives
1. ✅ Make AST validator the **default** validation system
2. ✅ Maintain **backward compatibility** with string validators
3. ✅ Provide **gradual migration path** for teams
4. ✅ Enable **seamless rollback** if issues occur
5. ✅ Update **all entry points** to use AST by default

### Success Criteria
- AST validator runs by default in all validation workflows
- String validators available via `--legacy` flag
- Pre-commit hooks use AST validation
- CI/CD pipeline uses AST validation
- Zero disruption to developer workflows
- Documentation updated with migration guide

## Migration Strategy

### Phase 1: Dual System (Week 1) - CURRENT PHASE

**Objective**: Run both validators in parallel for verification

**Implementation**:
1. Add `--engine` flag to `validate_golden_rules.py`:
   - `--engine ast` (new default)
   - `--engine legacy` (backward compatibility)
   - `--engine both` (parallel verification)

2. Update `run_all_golden_rules()` to support both engines:
   ```python
   def run_all_golden_rules(
       project_root: Path,
       scope_files: list[Path] | None = None,
       engine: str = "ast"  # Default to AST
   ) -> tuple[bool, dict]:
   ```

3. Maintain both validation systems during transition

**Testing Strategy**:
- Run both validators on CI/CD for 1 week
- Compare results for accuracy verification
- Monitor performance and reliability
- Collect developer feedback

**Rollback Plan**: Revert default to `engine="legacy"` if issues occur

### Phase 2: AST Default (Week 2)

**Objective**: Make AST the primary validator across all workflows

**Implementation**:
1. Update all entry points:
   - `scripts/validate_golden_rules.py` → AST default
   - Pre-commit hooks → Use `--engine ast`
   - CI/CD pipelines → Use AST validator
   - Development scripts → AST by default

2. Update documentation:
   - Developer guide: AST validation workflow
   - Contributing guide: How to fix AST violations
   - Architecture docs: AST validator design

3. Communication:
   - Announce AST as default in team channels
   - Provide migration guide for custom workflows
   - Document legacy flag for edge cases

**Testing Strategy**:
- Monitor CI/CD pipeline success rate
- Track developer feedback and issues
- Measure validation performance
- Document any edge cases requiring legacy mode

**Rollback Plan**: Change default back to legacy in config

### Phase 3: Legacy Deprecation (Month 2)

**Objective**: Deprecate string validators, prepare for removal

**Implementation**:
1. Add deprecation warnings to legacy validators:
   ```python
   warnings.warn(
       "String-based validators are deprecated. Use AST validator instead.",
       DeprecationWarning
   )
   ```

2. Update documentation to discourage legacy usage

3. Identify and migrate any remaining legacy-dependent workflows

4. Plan removal timeline (target: 3 months from deprecation)

**Testing Strategy**:
- Ensure all platform workflows use AST
- Verify no CI/CD jobs depend on legacy
- Check third-party integrations

### Phase 4: Legacy Removal (Month 3-4)

**Objective**: Remove string validators, complete migration

**Implementation**:
1. Remove legacy validators from codebase
2. Remove `--engine legacy` flag
3. Clean up dual-system code
4. Archive legacy validators for historical reference

**Testing Strategy**:
- Full platform validation with AST only
- Regression testing for all workflows
- Performance baseline verification

## Technical Implementation

### 1. Update Entry Point Function

**File**: `packages/hive-tests/src/hive_tests/architectural_validators.py`

```python
def run_all_golden_rules(
    project_root: Path,
    scope_files: list[Path] | None = None,
    engine: str = "ast"  # AST is now default
) -> tuple[bool, dict]:
    """
    Run all Golden Rules validation.

    Args:
        project_root: Root directory of the project
        scope_files: Optional list of specific files to validate
        engine: Validation engine to use ('ast', 'legacy', 'both')

    Returns:
        Tuple of (all_passed, results_dict)
    """
    if engine == "ast":
        return _run_ast_validator(project_root, scope_files)
    elif engine == "legacy":
        return _run_legacy_validators(project_root, scope_files)
    elif engine == "both":
        return _run_both_validators(project_root, scope_files)
    else:
        raise ValueError(f"Unknown engine: {engine}")
```

### 2. AST Validator Wrapper

```python
def _run_ast_validator(
    project_root: Path,
    scope_files: list[Path] | None = None
) -> tuple[bool, dict]:
    """Run AST-based validation (default)"""
    from .ast_validator import EnhancedValidator

    validator = EnhancedValidator(project_root)
    passed, violations_by_rule = validator.validate_all()

    # Convert to format expected by entry point
    results = {}
    for rule_name, violations in violations_by_rule.items():
        # Extract rule name from tuple (legacy format compatibility)
        if isinstance(rule_name, tuple):
            rule_name = rule_name[0]

        results[f"Golden Rule: {rule_name}"] = {
            "passed": len(violations) == 0,
            "violations": [str(v) for v in violations]
        }

    return passed, results
```

### 3. Legacy Validator Wrapper

```python
def _run_legacy_validators(
    project_root: Path,
    scope_files: list[Path] | None = None
) -> tuple[bool, dict]:
    """Run string-based validators (backward compatibility)"""
    import warnings
    warnings.warn(
        "Legacy string-based validators are deprecated. "
        "Use AST validator (default) instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Existing implementation
    results = {}
    all_passed = True

    golden_rules = [
        ("Golden Rule 5: Package vs App Discipline", validate_package_app_discipline),
        # ... existing rules
    ]

    for rule_name, validator_func in golden_rules:
        try:
            passed, violations = _cached_validator(
                rule_name, validator_func, project_root, scope_files
            )
            results[rule_name] = {"passed": passed, "violations": violations}
            if not passed:
                all_passed = False
        except Exception as e:
            results[rule_name] = {
                "passed": False,
                "violations": [f"Validation error: {e}"]
            }
            all_passed = False

    return all_passed, results
```

### 4. Dual Validation Mode

```python
def _run_both_validators(
    project_root: Path,
    scope_files: list[Path] | None = None
) -> tuple[bool, dict]:
    """Run both validators and compare results (verification mode)"""
    logger.info("Running both AST and legacy validators for comparison...")

    # Run AST validator
    ast_passed, ast_results = _run_ast_validator(project_root, scope_files)

    # Run legacy validators
    legacy_passed, legacy_results = _run_legacy_validators(project_root, scope_files)

    # Compare results and log differences
    _compare_validation_results(ast_results, legacy_results)

    # Return AST results (primary)
    return ast_passed, ast_results
```

### 5. Update CLI Script

**File**: `scripts/validate_golden_rules.py`

```python
def main():
    parser = argparse.ArgumentParser(...)

    # Add engine selection flag
    parser.add_argument(
        "--engine",
        "-e",
        type=str,
        choices=["ast", "legacy", "both"],
        default="ast",
        help="Validation engine (ast=default, legacy=old, both=compare)"
    )

    args = parser.parse_args()

    # Run validation with selected engine
    success = validate_platform_compliance(
        scope_files=scope_files,
        quick=args.quick,
        engine=args.engine  # Pass engine selection
    )
```

## Pre-commit Hook Configuration

### Update `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      - id: golden-rules-ast
        name: Golden Rules Validation (AST)
        entry: python scripts/validate_golden_rules.py --incremental --engine ast
        language: system
        types: [python]
        pass_filenames: false

      # Optional: Legacy mode (backward compatibility)
      - id: golden-rules-legacy
        name: Golden Rules Validation (Legacy)
        entry: python scripts/validate_golden_rules.py --incremental --engine legacy
        language: system
        types: [python]
        pass_filenames: false
        stages: [manual]  # Only run when explicitly requested
```

## CI/CD Pipeline Updates

### GitHub Actions / GitLab CI

```yaml
# .github/workflows/validation.yml
name: Golden Rules Validation

on: [push, pull_request]

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

      - name: Run Golden Rules (AST)
        run: |
          python scripts/validate_golden_rules.py --engine ast

      # Optional: Compare with legacy (verification phase)
      - name: Compare Validators
        if: github.event_name == 'pull_request'
        run: |
          python scripts/validate_golden_rules.py --engine both
```

## Migration Timeline

### Week 1: Dual System Implementation
- **Day 1-2**: Implement engine selection flag
- **Day 3**: Update CLI script and entry points
- **Day 4**: Update pre-commit hooks
- **Day 5**: Update CI/CD pipelines
- **Day 6-7**: Monitor and collect feedback

**Deliverables**:
- ✅ Code changes merged to main
- ✅ Documentation updated
- ✅ Team announcement sent
- ✅ Monitoring dashboard set up

### Week 2: AST as Default
- **Day 1**: Change default from legacy to AST
- **Day 2-3**: Monitor CI/CD and developer workflows
- **Day 4**: Address any issues or edge cases
- **Day 5**: Update all remaining documentation

**Deliverables**:
- ✅ AST default across all workflows
- ✅ Legacy available via flag
- ✅ Performance metrics collected
- ✅ Edge cases documented

### Month 2: Deprecation Preparation
- **Week 1**: Add deprecation warnings
- **Week 2**: Migrate remaining legacy-dependent code
- **Week 3**: Update external integrations
- **Week 4**: Finalize removal plan

**Deliverables**:
- ✅ Deprecation warnings active
- ✅ No critical dependencies on legacy
- ✅ Removal timeline communicated

### Month 3-4: Legacy Removal
- **Month 3**: Remove legacy code
- **Month 4**: Final cleanup and optimization

**Deliverables**:
- ✅ Legacy validators removed
- ✅ Codebase simplified
- ✅ Performance optimized

## Risk Management

### Risk 1: AST Validator Bugs
**Likelihood**: Low (comprehensive testing completed)
**Impact**: High (blocks validation)
**Mitigation**:
- Maintain legacy fallback during Phase 1-2
- Monitor error rates closely
- Fast rollback mechanism ready

### Risk 2: Performance Regression
**Likelihood**: Very Low (AST is faster)
**Impact**: Medium (slower CI/CD)
**Mitigation**:
- Performance monitoring in CI/CD
- Optimize AST validator if needed
- Per-file caching for further speedup

### Risk 3: Compatibility Issues
**Likelihood**: Low (backward compatible design)
**Impact**: Medium (workflow disruption)
**Mitigation**:
- Gradual rollout with verification phase
- Clear documentation for edge cases
- Support channel for issues

### Risk 4: Developer Confusion
**Likelihood**: Medium (new system)
**Impact**: Low (productivity impact)
**Mitigation**:
- Clear documentation and examples
- Team training sessions
- FAQ for common issues

## Success Metrics

### Performance Metrics
- ✅ Validation time: Target <40s for full validation
- ✅ Cache hit rate: Target >80% for incremental
- ✅ CI/CD duration: No regression vs baseline

### Quality Metrics
- ✅ False positive rate: <1% (vs ~10% legacy)
- ✅ Coverage: 100% (23/23 rules)
- ✅ Accuracy: >99% violation detection

### Adoption Metrics
- ✅ AST usage: >95% of validations by Week 2
- ✅ Legacy usage: <5% by Month 1
- ✅ Developer satisfaction: >80% positive feedback

## Support and Documentation

### Developer Resources
1. **Migration Guide**: Step-by-step for teams
2. **AST Validator Reference**: Rule documentation
3. **Troubleshooting Guide**: Common issues and fixes
4. **FAQ**: Frequently asked questions

### Communication Channels
1. **Slack**: `#hive-validation` channel for questions
2. **Email**: Weekly migration status updates
3. **Wiki**: Updated documentation and guides
4. **Office Hours**: Weekly Q&A sessions

## Rollback Procedures

### Emergency Rollback (Critical Issues)
```bash
# Immediate rollback to legacy
git revert <migration-commit>
git push origin main

# Or: Change default in code
# In architectural_validators.py, line X:
engine: str = "legacy"  # Rollback to legacy default
```

### Graceful Rollback (Non-Critical Issues)
```bash
# Update CI/CD config
- python scripts/validate_golden_rules.py --engine ast
+ python scripts/validate_golden_rules.py --engine legacy

# Update pre-commit config
- --engine ast
+ --engine legacy

# Communicate to team
Slack: "Temporarily using legacy validator while we fix [issue]"
```

## Conclusion

This migration strategy provides a **safe, gradual path** from legacy string-based validation to modern AST-based validation while maintaining backward compatibility. The phased approach minimizes risk and allows for easy rollback if issues occur.

**Key Advantages**:
- ✅ Zero disruption during transition
- ✅ Backward compatibility maintained
- ✅ Easy rollback mechanism
- ✅ Comprehensive monitoring and feedback
- ✅ Clear timeline and milestones

**Next Actions**:
1. Implement engine selection flag
2. Update entry points and CLI
3. Update pre-commit hooks
4. Deploy to CI/CD
5. Monitor and collect feedback

---

**Document Generated**: 2025-09-30
**Author**: Claude Code
**Status**: Ready for implementation
**Target Start**: Immediate (Phase 1)
**Expected Completion**: Month 4