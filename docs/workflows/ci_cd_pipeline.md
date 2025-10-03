# Hive Platform CI/CD Pipeline - Golden Gates

**Philosophy**: Fast feedback, mandatory quality standards, zero regressions

## Overview

The Hive platform uses a multi-layered CI/CD approach with **4 mandatory quality gates** that protect the codebase from common failure modes. Every pull request must pass all gates before merging.

## The Golden Gates Workflow

**File**: `.github/workflows/golden-gates.yml`
**Triggers**: Pull requests to main/develop, pushes to main
**Strategy**: Sequential gates with fail-fast validation

### Gate 1: Syntax Integrity ⚡

**Purpose**: Zero tolerance for Python syntax errors

**Validation**:
```bash
python -m compileall -q .
```

**Success Criteria**: 0 syntax errors platform-wide

**Why It Matters**:
- Syntax errors break pytest collection
- Prevents "broken main" scenarios
- Fast feedback (<5 min)
- Layer 1 baseline achieved: 78 → 0 syntax errors

**When It Fails**:
- Run locally: `python -m compileall -q . 2>&1 | grep 'Error compiling'`
- Fix syntax errors before committing
- Common causes: Missing commas, malformed ternary operators, indentation issues

---

### Gate 2: Test Collection 📋

**Purpose**: All tests must be importable (no ModuleNotFoundError)

**Validation**:
```bash
pytest --collect-only
```

**Success Criteria**:
- All tests collected successfully
- Zero import errors
- Zero collection errors

**Why It Matters**:
- Import errors prevent test execution
- Early detection of missing dependencies
- Validates package installation correctness
- Prevents "tests pass locally but fail in CI" scenarios

**When It Fails**:
- Run locally: `pytest --collect-only`
- Check error messages for ModuleNotFoundError
- Install missing packages: `pip install -e packages/missing-package/`
- Fix absolute imports: `from tests.xxx` → relative imports

**Current Status**: 149 collection errors being addressed by parallel agents

---

### Gate 3: Boy Scout Rule 🧹

**Purpose**: Linting violations CANNOT increase (our innovation!)

**Validation**:
```bash
pytest packages/hive-tests/tests/unit/test_boy_scout_rule.py::TestBoyScoutRule::test_linting_violations_do_not_increase -v
```

**Success Criteria**:
- Current violations ≤ baseline (1599 as of 2025-10-04)
- No new violations introduced
- Technical debt stable or decreasing

**Why It Matters**:
- **Incremental quality improvement** - no "big bang" cleanup sprints needed
- **Prevents regressions** - quality never degrades
- **Natural debt reduction** - violations decrease through normal development
- **Developer-friendly** - format-on-save prevents violations automatically

**Philosophy**: "Always leave code cleaner than you found it"

**When It Fails**:
```
❌ BOY SCOUT RULE VIOLATION

Linting violations INCREASED:
  Baseline: 1599 violations
  Current:  1650 violations
  Increase: +51

ACTION REQUIRED:
1. Run: ruff check . --fix
2. Fix remaining violations in files you touched
3. Never use --no-verify to bypass this check

Remember: Always leave code cleaner than you found it!
```

**How to Fix**:
- Auto-fix most violations: `ruff check . --fix`
- Fix remaining violations manually in files you edited
- Commit with clean violations count
- **Never** use `--no-verify` to bypass (except infrastructure commits)

**IDE Integration**: `.vscode/settings.json` enables format-on-save, preventing violations before commit

**Progress Tracking**: Update `BASELINE_VIOLATIONS` in test file when violations decrease

---

### Gate 4: Golden Rules 🏆

**Purpose**: Architectural integrity at ERROR severity level

**Validation**:
```bash
python scripts/validation/validate_golden_rules.py --level ERROR
```

**Success Criteria**: Zero ERROR-level violations (33 architectural rules)

