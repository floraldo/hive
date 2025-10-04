# Path A+ Playbook - Quick Reference

**Use This**: When executing autonomous development with human oversight

---

## Pre-Flight Checklist

### Before Starting
- [ ] Clear feature specification exists
- [ ] Success criteria defined
- [ ] Database/environment ready
- [ ] Quality gates functional (syntax, lint, test, Golden Rules)
- [ ] Human available for checkpoints

### Planning Phase
- [ ] Create Planner Agent execution plan
- [ ] Estimate each subtask conservatively
- [ ] Identify dependencies explicitly
- [ ] Note parallel execution opportunities
- [ ] Specify deliverables precisely
- [ ] Include edge cases in plan

---

## Execution Phases

### Phase 1: Planning (Planner Agent)
```
1. Load task specification
2. Analyze requirements
3. Decompose into subtasks (4-8 typical)
4. Estimate durations conservatively
5. Identify dependencies
6. Create execution plan
7. CHECKPOINT: Human reviews plan
```

**Output**: Structured JSON plan with subtasks, dependencies, estimates

### Phase 2: Implementation (Coder Agent)
```
1. Execute subtasks sequentially (unless parallel-safe)
2. Run syntax check after each file edit
3. Run linting after each completion
4. Test manually with real data
5. CHECKPOINT: Human verifies implementation
```

**Quality Gates** (run per subtask):
- `python -m py_compile <file>`
- `ruff check <file> --fix`

### Phase 3: Testing (Test Agent)
```
1. Create comprehensive test suite
   - Valid inputs (happy path)
   - Invalid inputs (error cases)
   - Edge cases (boundaries, nulls, extremes)
   - Integration tests (combined filters, real scenarios)
2. Run tests: pytest <test_file> -v
3. Fix any failures immediately
4. Aim for >90% coverage
5. CHECKPOINT: Human reviews test results
```

**Test Structure** (Genesis Pattern):
```python
class TestFunctionName:
    def test_valid_inputs(self): ...
    def test_invalid_inputs(self): ...
    def test_edge_cases(self): ...
    def test_boundary_conditions(self): ...

class TestIntegration:
    def test_realistic_scenarios(self): ...
    def test_combined_operations(self): ...
```

### Phase 4: Documentation (Doc Agent)
```
1. Update docstrings with examples
2. Add usage examples to README (if applicable)
3. Create/update CHANGELOG entry
4. Document edge cases
5. CHECKPOINT: Human verifies docs
```

### Phase 5: Validation (Guardian Agent)
```
1. Syntax validation (py_compile)
2. Linting validation (ruff check)
3. Unit tests (pytest)
4. Golden Rules (validate_golden_rules.py --level ERROR)
5. Integration test (manual with real data)
6. CHECKPOINT: Human approves for merge
```

---

## Quality Gates (Copy-Paste Ready)

### Syntax Check
```bash
python -m py_compile packages/<package>/src/<module>/<file>.py
```

### Linting
```bash
ruff check packages/<package>/src/<module>/<file>.py --fix
```

### Unit Tests
```bash
cd packages/<package> && python -m pytest tests/ -v
```

### Golden Rules
```bash
python scripts/validation/validate_golden_rules.py --level ERROR
```

### Test Collection (Quick Check)
```bash
python -m pytest --collect-only
```

---

## Common Patterns

### Time Filter Pattern (from Genesis)
```python
def parse_relative_time(time_str: str) -> datetime:
    """Parse 2d, 1h, 30m formats."""
    pattern = r'^(\d+)(d|day|days|h|hour|hours|m|min|minutes|w|week|weeks)$'
    match = re.match(pattern, time_str.lower())
    if not match:
        raise ValueError(f"Invalid format: '{time_str}'")
    amount = int(match.group(1))
    unit = match.group(2)
    # ... timedelta mapping
    return datetime.now() - delta
```

### Timezone Normalization (from Genesis)
```python
# Convert timezone-aware to naive for comparison
dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).replace(tzinfo=None)
```

### Combined Filters (from Genesis)
```python
# Apply filters sequentially
if status:
    items = [i for i in items if i['status'] == status]
if worker:
    items = [i for i in items if i['worker'] == worker]
if since_timestamp:
    items = [i for i in items if datetime.fromisoformat(i['created_at']) >= since_timestamp]
```

### API-First Error Handling (from Genesis)
```python
try:
    # operation
except ValueError as e:
    error_msg = str(e)
    if pretty:
        click.echo(f"Error: {error_msg}", err=True)
    else:
        click.echo(json.dumps({"error": error_msg}), err=True)
    raise click.Abort() from e
```

---

## Checkpoint Protocol

### When to Checkpoint
1. **After Planning**: Review plan before execution
2. **After Implementation**: Verify feature works
3. **After Testing**: Review test results
4. **After Validation**: Approve for merge

### What to Review
- **Planning**: Scope, estimates, dependencies
- **Implementation**: Code quality, edge cases
- **Testing**: Coverage, test quality, failures
- **Validation**: Quality gates, production readiness

### How to Decide
- ✅ **Proceed**: All deliverables complete, quality gates pass
- ⚠️ **Revise**: Minor issues, quick fixes needed
- ❌ **Abort**: Major issues, rethink approach

---

## Troubleshooting

### Common Issues

#### Tests Failing
```bash
# 1. Check syntax first
python -m py_compile <file>

# 2. Check test collection
python -m pytest --collect-only

# 3. Run single test with verbose output
python -m pytest tests/test_file.py::test_name -vv

# 4. Check for missing imports
ruff check <file>
```

