# Hive Platform Developer Onboarding Guide

**Version**: 3.0 (Platinum Architecture)
**Last Updated**: 2025-09-28
**Target Audience**: New developers joining the Hive project

## Welcome to Hive Platform

Congratulations on joining the Hive platform development team! This guide will get you productive quickly while ensuring you understand our architectural standards and development practices.

## 🚀 Quick Start (15 minutes)

### Prerequisites
- **Python 3.11+** (required)
- **Git** (latest version)
- **VS Code** or **PyCharm** (recommended)
- **Windows/Linux/macOS** (cross-platform)

### Initial Setup
```bash
# 1. Clone the repository
git clone <repository-url>
cd hive

# 2. Create feature branch (NEVER work on main)
git checkout -b feature/your-name-onboarding

# 3. Install core packages
cd packages/hive-db && pip install -e .
cd ../hive-logging && pip install -e .
cd ../hive-config && pip install -e .

# 4. Verify installation
python scripts/validate_golden_rules.py

# 5. Run your first test
python -m pytest tests/benchmarks/test_core_performance.py::TestCorePerformance::test_json_serialization_performance -v
```

**Success Indicator**: You should see a green test pass with benchmark metrics.

## 🏗️ Architecture Overview

### Core Pattern: Inherit → Extend
```
packages/          # Infrastructure layer (INHERIT)
├── hive-db/      # Database utilities
├── hive-logging/ # Logging framework
├── hive-config/  # Configuration management
└── ...

apps/             # Business logic layer (EXTEND)
├── ai-deployer/ # Deployment automation
├── ai-planner/  # Planning services
├── ai-reviewer/ # Code review automation
└── ...
```

### Golden Rule: Dependency Flow
```
✅ CORRECT: apps → packages
✅ CORRECT: apps → apps.core
❌ FORBIDDEN: packages → apps
❌ FORBIDDEN: packages → apps.core
```

## 📋 Development Standards

### 1. Golden Rules Compliance (A++ Grade)
We maintain **15 architectural rules** that ensure code quality:

```bash
# Check compliance before every commit
python scripts/validate_golden_rules.py

# Common violations and fixes:
# ❌ print("debug info")
# ✅ from hive_logging import get_logger; logger = get_logger(__name__)

# ❌ from apps.something import utilities
# ✅ from hive_db import get_sqlite_connection
```

### 2. Service Layer Discipline
```python
# CORRECT Structure
apps/your-app/src/your_app/
├── core/                    # Interfaces (abstract)
│   ├── interfaces.py       # ABC definitions
│   └── config.py          # Configuration
└── services/               # Implementations (concrete)
    ├── implementation.py   # Business logic
    └── monitoring_impl.py  # Service implementations
```

### 3. Pre-commit Quality Gates
```bash
# Install pre-commit hooks (run once)
pip install pre-commit
pre-commit install

# Your code is automatically checked for:
# - Black formatting
# - Import sorting (isort)
# - Type checking (mypy)
# - Linting (ruff)
```

## 🛠️ Development Workflow

### Daily Development Loop
```bash
# 1. Start your day
git status && git pull origin main

# 2. Create/switch to feature branch
git checkout -b feature/your-feature-name

# 3. Make changes (edit files)
# 4. Check compliance
python scripts/validate_golden_rules.py

# 5. Run relevant tests
python -m pytest tests/ -k "your_feature" -v

# 6. Commit changes
git add .
git commit -m "feat: implement user authentication system

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 7. Push and create PR
git push -u origin feature/your-feature-name
```

### Code Quality Checklist
Before every commit, ensure:
- [ ] Golden Rules validation passes (`python scripts/validate_golden_rules.py`)
- [ ] Tests pass (`python -m pytest`)
- [ ] Pre-commit hooks pass (automatic on commit)
- [ ] No `print()` statements in code (use `hive_logging`)
- [ ] Type hints added for new functions
- [ ] Documentation updated if needed

## 📦 Working with Packages

### hive-db (Database Operations)
```python
from hive_db import get_sqlite_connection, batch_insert

# Connect to database
conn = get_sqlite_connection("app.db")

# Batch operations for performance
data = [{"id": 1, "name": "example"}]
batch_insert(conn, "users", data, columns=["id", "name"])
```

### hive-logging (Structured Logging)
```python
from hive_logging import get_logger

logger = get_logger(__name__)

# Structured logging
logger.info("User authenticated", extra={
    "user_id": 123,
    "ip_address": "192.168.1.1"
})
```

### hive-config (Configuration Management)
```python
from hive_config import HiveConfig, load_config

# Extend base config
class MyAppConfig(HiveConfig):
    api_key: str = "default"
    timeout: int = 30

config = load_config()
```

## 🔍 Common Development Patterns

### 1. Creating New Apps
```bash
# Use the inherit-extend pattern
mkdir -p apps/my-new-app/src/my_new_app/core
mkdir -p apps/my-new-app/src/my_new_app/services

# Always create core interfaces first
touch apps/my-new-app/src/my_new_app/core/interfaces.py
touch apps/my-new-app/src/my_new_app/core/config.py

# Then implement business logic
touch apps/my-new-app/src/my_new_app/services/implementation.py
```