**Why It Matters**:
- **Architecture enforcement** - prevents layer violations
- **Pattern compliance** - ensures consistent platform patterns
- **Quality standards** - type hints, docstrings, error handling
- **Configuration consistency** - all packages follow same standards

**Key Rules Enforced** (ERROR level):
- No sys.path manipulation
- No print() statements (use hive_logging)
- Hive packages required for logging/config/db
- No hardcoded paths
- Type hints enforced
- Layer separation (packages/ vs apps/)
- No deprecated configuration patterns
- Environment isolation (no conda/absolute paths)
- Configuration consistency (pyproject.toml standards)

**When It Fails**:
- Review error output for specific rule violations
- Fix violations following architectural patterns
- Common fixes:
  - Replace `print()` with `from hive_logging import get_logger`
  - Use `create_config_from_sources()` instead of `get_config()`
  - Remove hardcoded paths, use environment variables
  - Add type hints to function signatures

**Tiered Compliance**: Development uses CRITICAL level (fast), PRs use ERROR level (comprehensive)

---

## Additional Validation

### Syntax Error Regression Check

**Part of Gate 3**, runs as additional verification:
```bash
pytest packages/hive-tests/tests/unit/test_boy_scout_rule.py::TestBoyScoutRule::test_syntax_errors_remain_zero -v
```

Ensures Layer 1 achievement (0 syntax errors) is maintained forever.

---

## Gates Summary Job

**Purpose**: Aggregate status report across all gates

**Output**:
```
======================================
🚪 GOLDEN GATES - QUALITY ENFORCEMENT
======================================

All 4 mandatory gates have been evaluated:

⚡ Gate 1 - Syntax Integrity:      success
📋 Gate 2 - Test Collection:      success
🧹 Gate 3 - Boy Scout Rule:       success
🏆 Gate 4 - Golden Rules:         success

✅ ALL GATES PASSED!

This PR maintains all quality standards:
  • Zero syntax errors (Layer 1)
  • All tests importable (Layer 2)
  • No new linting violations (Boy Scout Rule)
  • Architectural integrity (Golden Rules)

🎉 Excellent work! The foundation remains strong.
```

**If Gates Fail**:
```
❌ ONE OR MORE GATES FAILED!

This PR cannot be merged until all gates pass.
Review the failed gates above and fix the issues.

🏰 The Golden Gates protect the platform's quality foundation.
```

---

## Optional: Full Test Suite

**Job**: `full-test-suite`
**Status**: Non-blocking (`continue-on-error: true`)
**When**: Only on non-draft PRs

**Purpose**: Deeper validation beyond gates, provides warning signals but doesn't block merge

**Why Non-Blocking**:
- Layer 2 (test collection) still in progress
- Some tests may fail during active development
- Provides feedback without blocking progress
- Becomes mandatory once Layer 2 complete

---

## Integration with Existing Workflows

### Citadel Guardian (`.github/workflows/citadel-guardian.yml`)
- **Purpose**: AI-powered architectural compliance analysis
- **Relationship**: Complements Golden Gates with intelligent insights
- **Status**: Independent workflow

### Golden Rules Enhanced (`.github/workflows/golden-rules.yml`)
- **Purpose**: AST-based architectural validation
- **Relationship**: Superseded by Gate 4 in Golden Gates workflow
- **Status**: Can be deprecated once Golden Gates proven

### Code Quality (`.github/workflows/ci.yml`)
- **Purpose**: Black, isort, Ruff linting
- **Relationship**: Gate 3 (Boy Scout Rule) provides stronger enforcement
- **Status**: Can be consolidated into Golden Gates

---

## Local Development Workflow

### Pre-Commit Validation (Recommended)

```bash
# Install pre-commit hooks (one-time setup)
pre-commit install

# Hooks run automatically on git commit:
# 1. Syntax check (python -m py_compile)
# 2. Ruff auto-fix (safe violations)
# 3. Golden Rules validation (ERROR level)
```

### Manual Gate Validation (Before PR)

