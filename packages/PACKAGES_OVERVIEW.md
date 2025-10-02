# Hive Platform Packages - Infrastructure Layer Overview

**For**: AI agents working exclusively in the `packages/` directory
**Context**: Modular monolith architecture - packages are the infrastructure layer
**Last Updated**: 2025-09-30

---

## Architecture Context

### The Inherit→Extend Pattern

```
Hive Platform Architecture
├── apps/           # Business Logic Layer (extend)
│   ├── ecosystemiser/
│   ├── hive-orchestrator/
│   ├── ai-planner/
│   └── [other apps inherit from packages]
│
└── packages/       # Infrastructure Layer (inherit) ← YOU ARE HERE
    ├── hive-config/
    ├── hive-logging/
    ├── hive-db/
    └── [shared utilities]
```

**Critical Rule**: Packages NEVER import from apps. Dependency flow: `apps → packages`

---

## Package Catalog (16 Total, 242+ Python Files)

### 1. **hive-config** - Configuration Management
**Purpose**: Centralized configuration with Dependency Injection patterns
**Status**: Production-ready, actively used
**Key Pattern**: DI-first (no global singletons)

**Core Capabilities**:
- `create_config_from_sources()`: Primary config factory (DI pattern)
- `HiveConfig`: Platform-wide configuration schema (Pydantic)
- Environment variable overrides
- Type-safe configuration models
- Path management utilities

**Dependencies**: `hive-logging`

**Usage Pattern**:
```python
from hive_config import HiveConfig, create_config_from_sources

# Dependency Injection pattern (GOLD STANDARD)
class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()
        self.db_path = self._config.database.path
```

**Key Files**:
- `unified_config.py`: Main config schema and factory
- `loader.py`: Config loading from multiple sources
- `paths.py`: Project path management
- `validation.py`: Config validation utilities

**Anti-Pattern** (DEPRECATED):
```python
from hive_config import get_config  # AVOID - global state!
```

---

### 2. **hive-logging** - Structured Logging
**Purpose**: Standardized logging infrastructure
**Status**: Production-ready, mandatory use

**Core Capabilities**:
- `get_logger(__name__)`: Standard logger factory
- Structured logging with context
- Performance logging utilities
- Integration with monitoring systems

**Dependencies**: None (foundation layer)

**Golden Rule**: NO `print()` statements in code - use `get_logger()` instead

**Usage Pattern**:
```python
from hive_logging import get_logger

logger = get_logger(__name__)
logger.info("Operation completed", extra={"duration": 1.23})
```

**Key Files**:
- `logger.py`: Core logging implementation

---

### 3. **hive-db** - Database Management
**Purpose**: Database utilities and connection pooling
**Status**: Production-ready, DI-enabled

**Core Capabilities**:
- Thread-safe connection pooling (SQLite + PostgreSQL)
- Async connection pooling (aiosqlite)
- Transaction management
- Database utilities (migrations, backups, schema)
- Health monitoring

**Dependencies**: None (foundation layer)

**Usage Pattern (DI)**:
```python
from hive_db import ConnectionPool

# Create pool with configuration (DI)
db_config = {
    "max_connections": 25,
    "min_connections": 5,
    "connection_timeout": 30.0
}
pool = ConnectionPool(db_config=db_config)

# Use pooled connection
with pool.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
```

**Key Features**:
- Sync pools for multi-threaded apps
- Async pools for 3-5x throughput
- Automatic connection validation
- Context managers for safety

---

### 4. **hive-cache** - High-Performance Caching
**Purpose**: Redis-based caching with intelligent TTL
**Status**: Production-ready, optimized for Claude API

**Core Capabilities**:
- Async Redis operations
- Intelligent TTL management
- Circuit breaker integration
- Multi-format serialization (MessagePack, JSON)
- Compression for large payloads
- Claude API response caching

**Dependencies**: None (foundation layer)

