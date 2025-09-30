# Hive Platform Testing Guide

**Authoritative testing documentation for all Hive packages and applications.**

Replaces individual test directory READMEs with centralized guidance.

---

## Quick Start

```bash
# Run all tests
pytest

# Run specific categories
pytest tests/unit/          # Fast isolated tests
pytest tests/integration/   # Component interaction tests
pytest tests/e2e/           # End-to-end workflows

# With coverage
pytest --cov=. --cov-report=html

# Validate golden rules
python scripts/validate_golden_rules.py
```

---

## Directory Structure

Standard across all apps/ and packages/:

```
tests/
├── unit/          # Isolated component tests (<100ms)
├── integration/   # Multi-component tests (100ms-5s)
├── e2e/           # End-to-end workflows (5s-30s)
├── resilience/    # Failure mode testing
└── benchmarks/    # Performance measurement
```

---

## Test Categories

### Unit Tests (`unit/`)
- **Fast**: <100ms per test
- **Isolated**: No DB, network, or file system
- **Mocked**: Heavy use of mocks/stubs
- **Coverage**: 80%+ for core logic

### Integration Tests (`integration/`)
- **Moderate**: 100ms-5s per test
- **Real Dependencies**: May use DB, services
- **Focus**: Component interactions, API contracts
- **Coverage**: 60%+ for integration points

### E2E Tests (`e2e/`)
- **Slow**: 5s-30s per test
- **Full Stack**: Browser automation, API clients
- **Focus**: User journeys, acceptance criteria

### Resilience Tests (`resilience/`)
- **Focus**: Circuit breakers, timeouts, retry logic
- **Tools**: `from hive_async.resilience import AsyncCircuitBreaker`

### Benchmark Tests (`benchmarks/`)
- **Focus**: Latency, throughput, resource usage
- **Tools**: pytest-benchmark

---

## Naming Conventions

**Files**: `test_<module>.py`
**Classes**: `TestMyFeature`
**Functions**: `test_specific_behavior`

```python
# Good
def test_circuit_breaker_opens_after_threshold()
def test_connection_pool_handles_exhaustion()

# Bad
def test1()
def testStuff()
```

---

## Writing Tests

### Template

```python
"""Tests for my_feature module."""

from __future__ import annotations

import pytest
from my_package import MyClass


class TestMyFeature:
    """Test suite for MyClass."""

    @pytest.fixture
    def my_fixture(self):
        """Fixture description."""
        return MyClass()

    def test_basic_functionality(self, my_fixture):
        """Test basic functionality works."""
        result = my_fixture.do_something()
        assert result == expected

    def test_error_handling(self, my_fixture):
        """Test error handling."""
        with pytest.raises(ValueError):
            my_fixture.do_something(invalid_input)
```

### Best Practices

**Do**:
- Independent tests (no order dependencies)
- Descriptive names explaining what's tested
- One assertion per test
- AAA pattern: Arrange, Act, Assert
- Use fixtures for setup/teardown

**Don't**:
- Test implementation details
- Use global state
- Hardcode paths
- Leave failing tests commented out
- Skip tests without reason

---

## Common Fixtures

```python
# Database
@pytest.fixture
def db_connection():
    from hive_db import create_database_manager
    manager = create_database_manager()
    yield manager
    manager.close_all_pools()

# Configuration
@pytest.fixture
def test_config():
    from hive_config import HiveConfig
    return HiveConfig(
        database={"path": ":memory:"},
        claude={"mock_mode": True}
    )

# Mock service
@pytest.fixture
def mock_claude(monkeypatch):
    def mock_call(*args, **kwargs):
        return {"response": "mocked"}
    monkeypatch.setattr("claude.call", mock_call)
```

---

## Golden Rules Compliance

All tests must comply with architectural golden rules:

```bash
# Validate before commit
python scripts/validate_golden_rules.py --incremental

# Full validation
python scripts/validate_golden_rules.py
```

**Key rules for tests**:
1. No `print()` - use `hive_logging`
2. No `sys.path` manipulation - proper imports
3. Import from `hive_*` packages
4. Type hints required
5. No hardcoded paths

---

## Running Tests

```bash
# Basic
pytest                          # All tests
pytest -v                       # Verbose
pytest -x                       # Stop on first failure
pytest -k "database"            # Match pattern

# Coverage
pytest --cov=. --cov-report=html
pytest --cov-report=term-missing

# Parallel
pytest -n auto                  # Requires pytest-xdist

# Performance
pytest --durations=10           # Show 10 slowest tests
```

---

## Continuous Integration

### Pre-Commit Hooks

```bash
pre-commit install
```

Runs automatically:
- Syntax validation
- Linting (ruff)
- Formatting (black)
- Type checking (mypy)
- Golden rules

### CI Pipeline

GitHub Actions validates:
1. All tests pass
2. Coverage thresholds met
3. Linting passes
4. Type checking passes
5. Golden rules compliance

---

## Troubleshooting

**Import errors**:
```bash
# Run from project root
cd /path/to/hive
pytest
```

**Database locked**:
```python
# Use in-memory DB
@pytest.fixture
def test_db():
    return ":memory:"
```

**Async tests**:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

---

## Architectural Validation Framework

Located in `packages/hive-tests/src/hive_tests/`:

### Golden Rules Validators

15 architectural rules enforced:

1. No sys.path manipulation
2. No print() statements (use hive_logging)
3. Hive packages required
4. No direct database imports
5. No hardcoded paths
6. Exception handling required
7. Type hints enforced
8. Docstring compliance
9. Layer separation (packages cannot import apps)
10. Component isolation
11. Configuration centralized
12. Async patterns enforced
13. Cache utilization
14. Performance monitoring
15. Resource cleanup

### Usage

```python
from hive_tests.architectural_validators import run_all_golden_rules

project_root = Path("/path/to/hive")
all_passed, results = run_all_golden_rules(project_root)

for rule_name, result in results.items():
    print(f"{rule_name}: {'PASS' if result['passed'] else 'FAIL'}")
    if not result['passed']:
        for violation in result['violations']:
            print(f"  - {violation}")
```

### Autofix Tool

Automated code fixes in `autofix.py`:

```bash
# Dry run
python packages/hive-tests/src/hive_tests/autofix.py --dry-run

# Apply fixes
python packages/hive-tests/src/hive_tests/autofix.py --fix

# Specific file
python packages/hive-tests/src/hive_tests/autofix.py --file path/to/file.py
```

Fixes:
- Missing trailing commas
- Import sorting
- Async naming conventions
- Type hint additions

---

## Resources

- pytest: https://docs.pytest.org/
- pytest-asyncio: Async test support
- pytest-cov: Coverage reporting
- pytest-xdist: Parallel execution
- Golden Rules: `scripts/validate_golden_rules.py --help`

---

## Contributing

When adding test utilities:

1. Add to `packages/hive-tests/src/hive_tests/`
2. Document in this README
3. Add examples
4. Update CI workflows if needed

**Questions?** Open an issue or ask in #hive-development