# Hive Test Intelligence

**Intelligent test analysis and health monitoring for the Hive platform.**

## Overview

Hive Test Intelligence provides automated test result collection, flaky test detection, failure trend analysis, and actionable insights for platform health monitoring. It replaces manual test result triage with intelligent, data-driven analysis.

## Features

- **Automatic Test Result Collection**: Pytest plugin captures comprehensive test execution data
- **Flaky Test Detection**: Identifies tests with intermittent failures requiring attention
- **Trend Analysis**: Tracks package health over time to identify improvement or degradation
- **Failure Pattern Clustering**: Groups similar failures to identify common root causes
- **Slow Test Identification**: Detects performance bottlenecks in the test suite
- **Rich CLI Interface**: Beautiful terminal dashboards for quick insights

## Installation

```bash
# Install the package
pip install -e packages/hive-test-intelligence

# The pytest plugin is automatically activated
```

## Usage

### Automatic Data Collection

The pytest plugin automatically collects test data when you run tests:

```bash
# Run tests normally - intelligence collection happens automatically
python -m pytest packages/

# Data is stored in: data/test_intelligence.db
```

### CLI Commands

#### Show Platform Health Status

```bash
hive-test-intel status
```

Output:
```
Platform Test Health Dashboard
Generated: 2025-10-04 18:30:00

Latest Test Run:
  Total Tests: 821
  Passed: 560
  Failed: 178
  Errors: 18
  Skipped: 65
  Pass Rate: 68.2%
  Duration: 254.58s

Package Health (Last 7 Days):
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Package               ┃ Tests┃ Pass Rate ┃ Trend  ┃ Flaky ┃ Avg Duration ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━┩
│ ✅ hive-config        │   45 │   100.0%  │ → stable│     0 │        150ms │
│ ✅ hive-logging       │   38 │   100.0%  │ → stable│     0 │        120ms │
│ ⚠️  hive-ai           │  187 │    42.3%  │ ↘ -15% │     5 │        450ms │
│ ⚠️  hive-tests        │   56 │    58.9%  │ ↘ -8%  │     2 │        320ms │
└───────────────────────┴──────┴───────────┴────────┴───────┴──────────────┘
```

#### Detect Flaky Tests

```bash
hive-test-intel flaky --threshold 0.2
```

Output:
```
Flaky Test Detection

Found 12 flaky tests:

1. packages/hive-orchestration/tests/test_concurrent_tasks.py::test_parallel_execution
   Fail Rate: 23% (7/30 runs)
   Passed: 23 | Failed: 5 | Errors: 2
   Recent Errors:
     • sqlite3.OperationalError: database is locked...
     • asyncio.TimeoutError: Task timed out after 5.0s...
```

#### Analyze Trends

```bash
hive-test-intel trends --days 7 --packages hive-ai,hive-orchestration
```

#### Identify Slow Tests

```bash
hive-test-intel slow --top 20
```

#### Analyze Failure Patterns

```bash
hive-test-intel patterns
```

Output:
```
Failure Pattern Analysis

Found 3 failure patterns:

1. Pattern: TypeError: 'tuple' object does not support item assignment
   Affected Tests: 47
   Packages: hive-ai, hive-tests, hive-orchestration
   Suggested Cause: Possible Pydantic migration issue - check for tuple wrapping
   Tests:
     • packages/hive-ai/tests/test_agents_agent.py::TestBaseAgentTools::test_add_tool
     • packages/hive-ai/tests/test_agents_agent.py::TestBaseAgentTools::test_remove_tool
     ... and 45 more
```

## Architecture

### Components

1. **Collector** (`collector.py`): Pytest plugin that captures test execution data
2. **Storage** (`storage.py`): SQLite persistence layer for test history
3. **Analyzer** (`analyzer.py`): Statistical analysis and pattern detection
4. **CLI** (`cli.py`): Rich-based command-line interface
5. **Models** (`models.py`): Pydantic data models

### Data Model

```
test_runs:
  - id, timestamp, total_tests, passed, failed, errors
  - duration_seconds, git_commit, git_branch

test_results:
  - id, run_id, test_id, status, duration_ms
  - error_message, package_name, test_type, file_path

Derived Analytics:
  - flaky_tests (computed from test_results)
  - package_health (aggregated statistics)
  - failure_patterns (clustered error messages)
```

## Integration

### With CI/CD

Export intelligence data for GitHub Actions:

```yaml
- name: Run Tests with Intelligence
  run: python -m pytest packages/

- name: Check for Regressions
  run: |
    hive-test-intel status --days 1 > test_report.txt
    # Block merge if flaky tests increased
```

### With hive-orchestration

Automatically create tasks for failing tests:

```python
from hive_test_intelligence import TestIntelligenceAnalyzer
from hive_orchestration import create_task

analyzer = TestIntelligenceAnalyzer()
flaky_tests = analyzer.detect_flaky_tests()

for flaky in flaky_tests:
    create_task(
        title=f"Fix flaky test: {flaky.test_id}",
        task_type="bug",
        priority="high" if flaky.fail_rate > 0.5 else "medium"
    )
```

## Development

### Running Tests

```bash
cd packages/hive-test-intelligence
pytest tests/
```

### Code Quality

```bash
ruff check src/
black src/
mypy src/
```

## License

Part of the Hive platform. See main project LICENSE.