**Usage Pattern**:
```python
from hive_cache import get_cache_client

# Async cache operations
cache = await get_cache_client()
await cache.set("user:123", user_data, ttl=3600)
user = await cache.get("user:123")

# Pattern operations
await cache.delete_pattern("session:*")
```

**Key Features**:
- Connection pooling
- Performance monitoring
- Health checks
- Key namespacing

---

### 5. **hive-bus** - Event Bus & Messaging
**Purpose**: Inter-service communication infrastructure
**Status**: Production-ready

**Core Capabilities**:
- Async event publishing/subscription
- Message routing and filtering
- Dead letter queue handling
- Circuit breaker integration

**Dependencies**: None (foundation layer)

**Usage Pattern**:
```python
from hive_bus import EventBus

bus = EventBus()
await bus.publish("event.type", payload)
```

---

### 6. **hive-errors** - Error Handling
**Purpose**: Standardized error handling and reporting
**Status**: Production-ready

**Core Capabilities**:
- Base error classes with structured context
- Async error handling utilities
- Error monitoring and reporting
- Recovery strategy patterns

**Dependencies**: None (foundation layer)

**Usage Pattern**:
```python
from hive_errors import BaseError, ErrorReporter

class MyError(BaseError):
    pass

reporter = ErrorReporter()
await reporter.report(error, context)
```

---

### 7. **hive-async** - Async Utilities
**Purpose**: Async patterns and utilities
**Status**: Production-ready

**Core Capabilities**:
- AsyncResourceManager for cleanup
- Retry logic with exponential backoff
- Generic connection pooling
- Task management
- Concurrency control

**Dependencies**: None (foundation layer)

**Usage Pattern**:
```python
from hive_async import async_retry, TaskManager, gather_with_concurrency

# Retry with backoff
result = await async_retry(unstable_function, max_attempts=5)

# Concurrency-limited operations
results = await gather_with_concurrency(
    *[async_operation(i) for i in range(100)],
    max_concurrent=10
)
```

**Key Features**:
- Context managers
- Connection pooling
- Task coordination
- Circuit breakers

---

### 8. **hive-ai** - AI Infrastructure
**Purpose**: Core AI utilities and model management
**Status**: Production-ready

**Core Capabilities**:
- AI model client management
- Performance metrics collection
- Model registry and pooling
- Standardized AI interfaces

**Dependencies**: None (foundation layer)

**Components**:
- `core/`: Core interfaces and configuration
- `models/`: AI model management
- `agents/`: Agent patterns
- `prompts/`: Prompt templates
- `observability/`: AI monitoring

**Usage Pattern**:
```python
from hive_ai import AIClient, ModelRegistry

client = AIClient()
registry = ModelRegistry()
```

---

### 9. **hive-performance** - Performance Monitoring
**Purpose**: Performance metrics and monitoring
**Status**: Production-ready

**Core Capabilities**:
- Performance metrics collection
- Resource monitoring
- Prometheus integration
- Performance profiling

**Dependencies**: `hive-logging`

---

### 10. **hive-tests** - Testing & Validation
**Purpose**: Architectural validation and testing utilities
**Status**: Production-ready, CRITICAL for quality

**Core Capabilities**:
- **Golden Rules Validator**: 24 architectural rules (AST-based)
- Testing utilities and fixtures
- Autofix tool for common issues
- Performance benchmarking

**Dependencies**: `hive-config`

**Key Components**:
- `ast_validator.py`: AST-based validation (default, 100% coverage)
- `architectural_validators.py`: Legacy validator (deprecated)
- `autofix.py`: Automated code fixes

**Golden Rules** (24 enforced):
1. App Contract Compliance
2. Co-located Tests Pattern
3. No sys.path Manipulation
4. Single Config Source
5. Package-App Discipline
6. Dependency Direction
7. Service Layer Discipline
8. Interface Contracts
9. Error Handling Standards
10. Logging Standards (NO print()!)
11. Async Pattern Consistency
12. No Synchronous Calls in Async
13. Inherit-Extend Pattern
14. Package Naming Consistency
15. No Unsafe Function Calls
16. CLI Pattern Consistency
17. No Global State Access
18. Test Coverage Mapping
19. Documentation Hygiene
20. hive-models Purity
21. Python Version Consistency (3.11+)
22. Pyproject Dependency Usage
23. Unified Tool Configuration
24. Configuration DI Pattern (NEW)

