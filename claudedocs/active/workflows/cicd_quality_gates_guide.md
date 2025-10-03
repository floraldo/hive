# CI/CD Quality Gates Integration Guide

**Status**: Complete
**Created**: 2025-09-30
**Part of**: Project Aegis Stage 7

---

## Overview

This guide documents the automated quality gate system integrated into the Hive platform CI/CD pipeline.

---

## Quality Gate Architecture

### Gate 1: Code Quality & Formatting
**Tools**: Black, isort, Ruff
**Purpose**: Enforce consistent code style and catch basic linting issues
**Blocking**: Yes
**Runtime**: ~2-3 minutes

### Gate 1.5: Smoke Tests & Autofix Validation (NEW)
**Tools**: pytest (smoke tests), AutoFix (async naming)
**Purpose**: Validate all modules can be imported, check code quality patterns
**Blocking**: Warning only (smoke tests may fail)
**Runtime**: ~3-5 minutes

**What it checks**:
- All Python modules can be imported without errors
- Async function naming conventions (warning only)
- Basic code quality patterns

### Gate 2: Architectural Validation
**Tools**: Golden Rules Framework
**Purpose**: Enforce architectural compliance (15 rules)
**Blocking**: Yes
**Runtime**: ~1-2 minutes

### Gate 3: Functional Tests
**Tools**: pytest (unit tests), coverage
**Purpose**: Validate business logic correctness
**Blocking**: Yes
**Runtime**: ~5-10 minutes

### Gate 4: Performance Regression
**Tools**: Custom benchmarks
**Purpose**: Prevent performance degradation
**Blocking**: Yes (>5% regression)
**Runtime**: ~3-5 minutes

### Gate 5: Integration Tests
**Tools**: pytest (integration tests)
**Purpose**: Validate cross-component interactions
**Blocking**: Warning only (optional)
**Runtime**: ~5-10 minutes

---

## Pre-Commit Hooks

### Enabled Hooks

1. **Ruff** (linting + auto-fix)
   - Runs on every commit
   - Fixes common issues automatically
   - Blocks commit if errors remain

2. **Ruff Format** (code formatting)
   - Formats code automatically
   - Ensures consistent style

3. **Black** (backup formatter)
   - Additional formatting pass
   - Handles edge cases Ruff misses

4. **Python Syntax Check**
   - Validates all Python files compile
   - Catches syntax errors early
   - Blocks commit on syntax errors

5. **Golden Rules Check** (NEW - ENABLED)
   - Validates architectural compliance
   - Runs incrementally for performance
   - Blocks commit on violations
   - **Bypass**: `SKIP=golden-rules-check git commit`

