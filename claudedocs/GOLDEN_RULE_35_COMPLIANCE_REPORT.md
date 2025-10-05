# Golden Rule 35: Observability Standards - Compliance Report

**Date**: 2025-10-05
**Rule**: Golden Rule 35 - Observability Standards
**Severity**: WARNING (6-month grace period)
**Status**: ✅ PASSING (but 120 violations detected)

---

## Executive Summary

Golden Rule 35 is **PASSING** the build (grace period active), but **120 violations** exist that should be addressed:

- **78 WARNING-level** violations (manual timing code)
- **42 INFO-level** violations (function-level timing suggestions)

**Target**: Reduce to <60 violations (50% reduction)

---

## Violation Breakdown

### By Severity
| Severity | Count | Description |
|----------|-------|-------------|
| WARNING  | 78    | Manual `time.time()` pairs - should use `@timed()` |
| INFO     | 42    | Functions with timing - consider decorators |
| **Total** | **120** | **All observability anti-patterns** |

### Top 10 Files with Most Violations
| Count | File |
|-------|------|
| 6 | `apps/ecosystemiser/src/ecosystemiser/discovery/algorithms/base.py` |
| 6 | `packages/hive-ai/src/hive_ai/observability/health.py` |
| 5 | `apps/ecosystemiser/scripts/foundation_benchmark.py` |
| 5 | `packages/hive-app-toolkit/src/hive_app_toolkit/cost/rate_limiter.py` |
| 4 | `apps/ecosystemiser/scripts/run_cli_suite.py` |
| 4 | `apps/ecosystemiser/scripts/archive/run_benchmarks_broken.py` |
| 4 | `apps/ecosystemiser/solver/hybrid_solver.py` |
| 4 | `apps/ecosystemiser/tests/performance/test_hybrid_solver_8760h.py` |
| 4 | `apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service.py` |
| 4 | `packages/hive-ai/src/hive_ai/models/client.py` |

---

## Compliance Strategy

### Phase 1: Low-Hanging Fruit (Target: 30 violations fixed)

**Scripts and Test Files** (easiest to fix):
- `apps/ecosystemiser/scripts/` - 15+ violations in demo/benchmark scripts
- `apps/ecosystemiser/tests/performance/` - 4 violations in test files
- `apps/chimera-daemon/scripts/` - 2 violations in validation scripts

**Approach**: Add `@timed()` decorators or remove timing code entirely (scripts often don't need metrics)

**Effort**: 30 minutes (simple find-replace patterns)

### Phase 2: Package Utilities (Target: 20 violations fixed)

**Utility Packages**:
- `packages/hive-ai/src/hive_ai/observability/health.py` - 6 violations
- `packages/hive-ai/src/hive_ai/models/client.py` - 4 violations
- `packages/hive-app-toolkit/src/hive_app_toolkit/cost/rate_limiter.py` - 5 violations

**Approach**: Replace manual timing with `@timed()` decorators (production code)

**Effort**: 45 minutes (requires code understanding)

### Phase 3: Core Application Code (Target: 10 violations fixed)

**AI Apps**:
- `apps/ai-planner/src/ai_planner/agent.py` - 1 violation
- `apps/ai-planner/src/ai_planner/async_agent.py` - 1 violation
- `apps/ai-reviewer/src/ai_reviewer/async_agent.py` - 1 violation

**Orchestrator**:
- `apps/hive-orchestrator/src/hive_orchestrator/core/claude/claude_service.py` - 4 violations

**Approach**: Carefully replace timing with decorators (critical production code)

**Effort**: 60 minutes (requires testing validation)

---

## Auto-Fix Candidates

### Simple Replacements (Pattern-Based)

**Pattern 1: Standalone timing blocks**
```python
# BEFORE
start_time = time.time()
result = do_work()
duration = time.time() - start_time
logger.info(f"Took {duration:.2f}s")
return result

# AFTER
@timed(metric_name="do_work.duration")
def do_work():
    result = do_work()
    return result
```

**Auto-Fix**: Scripts can use morphllm/Ruff to detect and replace

### Manual Review Required

**Pattern 2: Timing with metadata**
```python
# Needs manual review - timing includes context
start = time.time()
result = complex_operation(context)
metrics = {
    "duration": time.time() - start,
    "items_processed": len(result),
    "context_id": context.id
}
```

**Manual Fix**: Extract to function, add decorator with labels

---

## Implementation Plan

### Step 1: Scripts Cleanup (30 min)

```bash
# Remove timing from demo/benchmark scripts
# OR add @timed() decorators if metrics are needed
ruff check --select E,F,W apps/ecosystemiser/scripts/
```

**Target**: 30 violations → 0 violations in scripts

### Step 2: Package Utilities (45 min)

```bash
# Replace manual timing in hive-ai and hive-app-toolkit
# Use @timed() decorator with appropriate metric names
```

**Target**: 15 violations → 0 violations in utility packages

### Step 3: Core Apps (60 min)

```bash
# Carefully replace timing in AI apps and orchestrator
# Validate with existing tests
pytest apps/ai-planner/tests
pytest apps/ai-reviewer/tests
pytest apps/hive-orchestrator/tests
```

**Target**: 5 violations → 0 violations in core apps

### Step 4: Validation

```bash
# Re-run validator
python -c "
from pathlib import Path
from hive_tests.observability_validator import validate_observability_standards

project_root = Path.cwd()
passed, violations = validate_observability_standards(project_root)
print(f'Total violations: {len(violations)}')
print(f'Target (<60): {\"PASS\" if len(violations) < 60 else \"FAIL\"}')
"
```

**Expected**: 120 → <60 violations (50% reduction achieved)

---

## Success Criteria

- [x] **Baseline Established**: 120 violations documented
- [ ] **Scripts Cleaned**: 0 violations in `*/scripts/` directories
- [ ] **Packages Fixed**: 0 violations in utility packages
- [ ] **Core Apps Improved**: <5 violations in production code
- [ ] **50% Reduction**: <60 total violations
- [ ] **Tests Passing**: All existing tests still pass
- [ ] **Commit Created**: Golden Rule 35 compliance commit

---

## Risk Assessment

### Low Risk (Scripts)
- **Impact**: Minimal - scripts are for demos/benchmarks
- **Approach**: Remove timing code or add decorators
- **Rollback**: Simple revert if issues occur

### Medium Risk (Utilities)
- **Impact**: Moderate - used by multiple apps
- **Approach**: Replace with decorators, validate imports
- **Rollback**: Revert individual files if needed

### High Risk (Core Apps)
- **Impact**: High - production code paths
- **Approach**: Careful replacement with test validation
- **Rollback**: Full validation before commit

---

## Timeline

**Total Effort**: ~2.5 hours
- Step 1 (Scripts): 30 minutes
- Step 2 (Utilities): 45 minutes
- Step 3 (Core Apps): 60 minutes
- Validation & Commit: 15 minutes

**Expected Completion**: Same day (2025-10-05)

---

## Next Steps

1. **Start with Scripts** (lowest risk, highest impact)
2. **Validate each step** (run tests, check violations)
3. **Progressive commits** (commit after each phase)
4. **Final validation** (ensure 50% reduction achieved)

---

**Status**: Ready to begin compliance sprint
**Files Created**: This report
**Next Action**: Start Step 1 (Scripts cleanup)