**Usage**:
```bash
# Validate architecture
python scripts/validate_golden_rules.py

# Incremental validation (fast)
python scripts/validate_golden_rules.py --incremental

# Auto-fix issues
python packages/hive-tests/src/hive_tests/autofix.py --fix
```

---

### 11. **hive-app-toolkit** - Application Framework
**Purpose**: Production-grade app development accelerator
**Status**: Production-ready, strategic

**Core Capabilities**:
- FastAPI application templates
- Docker/Kubernetes configurations
- CI/CD pipeline generation
- Cost control framework
- Monitoring/observability patterns

**Dependencies**: `hive-logging`, `hive-performance`, `hive-cache`, `hive-config`, `hive-errors`

**Mission**: 5x faster development with battle-tested patterns

**Usage**:
```bash
# Create new service
hive-toolkit init my-service --type api

# Add capabilities
hive-toolkit add-api
hive-toolkit add-k8s
```

**Templates**:
- API Service (REST/GraphQL)
- Event-Driven Service
- Batch Processing

---

### 12. **hive-cli** - CLI Utilities
**Purpose**: Command-line interface utilities
**Status**: Production-ready

**Core Capabilities**:
- CLI framework patterns
- Rich terminal formatting
- Command parsing
- Interactive prompts

**Dependencies**: TBD

---

### 13. **hive-algorithms** - Algorithm Library
**Purpose**: Shared algorithms and data structures
**Status**: Production-ready

**Core Capabilities**:
- Common algorithms
- Data structure utilities
- Performance-optimized implementations

**Dependencies**: None (foundation layer)

---

### 14. **hive-models** - Data Models
**Purpose**: Shared data models and schemas
**Status**: Production-ready

**Core Capabilities**:
- Pydantic data models
- Schema definitions
- Validation logic

**Golden Rule**: Data-only, no business logic

**Dependencies**: None (foundation layer)

---

### 15. **hive-deployment** - Deployment Utilities
**Purpose**: Deployment automation and utilities
**Status**: Production-ready

**Core Capabilities**:
- Deployment scripts
- Environment management
- Release automation

**Dependencies**: TBD

---

### 16. **hive-service-discovery** - Service Registry
**Purpose**: Service discovery and registration
**Status**: Production-ready

**Core Capabilities**:
- Service registry
- Health checking
- Load balancing support

**Dependencies**: TBD

---

## Inter-Package Dependencies

### Dependency Graph (Simplified)

```
Foundation Layer (No dependencies):
├── hive-logging
├── hive-errors
├── hive-async
├── hive-db
├── hive-cache
├── hive-bus
├── hive-ai
├── hive-algorithms
├── hive-models
└── hive-service-discovery

Integration Layer (Depends on foundation):
├── hive-config → hive-logging
├── hive-performance → hive-logging
└── hive-tests → hive-config

Application Layer (Depends on multiple):
└── hive-app-toolkit → {hive-logging, hive-performance, hive-cache, hive-config, hive-errors}
```

**Key Principle**: Minimize cross-package dependencies, maximize cohesion

---

## Shared Patterns & Best Practices

### 1. Dependency Injection (DI) Pattern
**GOLD STANDARD** - Used everywhere

```python
# Correct DI pattern
class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()

# Wrong - global state
class MyService:
    def __init__(self):
        self.config = get_config()  # DEPRECATED
```

**Benefits**:
- Testable (inject mocks)
- Thread-safe (no global state)
- Explicit dependencies
- Parallel-friendly

### 2. Async-First Architecture
```python
# Async patterns
async with pool.get_connection() as conn:
    await conn.execute(query)

# Retry with backoff
result = await async_retry(operation, max_attempts=5)

# Concurrency control
results = await gather_with_concurrency(*tasks, max_concurrent=10)
```