6. **Autofix Validation** (NEW)
   - Checks async naming conventions
   - Validates code quality patterns
   - Warning only (doesn't block)
   - Will be enforced in future

---

## Installation

### Initial Setup

```bash
# Install pre-commit hooks
pip install pre-commit
cd /path/to/hive
pre-commit install

# Test hooks
pre-commit run --all-files
```

### Update Hooks

```bash
# Update to latest versions
pre-commit autoupdate

# Re-run after updates
pre-commit run --all-files
```

---

## Usage Workflows

### Normal Development Flow

```bash
# 1. Make changes
vim apps/ecosystemiser/src/some_file.py

# 2. Stage changes
git add apps/ecosystemiser/src/some_file.py

# 3. Commit (hooks run automatically)
git commit -m "feat: add new feature"

# Hooks will:
# - Auto-format code (ruff, black)
# - Check syntax (py_compile)
# - Validate architecture (golden rules)
# - Warn about quality issues (autofix)

# 4. Push to trigger CI
git push origin feature/my-branch
```

### Bypass Pre-Commit (Use Sparingly)

```bash
# Skip all hooks (emergency only)
git commit --no-verify -m "emergency fix"

# Skip specific hook
SKIP=golden-rules-check git commit -m "architectural change in progress"
```

### Manual Hook Execution

```bash
# Run all hooks on staged files
pre-commit run

# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run golden-rules-check
pre-commit run autofix-validation

# Run hooks on specific files
pre-commit run --files apps/ecosystemiser/src/file.py
```

---

## CI/CD Integration Details

### GitHub Actions Workflow

**File**: `.github/workflows/ci.yml`

**Trigger Events**:
- Pull requests to `main`
- Pushes to `main`

**Quality Gate Sequence**:
```
code-quality (Gate 1)
    ↓
smoke-tests-autofix (Gate 1.5) [NEW]
    ↓
golden-tests (Gate 2)
    ↓
ecosystemiser-tests (Gate 3)
    ↓
performance-regression (Gate 4)
    ↓
integration-tests (Gate 5)
    ↓
all-quality-gates-passed (Summary)
```

### Parallel Execution

Quality gates run sequentially with dependencies to ensure:
- Fast feedback (fail fast on style issues)
- Resource efficiency (expensive tests only after cheap checks pass)
- Clear failure attribution (know which gate failed)

---

## Smoke Tests

### Purpose

Validate all Python modules can be imported without:
- Syntax errors
- Missing dependencies
- Circular import issues
- Module initialization errors

### Location

All smoke tests are in `packages/*/tests/smoke/` directories:
- `packages/hive-ai/tests/smoke/test_smoke_hive_ai.py`
- `packages/hive-async/tests/smoke/test_smoke_hive_async.py`
- etc. (17 packages total)

### Auto-Generation

Smoke tests are generated automatically:

```bash
# Generate for all packages
python scripts/generate_smoke_tests.py

# Generate for specific package
python scripts/generate_smoke_tests.py --package hive-async

# Dry run (preview only)
python scripts/generate_smoke_tests.py --dry-run
```

### Running Smoke Tests

```bash
# Run all smoke tests
pytest packages/*/tests/smoke/ -v

# Run for specific package
pytest packages/hive-async/tests/smoke/ -v

# Quick smoke test (fail fast)
pytest packages/*/tests/smoke/ -x
```

---

## Autofix Integration

### Purpose

Autofix validates code quality patterns beyond basic linting:
- Async function naming (`_async` suffix)
- Code organization patterns
- Best practice adherence

### Pre-Commit Integration

**Hook**: `autofix-validation`
**Mode**: Warning only (doesn't block commits)
**Future**: Will be enforced when codebase is fully compliant

### CI Integration

**Job**: `smoke-tests-autofix`
**Step**: "Run Autofix Dry-Run Validation"
**Mode**: Warning only (doesn't fail builds)

### Manual Autofix

```bash
# Check for violations
python -c "from hive_tests.autofix import AutoFix; AutoFix().analyze('apps/')"

# Fix violations automatically
python -c "from hive_tests.autofix import AutoFix; AutoFix().fix_all('apps/')"

# Dry run (preview changes)
python -c "from hive_tests.autofix import AutoFix; AutoFix().analyze('apps/', dry_run=True)"
```

---

## Golden Rules Integration

### Pre-Commit

**Status**: ENABLED (as of Project Aegis Stage 7)
**Mode**: Blocking (fails commit on violations)
**Performance**: Incremental validation (~0.6s cached, 5-10s cold)

### CI

**Job**: `golden-tests`
**Mode**: Blocking (fails build on violations)
**Coverage**: Full repository validation

### Suppression Mechanism

```python
# Suppress specific rule with justification
# golden-rule-ignore: no-print-statements - Debug output for CLI tool
print("Debug information")

# Suppress multiple rules
# golden-rule-ignore: no-print-statements,no-hardcoded-paths - Intentional for script
```

---

## Gradual Rollout Strategy

### Phase 1: Warning Mode (CURRENT)
- Smoke tests: Continue on error
- Autofix: Warning only, exit 0
- Pre-commit autofix: Warning only
- **Duration**: 2-4 weeks

### Phase 2: Soft Enforcement (FUTURE)
- Smoke tests: Fail build on critical errors
- Autofix: Block new violations (existing allowed)
- Pre-commit autofix: Warning with guidance
- **Duration**: 4-6 weeks

### Phase 3: Full Enforcement (TARGET)
- Smoke tests: All pass required
- Autofix: All violations block commits
- Pre-commit autofix: Blocking (exit 1)
- **Timeline**: After codebase is compliant

---

## Troubleshooting

### Pre-Commit Hook Failures

**Problem**: Golden rules check fails
```bash
# View detailed errors
python scripts/validate_golden_rules.py --incremental

# Bypass for architectural work
SKIP=golden-rules-check git commit -m "architectural change"
```

**Problem**: Autofix warnings
```bash
# Preview autofix changes
python -m hive_tests.autofix analyze apps/

# Apply fixes
python -m hive_tests.autofix fix apps/
```

**Problem**: Syntax check fails
```bash
# Find syntax errors
python -m py_compile path/to/file.py

# Check all Python files
find . -name "*.py" -exec python -m py_compile {} \;
```

### CI Failures

**Problem**: Smoke tests fail
```bash
# Run locally
pytest packages/*/tests/smoke/ -v

# Regenerate if needed
python scripts/generate_smoke_tests.py
```

**Problem**: Golden tests fail
```bash
# Run locally
cd packages/hive-tests
pytest tests/test_architecture.py -v
```

**Problem**: Performance regression
```bash
# Run benchmarks locally
cd apps/ecosystemiser
poetry run python scripts/run_benchmarks.py
```

---

## Metrics & Monitoring

### Quality Gate Success Rates

Track in GitHub Actions insights:
- Gate 1: Code Quality (target: >95%)
- Gate 1.5: Smoke Tests (target: >90% initially, >99% future)
- Gate 2: Golden Rules (target: >95%)
- Gate 3: Functional Tests (target: >90%)
- Gate 4: Performance (target: >95%)
- Gate 5: Integration (target: >80%)

### Pre-Commit Hook Metrics

Monitor locally:
- Hook execution time (target: <30s total)
- Bypass frequency (target: <5%)
- Auto-fix success rate (target: >90%)

---

## Best Practices

### For Developers

1. **Run pre-commit before pushing**
   ```bash
   pre-commit run --all-files
   ```

2. **Test locally before PR**
   ```bash
   # Quick validation
   pytest packages/*/tests/smoke/ -x
   python scripts/validate_golden_rules.py --incremental
   ```

3. **Use bypass sparingly**
   - Only for genuine emergencies or work-in-progress
   - Add explanation in commit message
   - Fix violations in follow-up commit

4. **Keep hooks updated**
   ```bash
   pre-commit autoupdate
   ```

### For AI Agents

1. **Always validate syntax after edits**
   ```bash
   python -m py_compile modified_file.py
   ```

2. **Run incremental validation**
   ```bash
   python scripts/validate_golden_rules.py --incremental
   ```

3. **Check for autofix violations**
   ```bash
   python -m hive_tests.autofix analyze modified_file.py
   ```

4. **Test smoke tests after changes**
   ```bash
   pytest packages/changed-package/tests/smoke/ -v
   ```

---

## Migration Checklist

### Completed ✅
- [x] Added smoke test generation script
- [x] Generated smoke tests for all 17 packages
- [x] Created autofix validation in CI
- [x] Enabled golden rules in pre-commit
- [x] Added autofix hook to pre-commit
- [x] Integrated smoke tests into CI pipeline
- [x] Created comprehensive documentation

### In Progress 🔄
- [ ] Monitor smoke test success rates
- [ ] Gather autofix violation metrics
- [ ] Gradual enforcement rollout

### Future 📋
- [ ] Fix remaining 18 files with syntax errors
- [ ] Achieve 100% smoke test pass rate
- [ ] Enforce autofix violations (change to blocking)
- [ ] Add performance budgets to CI
- [ ] Expand smoke tests to apps/

---

## Summary

**Quality Gates Added**: 1 new gate (smoke tests + autofix)
**Pre-Commit Hooks Added**: 2 new hooks (golden rules enabled + autofix)
**Enforcement Strategy**: Gradual (warning → soft → full)
**Risk Level**: LOW (warnings don't block, gradual rollout)
**Impact**: Early detection of quality issues, reduced technical debt

**Key Principle**: Fail fast, fix early, maintain quality.