```bash
# Gate 1: Syntax Integrity
python -m compileall -q . 2>&1 | grep 'Error compiling'

# Gate 2: Test Collection
pytest --collect-only

# Gate 3: Boy Scout Rule
pytest packages/hive-tests/tests/unit/test_boy_scout_rule.py::TestBoyScoutRule::test_linting_violations_do_not_increase -v

# Gate 4: Golden Rules
python scripts/validation/validate_golden_rules.py --level ERROR
```

### IDE Integration (VSCode)

**File**: `.vscode/settings.json`

**Key Settings**:
- Format on save (Ruff)
- Auto-fix violations on save
- Organize imports automatically
- Trim trailing whitespace
- Insert final newline

**Result**: Boy Scout Rule violations prevented before commit

---

## Performance Characteristics

| Gate | Typical Duration | Fail-Fast |
|------|------------------|-----------|
| Gate 1 | ~30 seconds | ✅ Yes |
| Gate 2 | ~1-2 minutes | ✅ Yes |
| Gate 3 | ~1 minute | ✅ Yes |
| Gate 4 | ~30 seconds | ✅ Yes |
| **Total** | **~3-4 minutes** | **Sequential** |

**Strategy**: Sequential gates with `needs:` dependencies for logical progression

---

## Quality Metrics & Progress

### Layer 1: Syntax Errors
- **Start**: 78 syntax errors
- **Current**: 0 syntax errors ✅
- **Status**: COMPLETE (Gate 1 enforcement)

### Layer 2: Test Collection
- **Start**: 149 collection errors
- **Current**: In progress (parallel agents)
- **Status**: ACTIVE (Gate 2 validation ready)

### Layer 3: Linting Violations (Boy Scout Rule)
- **Start**: 1733 violations
- **Current**: 1599 violations (-134, -7.7%)
- **Progress**: 1733 → 1599 → trending to 0
- **Status**: ACTIVE (Gate 3 enforcement)

### Layer 4: Golden Rules
- **Total Rules**: 33 architectural validators
- **ERROR Level**: 13 rules (mandatory for PRs)
- **Status**: ENFORCED (Gate 4)

---

## Emergency Bypass

**When to Use `--no-verify`**: ONLY for infrastructure commits that touch:
- Pre-commit hooks themselves
- Testing infrastructure (test files validating tests)
- CI/CD workflows
- Quality gate implementations

**Never Use `--no-verify`**: For regular development work

**Master Agent Privilege**: Can use `--no-verify` for coordinated multi-file quality improvements

---

## Future Enhancements

### When Layer 2 Complete
- Enable `full-test-suite` as mandatory gate
- Add test coverage reporting
- Enforce minimum coverage thresholds

### When Layer 3 Complete (0 violations)
- Enable `test_zero_violations_achieved()` in Boy Scout Rule test
- Tighten enforcement (WARNING → ERROR for additional rules)
- Add complexity metrics

### Long-term
- Performance regression testing
- Security scanning (dependency vulnerabilities)
- Documentation coverage
- API compatibility validation

---

## Philosophy

**The Golden Gates embody the Hive platform's quality philosophy**:

1. **Fast Feedback** - Fail fast on fundamental issues (syntax, imports)
2. **Zero Regressions** - Quality never degrades (Boy Scout Rule)
3. **Incremental Improvement** - Technical debt decreases naturally through development
4. **Developer-Friendly** - Automation prevents violations, not punishment after the fact
5. **Evidence-Based** - Programmatic enforcement, not documentation/trust

**Result**: A platform that gets cleaner, stronger, and more reliable with every PR.

---

## Resources

- **Golden Gates Workflow**: `.github/workflows/golden-gates.yml`
- **Boy Scout Rule Test**: `packages/hive-tests/tests/unit/test_boy_scout_rule.py`
- **Golden Rules Validator**: `scripts/validation/validate_golden_rules.py`
- **IDE Config**: `.vscode/settings.json`
- **Platform Guide**: `.claude/CLAUDE.md`