### 3. Type Hints Everywhere
```python
def process_data(
    config: HiveConfig,
    data: dict[str, Any],
    timeout: float = 30.0
) -> ProcessResult:
    """Process data with configuration."""
    pass
```

### 4. Logging Standards
```python
from hive_logging import get_logger

logger = get_logger(__name__)
logger.info("Processing started", extra={"item_count": 100})
```

**Never**: `print()` statements in production code

### 5. Error Handling
```python
from hive_errors import BaseError

class ValidationError(BaseError):
    """Validation failed."""
    pass

try:
    validate(data)
except ValidationError as e:
    logger.error("Validation failed", exc_info=e)
    raise
```

### 6. Configuration Management
```python
# Create once at app startup
config = create_config_from_sources()

# Pass through DI
service = MyService(config=config)
worker = MyWorker(config=config)
```

### 7. Resource Management
```python
# Context managers for cleanup
async with AsyncResourceManager() as manager:
    manager.register_resource("db", db_conn, cleanup_callback=close_db)
    # Automatic cleanup

# Connection pools
async with pool.connection() as conn:
    await conn.execute(query)
    # Connection returned to pool
```

---

## Quality Gates & Standards

### Pre-Commit Checklist
1. Syntax validation: `python -m py_compile file.py`
2. Golden rules: `python scripts/validate_golden_rules.py --incremental`
3. Linting: `python -m ruff check .`
4. Type checking: `python -m mypy file.py`
5. Tests: `pytest tests/`

### Code Quality Tools
```toml
pytest = "^8.3.2"         # Testing
black = "^24.8.0"          # Formatting
mypy = "^1.8.0"            # Type checking
ruff = "^0.1.15"           # Linting
isort = "^5.13.0"          # Import sorting
```

### Performance Standards
- Unit tests: <100ms
- Integration tests: 100ms-5s
- E2E tests: 5s-30s
- Full validation: ~30-40s
- Incremental validation: ~2-5s

---

## Common Tasks

### Adding a New Package

1. **Create structure**:
```bash
mkdir -p packages/hive-mypackage/src/hive_mypackage/tests
```

2. **Add pyproject.toml**:
```toml
[tool.poetry]
name = "hive-mypackage"
version = "1.0.0"
description = "Package description"
packages = [{include = "hive_mypackage", from = "src"}]

[tool.poetry.dependencies]
python = "^3.11"
```

3. **Create __init__.py**:
```python
"""Hive MyPackage - Description"""
from .main import main_function

__all__ = ["main_function"]
__version__ = "1.0.0"
```

4. **Add README.md** with:
   - Purpose and features
   - Usage examples
   - Dependencies
   - Integration patterns

5. **Validate**:
```bash
python scripts/validate_golden_rules.py --app mypackage
```

### Importing from Packages

```python
# Correct - from packages
from hive_config import create_config_from_sources
from hive_logging import get_logger
from hive_db import ConnectionPool

# Wrong - never import apps in packages
from apps.ecosystemiser import something  # FORBIDDEN!
```

### Testing Patterns

```python
import pytest
from hive_config import HiveConfig

@pytest.fixture
def test_config() -> HiveConfig:
    """Isolated test configuration."""
    return HiveConfig(
        database={"path": ":memory:"},
        claude={"mock_mode": True}
    )

def test_service(test_config):
    service = MyService(config=test_config)
    assert service.is_configured()
```

---

## Emergency Procedures

### Syntax Errors in Code
```bash
# Fix trailing comma issues
python scripts/emergency_syntax_fix.py

# Validate syntax
python -m pytest --collect-only
```

### Golden Rule Violations
```bash
# Check violations
python scripts/validate_golden_rules.py

# Auto-fix common issues
python packages/hive-tests/src/hive_tests/autofix.py --fix
```

### Configuration Issues
```bash
# Verify config loading
python -c "from hive_config import create_config_from_sources; print(create_config_from_sources())"

# Check environment
python -c "import os; print(os.getenv('HIVE_ENVIRONMENT', 'development'))"
```