#### Linting Errors
```bash
# Auto-fix most issues
ruff check <file> --fix

# Manual review remaining
ruff check <file>
```

#### Import Errors
```bash
# Check package structure
ls packages/<package>/src/<module>/

# Verify __init__.py exists
cat packages/<package>/src/<module>/__init__.py

# Test import directly
python -c "from <module> import <function>"
```

#### Timezone Issues
```python
# Convert to naive datetime for comparison
dt = datetime.fromisoformat(ts).replace(tzinfo=None)

# Or make both timezone-aware
from datetime import timezone
dt_aware = datetime.now(timezone.utc)
```

---

## Performance Benchmarks (from Genesis)

| Metric | Target | Genesis Actual |
|--------|--------|----------------|
| Plan Accuracy | 80-90% | 85% |
| Implementation Speed | -10% to +20% | -25% (faster) |
| Test Coverage | >90% | 100% |
| Quality Gate Pass | 100% | 100% |
| Human Checkpoints | 4-6 | 5 |
| Bug Discovery Rate | 1-2/feature | 1.5/feature |

---

## Time Estimates (Rule of Thumb)

### By Complexity
- **Simple** (click option, docstring): 10-15 min
- **Medium** (utility function, filter logic): 20-30 min
- **Complex** (multi-file, async, integration): 40-60 min

### By Phase
- **Planning**: 10-20% of total time
- **Implementation**: 40-50% of total time
- **Testing**: 30-40% of total time
- **Documentation**: 5-10% of total time
- **Validation**: 10-15% of total time

### Genesis Example (130 min feature)
- Planning: 0 min (manual simulation)
- Implementation: 50 min (3 subtasks)
- Testing: 45 min (19 tests + fixes)
- Documentation: 5 min (already done during coding)
- Validation: 10 min (all gates)
- **Total**: 110 min (15% faster than estimated)

---

## Success Criteria Template

### Feature Completeness
- [ ] All requirements implemented
- [ ] All acceptance criteria met
- [ ] Edge cases handled
- [ ] Error messages clear

### Quality
- [ ] Syntax validation: PASS
- [ ] Linting: PASS
- [ ] Unit tests: PASS (>90% coverage)
- [ ] Golden Rules: PASS
- [ ] Integration test: PASS

### Documentation
- [ ] Docstring updated with examples
- [ ] README updated (if applicable)
- [ ] CHANGELOG entry added
- [ ] Edge cases documented

### Performance
- [ ] No performance regression
- [ ] Resource usage acceptable
- [ ] Scales to expected load

---

## Next Steps After Completion

### Immediate
1. Create Git commit with descriptive message
2. Run pre-commit hooks
3. Create PR with summary
4. Request human review

### Follow-Up
1. Monitor production usage
2. Gather user feedback
3. Update pattern library
4. Extract reusable components

---

## Graduation Criteria (Path A+ → Path B)

### Technical Readiness
- [ ] 5+ features delivered via Path A+
- [ ] Quality gates automated and reliable
- [ ] Test coverage consistently >90%
- [ ] Golden Rules passing consistently
- [ ] Error recovery patterns documented

### Operational Readiness
- [ ] Monitoring and alerting in place
- [ ] Rollback capability exists
- [ ] Human review before production deploy
- [ ] Pattern library established

### Risk Tolerance
- [ ] Non-critical features only
- [ ] Gradual rollout capability
- [ ] User impact limited
- [ ] Quick recovery possible

---

## Quick Command Reference

```bash
# Full validation suite (copy-paste ready)
python -m py_compile packages/<pkg>/src/<module>/<file>.py && \
ruff check packages/<pkg>/src/<module>/<file>.py && \
cd packages/<pkg> && python -m pytest tests/ -v && \
cd ../.. && python scripts/validation/validate_golden_rules.py --level ERROR

# Single test debug
python -m pytest tests/test_file.py::TestClass::test_method -vv -s

# Coverage check
pytest tests/ --cov=src --cov-report=term-missing

# Watch mode (re-run on file change)
pytest tests/ --watch

# Parallel test execution
pytest tests/ -n auto
```

---

## Anti-Patterns to Avoid

❌ **Skip Planning**: "Let's just start coding"
❌ **Optimistic Estimates**: "This will only take 10 minutes"
❌ **Testing Afterthought**: "We'll write tests later"
❌ **Documentation Neglect**: "We'll document it eventually"
❌ **Quality Gate Skipping**: "It looks fine, deploy it"
❌ **Over-Engineering**: "Let's add every possible feature"
❌ **Under-Specification**: "Figure it out as you go"

---

## Key Principles

1. **Plan First, Code Second** - 30 min planning saves hours debugging
2. **Test Immediately** - Catch bugs when context is fresh
3. **Document During Development** - It's faster and more accurate
4. **Quality Gates Are Time Savers** - Early detection is cheap detection
5. **Human Checkpoints Are Strategic** - Not micromanagement, oversight
6. **Conservative Estimates Win** - Better 15% fast than 50% late
7. **Edge Cases Are Not Edge** - They're core requirements

---

**Path A+ Motto**: *"Autonomous execution, human validation, perfect collaboration"*

**Use This Playbook For**: Every new feature until Path B readiness achieved (5+ successful missions)

---

*Based on Project Genesis learnings - 2025-10-04*