### 2. Async Function Naming
```python
# CORRECT: Async functions end with _async
async def process_data_async(data):
    return await some_operation(data)

# INCORRECT: Missing _async suffix
async def process_data(data):  # Will fail Golden Rules
    return await some_operation(data)
```

### 3. Error Handling
```python
from hive_logging import get_logger
from hive_errors import HiveError

logger = get_logger(__name__)

try:
    result = risky_operation()
except Exception as e:
    logger.error("Operation failed", extra={"error": str(e)})
    raise HiveError(f"Failed to process: {e}") from e
```

## 🧪 Testing Standards

### Running Tests
```bash
# All tests
python -m pytest

# Specific module
python -m pytest tests/test_authentication.py -v

# Performance benchmarks
python -m pytest tests/benchmarks/ --benchmark-only

# Coverage report
python -m pytest --cov=src --cov-report=html
```

### Writing Tests
```python
import pytest
from hive_db import get_sqlite_connection
from your_app.services.implementation import YourService

class TestYourService:
    @pytest.fixture
    def service(self):
        return YourService()

    def test_feature_works(self, service):
        result = service.process_data({"test": "data"})
        assert result["status"] == "success"
```

## 🚨 Common Pitfalls & Solutions

### 1. Import Errors
```python
# ❌ WRONG: Importing from apps
from apps.ai_planner.src.ai_planner import something

# ✅ CORRECT: Use packages
from hive_db import get_sqlite_connection
from hive_logging import get_logger
```

### 2. Unicode Issues (Windows)
```python
# If you see encoding errors on Windows:
# ✅ Files are saved as UTF-8 (not UTF-8 BOM)
# ✅ Use .gitattributes for line endings
# ✅ Never use emoji in code comments
```

### 3. Pre-commit Hook Failures
```bash
# If pre-commit fails:
# 1. Fix the issues shown
# 2. Re-stage files: git add .
# 3. Commit again: git commit -m "your message"

# To skip hooks temporarily (emergency only):
git commit --no-verify -m "emergency fix"
```

## 📚 Advanced Topics

### Architecture Decision Records (ADRs)
Located in `docs/architecture/adr/`, document major decisions:
- ADR-001: Dependency Injection Pattern
- ADR-002: Golden Rules Governance
- ADR-003: Async Function Naming
- ADR-004: Service Layer Architecture

### Performance Monitoring
```bash
# Benchmark your changes
python -m pytest tests/benchmarks/test_core_performance.py --benchmark-only

# Check for regressions
python -m pytest tests/benchmarks/ --benchmark-compare=baseline.json
```

### Fleet Command System (Advanced)
Multi-agent development system in tmux:
```bash
# Initialize fleet
./scripts/fleet_send.sh send backend "[T101] Implement user authentication"

# Monitor progress
tmux list-sessions
```

## 🆘 Getting Help

### Immediate Help
1. **Check Golden Rules**: `python scripts/validate_golden_rules.py`
2. **Run Tests**: `python -m pytest tests/ -v`
3. **Check Logs**: Look in `logs/` directory
4. **Read ADRs**: Review decision records in `docs/architecture/adr/`

### Code Examples
- **Authentication**: `apps/ai-deployer/src/ai_deployer/core/`
- **Database Usage**: `packages/hive-db/src/hive_db/`
- **Logging Patterns**: `packages/hive-logging/src/hive_logging/`
- **Configuration**: `apps/*/src/*/core/config.py`

### Best Practices
- **Start Small**: Make one small change, test it, commit it
- **Follow Patterns**: Look at existing code for examples
- **Ask Questions**: Better to ask than make assumptions
- **Read ADRs**: Understand the "why" behind decisions

## 🎯 Your First Week Goals

### Day 1-2: Environment Setup
- [ ] Complete quick start setup
- [ ] Run all benchmark tests successfully
- [ ] Make your first small commit (fix a typo, add a comment)

### Day 3-4: Code Understanding
- [ ] Read through 2-3 ADRs
- [ ] Explore one app directory structure
- [ ] Run Golden Rules validation on entire codebase

### Day 5-7: First Contribution
- [ ] Pick a small bug or enhancement
- [ ] Follow the development workflow
- [ ] Create your first pull request

## 🏆 Success Metrics

You're successfully onboarded when you can:
1. Create a feature branch and make commits without Golden Rules violations
2. Write a new service following the inherit-extend pattern
3. Add tests and benchmarks for your code
4. Navigate the codebase confidently
5. Understand the "why" behind our architectural decisions

## 🔗 Quick Reference Links

### Essential Commands
```bash
# Daily workflow
python scripts/validate_golden_rules.py
python -m pytest tests/ -v
git status && git branch

# Quality checks
pre-commit run --all-files
python -m pytest tests/benchmarks/ --benchmark-only

# Package development
cd packages/your-package && pip install -e .
```

### File Locations
- **Golden Rules**: `packages/hive-tests/src/hive_tests/architectural_validators.py`
- **Project Config**: `.claude/project.yaml`
- **ADRs**: `docs/architecture/adr/`
- **Benchmarks**: `tests/benchmarks/`
- **Documentation**: `claudedocs/`

---

**Welcome to the team! Remember: Build only what's asked, follow the patterns, and when in doubt, check the Golden Rules.**

*Updated for Hive Platform v3.0 Platinum Architecture*