---

## Critical Rules for Package Development

### DO:
- ✅ Use Dependency Injection everywhere
- ✅ Type hints on all functions
- ✅ Use `hive_logging.get_logger()` for logging
- ✅ Write tests for all public APIs
- ✅ Document with docstrings and README
- ✅ Validate with golden rules before commit
- ✅ Use async patterns for I/O operations
- ✅ Handle errors with `hive_errors`
- ✅ Follow inherit→extend pattern

### DON'T:
- ❌ Import from apps/ directory (packages → apps forbidden)
- ❌ Use `print()` statements (use logger)
- ❌ Use global singletons (use DI)
- ❌ Use `sys.path` manipulation
- ❌ Hardcode paths (use `hive_config.paths`)
- ❌ Skip type hints
- ❌ Leave TODOs in production code
- ❌ Use `exec()`, `eval()`, or `pickle`
- ❌ Create global state

---

## Package Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/enhance-hive-cache

# 2. Make changes in packages/hive-cache/

# 3. Run tests
pytest packages/hive-cache/tests/

# 4. Validate architecture
python scripts/validate_golden_rules.py --incremental

# 5. Format and lint
black packages/hive-cache/
ruff check packages/hive-cache/

# 6. Type check
mypy packages/hive-cache/src/

# 7. Commit and push
git add packages/hive-cache/
git commit -m "feat(cache): Add Redis sentinel support"
git push origin feature/enhance-hive-cache
```

---

## Resources

### Documentation
- Main README: `/README.md`
- Project guide: `/.claude/CLAUDE.md`
- Golden rules: `packages/hive-tests/README.md`
- Config guide: `packages/hive-config/README.md`

### Validation Tools
- Golden rules: `scripts/validate_golden_rules.py`
- Autofix: `packages/hive-tests/src/hive_tests/autofix.py`
- Emergency fix: `scripts/emergency_syntax_fix.py`

### Key Concepts
- **Modular Monolith**: Single repo, independent packages
- **Inherit→Extend**: Apps inherit package infrastructure
- **Dependency Injection**: No global state, explicit dependencies
- **Golden Rules**: 24 architectural validators (100% coverage)
- **Type Safety**: Full type hints, mypy validation

---

## Getting Help

### Common Issues

**Q: Import error from package**
```python
# Wrong
from hive_config.unified_config import HiveConfig

# Right
from hive_config import HiveConfig
```

**Q: Configuration not loading**
```python
# Check __init__.py exports
from hive_config import create_config_from_sources
config = create_config_from_sources()
```

**Q: Golden rule violation**
```bash
# See violation details
python scripts/validate_golden_rules.py

# Try auto-fix
python packages/hive-tests/src/hive_tests/autofix.py --fix
```

**Q: Async pattern issues**
```python
# Use async patterns
async with pool.connection() as conn:
    await conn.execute(query)
```

### Support
- Check package README files
- Review existing patterns in similar packages
- Validate with golden rules
- Run tests frequently

---

## Summary

**Packages Directory**: Infrastructure layer providing reusable utilities for all Hive applications

**Key Packages**:
- `hive-config`: Configuration management (DI-first)
- `hive-logging`: Structured logging (mandatory)
- `hive-db`: Database pooling and utilities
- `hive-cache`: High-performance caching
- `hive-tests`: Architectural validation (24 golden rules)
- `hive-app-toolkit`: Application development accelerator

**Core Patterns**:
- Dependency Injection (no global state)
- Async-first architecture
- Type hints everywhere
- Golden rules compliance
- Inherit→extend model

**Quality Gates**:
- Golden rules validation (~30-40s)
- Type checking (mypy)
- Linting (ruff)
- Testing (pytest, 80%+ coverage)
- No syntax errors, no print() statements

**Remember**: Packages are the foundation. Keep them stable, well-tested, and independent. Apps build on this infrastructure through the inherit→extend pattern.