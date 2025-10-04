# Project Genesis - Phase 2 Execution Plan

**Status**: Subtasks 001-003 ✅ COMPLETED | Subtasks 004-006 📋 PLANNED

## Completed Work (Coder Agent)

### ✅ Subtask 001: Time Parsing Utility (30 min estimated)
- **Actual Duration**: ~25 minutes
- **Deliverables**:
  - `parse_relative_time()` function with regex validation
  - Support for 2d, 1h, 30m, 1w formats
  - Comprehensive error handling
- **Status**: COMPLETE - Quality gates passed

### ✅ Subtask 002: CLI Option Integration (15 min estimated)
- **Actual Duration**: ~10 minutes
- **Deliverables**:
  - `--since` click.option added
  - Function signature updated
  - Docstring examples added
- **Status**: COMPLETE - Quality gates passed

### ✅ Subtask 003: Database Filtering Logic (20 min estimated)
- **Actual Duration**: ~15 minutes
- **Deliverables**:
  - Timestamp comparison logic
  - ISO date parsing with timezone handling
  - Filter compatibility maintained
- **Status**: COMPLETE - Quality gates passed

**Total Phase 1**: 65 min estimated → ~50 min actual (23% faster than planned)

---

## Remaining Work (Phase 2)

### 📋 Subtask 004: Comprehensive Unit Tests (40 min estimated)
**Assignee**: Test Agent (manual execution by Claude)
**Dependencies**: Subtask 003 ✅
**File**: `packages/hive-cli/tests/test_tasks_command.py` (NEW FILE)

**Test Coverage Required**:

#### 1. Time Parser Tests
```python
class TestParseRelativeTime:
    def test_valid_formats_days(self):
        # Test: 2d, 3days, 1day

    def test_valid_formats_hours(self):
        # Test: 1h, 2hours, 24hour

    def test_valid_formats_minutes(self):
        # Test: 30m, 45min, 1minute

    def test_valid_formats_weeks(self):
        # Test: 1w, 2weeks

    def test_invalid_formats(self):
        # Test: "invalid", "2x", "abc", "", "2.5d"
        # Expect: ValueError with clear message

    def test_case_insensitive(self):
        # Test: "2D", "1H", "30M" all work

    def test_edge_cases(self):
        # Test: "0d" (zero time)
        # Test: Large values (999d)
```

#### 2. CLI Integration Tests
```python
class TestListTasksSinceFilter:
    @pytest.fixture
    def mock_tasks(self):
        # Mock tasks with various created_at timestamps

    def test_since_filter_excludes_old_tasks(self, mock_tasks):
        # Tasks older than --since are filtered out

    def test_since_filter_includes_recent_tasks(self, mock_tasks):
        # Tasks within --since timeframe are included

    def test_since_with_status_filter(self, mock_tasks):
        # Combined filters work correctly

    def test_since_with_worker_filter(self, mock_tasks):
        # Combined filters work correctly

    def test_invalid_since_format_error(self):
        # Invalid format shows clear error message

    def test_since_filter_empty_result(self, mock_tasks):
        # No tasks match -> empty list (not error)
```

#### 3. Edge Case Tests
```python
class TestEdgeCases:
    def test_missing_created_at_field(self):
        # Tasks without created_at are skipped (not crash)

    def test_malformed_timestamp(self):
        # Malformed timestamps handled gracefully

    def test_timezone_handling(self):
        # UTC timestamps converted correctly

    def test_very_recent_tasks(self):
        # Tasks created seconds ago (--since 1m)
```

**Estimation**: 40 minutes (Planner's estimate accurate)

---

### 📋 Subtask 005: Documentation Update (10 min estimated)
**Assignee**: Doc Agent (manual execution by Claude)
**Dependencies**: Subtask 003 ✅
**File**: `packages/hive-cli/src/hive_cli/commands/tasks.py` (UPDATE)

**Already Completed** ✅:
- Docstring examples added during Coder Agent phase
- Examples include: `--since 2d`, `--since 1h --pretty`, `--since 30m --status completed`

**Additional Documentation Needed**:
1. **README.md Update** (if exists):
   - Add `--since` to feature list
   - Add usage examples section

2. **CHANGELOG.md Entry** (if exists):
   ```markdown
   ## [Unreleased]
   ### Added
   - `--since` filter for `hive tasks list` command
   - Support for relative time formats (2d, 1h, 30m, 1w)
   ```

**Estimation**: 5-10 minutes (mostly already done)

---

### 📋 Subtask 006: Quality Gates Validation (15 min estimated)
**Assignee**: Guardian Agent (manual execution by Claude)
**Dependencies**: Subtasks 004 ✅, 005 ✅

**Validation Commands**:

#### 1. Syntax Validation ✅ (Already Passing)
```bash
python -m py_compile packages/hive-cli/src/hive_cli/commands/tasks.py
# Status: PASSING
```

#### 2. Linting Validation ✅ (Already Passing)
```bash
ruff check packages/hive-cli/src/hive_cli/commands/tasks.py
# Status: PASSING (all checks passed)
```

#### 3. Unit Tests 🔄 (Pending Subtask 004)
```bash
pytest packages/hive-cli/tests/test_tasks_command.py -v
# Expected: All tests passing
```

#### 4. Golden Rules Validation 🔄 (Final Check)
```bash
python scripts/validation/validate_golden_rules.py --level ERROR
# Expected: All 24 rules passing
```

#### 5. Integration Test 🔄 (Manual Verification)
```bash
# Test with actual database
hive tasks list --since 3h --pretty
# Expected: Genesis task appears (created 2.4h ago)
```

**Estimation**: 15 minutes

---

## Execution Strategy

### Parallel Opportunities (from Planner)
The Planner identified that **Subtasks 004 and 005 can run in parallel** since they have the same dependency (Subtask 003) but no interdependency.

**Strategy**:
1. ✅ **Sequential Phase 1**: Subtasks 001 → 002 → 003 (COMPLETED)
2. 🔄 **Parallel Phase 2**: Subtasks 004 || 005 (NEXT)
3. 🔄 **Sequential Phase 3**: Subtask 006 (FINAL)

### Optimal Execution Order

**Option A: Sequential (Traditional)**
```
004 (tests) → 005 (docs) → 006 (validation)
Estimated: 40 + 10 + 15 = 65 minutes
```

**Option B: Parallel (Optimized)** ⭐
```
[004 (tests) || 005 (docs)] → 006 (validation)
Estimated: max(40, 10) + 15 = 55 minutes
Savings: 10 minutes (15% faster)
```

**Recommended**: Option B (Parallel Execution)

### Implementation Approach

Since we're in Path A+ (manual agent triggering), we'll simulate parallel execution:

1. **Create unit tests** (Subtask 004) - Test Agent role
2. **Verify documentation** (Subtask 005) - Doc Agent role (quick check)
3. **Run quality gates** (Subtask 006) - Guardian Agent role

---

## Success Criteria

### Subtask 004 Success:
- ✅ All test cases implemented (time parser, CLI integration, edge cases)
- ✅ Test coverage ≥ 90% for new code
- ✅ All tests passing with pytest

### Subtask 005 Success:
- ✅ Docstring examples complete (already done)
- ✅ README updated (if exists)
- ✅ CHANGELOG entry added (if exists)

### Subtask 006 Success:
- ✅ Syntax validation: PASSING
- ✅ Linting validation: PASSING
- ✅ Unit tests: PASSING
- ✅ Golden Rules: PASSING
- ✅ Integration test: PASSING

### Overall Genesis Mission Success:
- ✅ Feature fully implemented and tested
- ✅ All quality gates passing
- ✅ Path A+ methodology validated
- ✅ Autonomous development proven viable

---

## Risk Assessment

### Low Risk ✅
- Time parser implementation (proven working)
- CLI integration (tested with actual data)
- Quality gates (currently passing)

### Medium Risk ⚠️
- Test file creation (new file, may need package structure setup)
- Mock data generation for tests (need realistic fixtures)

### Mitigation Strategies
1. **Test Setup**: Check existing test patterns in hive-cli package
2. **Mock Strategy**: Use simple dict mocks, avoid complex DB mocking
3. **Incremental Validation**: Run tests after each test class

---

## Next Immediate Action

**Execute Subtask 004: Create Unit Tests**

Role: Test Agent (manual execution by Claude)
File: `packages/hive-cli/tests/test_tasks_command.py`
Duration: ~40 minutes estimated

**Command to initiate**:
```
Proceed to Subtask 004: Create comprehensive unit tests for time parsing and CLI filtering
```

---

## Metrics Tracking

| Subtask | Estimated | Actual | Status | Variance |
|---------|-----------|--------|--------|----------|
| 001 | 30 min | ~25 min | ✅ | -17% |
| 002 | 15 min | ~10 min | ✅ | -33% |
| 003 | 20 min | ~15 min | ✅ | -25% |
| 004 | 40 min | TBD | 🔄 | TBD |
| 005 | 10 min | TBD | 🔄 | TBD |
| 006 | 15 min | TBD | 🔄 | TBD |
| **Total** | **130 min** | **~50 min** | **46%** | **-23% avg** |

**Current Performance**: Ahead of schedule by 23% (Planner's estimates conservative)
