# Configuration Dependency Injection - Comprehensive Developer Guide

**Date**: 2025-09-30
**Status**: Active Migration
**Part of**: Project Aegis Phase 2

---

## Executive Summary

This guide provides complete instructions for migrating from global state configuration (`get_config()`) to dependency injection (DI) pattern across the Hive platform. The migration improves testability, eliminates hidden dependencies, and enables parallel execution.

**Key Facts**:
- ✅ **Total Migration Scope**: 13 `get_config()` usages
- ✅ **Risk Level**: LOW (backward compatible during migration)
- ✅ **Gold Standard**: EcoSystemiser demonstrates ideal pattern
- ✅ **Timeline**: 3.5 hours active work + adoption period

---

## Table of Contents

1. [Why We're Migrating](#why-were-migrating)
2. [Gold Standard Pattern](#gold-standard-pattern)
3. [Migration Recipes](#migration-recipes)
4. [Testing Strategies](#testing-strategies)
5. [Common Pitfalls](#common-pitfalls)
6. [FAQ](#faq)
7. [Quick Reference Card](#quick-reference-card)

---

## Why We're Migrating

### Problems with Global State

**1. Hidden Dependencies**
```python
# Who knows this needs config? Not obvious from signature!
class MyService:
    def __init__(self):
        self.config = get_config()  # Hidden dependency
```

**2. Testing Nightmares**
```python
# Tests interfere with each other - must reset global state
def test_service_a():
    load_config(path="test_a.json")
    service = MyService()
    # ... test

def test_service_b():
    load_config(path="test_b.json")  # Overwrites global state!
    service = MyService()  # Uses config from test_a if not reset!
```

**3. Thread Safety Issues**
```python
# Multiple threads sharing global config = race conditions
config = get_config()  # Global state
config.database.timeout = 30  # Affects ALL threads!
```

**4. Parallel Execution Blocked**
```python
# Can't run tests in parallel - global state conflicts
pytest -n auto  # FAILS with global config
```

### Benefits of Dependency Injection

**1. Explicit Dependencies**
```python
# Clear what this service needs!
class MyService:
    def __init__(self, config: HiveConfig):
        self._config = config  # Explicit dependency
```

**2. Easy Testing**
```python
# Each test isolated, parallel execution works
def test_service_a(mock_config_a):
    service = MyService(config=mock_config_a)

def test_service_b(mock_config_b):
    service = MyService(config=mock_config_b)

# Run in parallel: pytest -n auto  ✅ WORKS!
```

**3. Thread Safety by Default**
```python
# Each instance has its own config
config_a = create_config_from_sources()
config_b = create_config_from_sources()
service_a = MyService(config=config_a)  # Independent
service_b = MyService(config=config_b)  # Independent
```

**4. Flexible Configuration**
```python
# Different components can have different configs
prod_config = create_config_from_sources()
test_config = HiveConfig(database=DatabaseConfig(path=":memory:"))

prod_service = MyService(config=prod_config)
test_service = MyService(config=test_config)
```

---

## Gold Standard Pattern

The **EcoSystemiser** application demonstrates the ideal configuration pattern for Hive apps.

### Full Implementation

**File**: `apps/ecosystemiser/src/ecosystemiser/config/bridge.py`

```python
"""
Configuration bridge between EcoSystemiser and Hive platform.

Follows the inherit→extend pattern:
- Inherits: Core platform settings from hive-config
- Extends: Domain-specific EcoSystemiser settings
"""

from __future__ import annotations

from ecosystemiser.settings import Settings as EcoSystemiserSettings
from hive_config import DatabaseConfig as HiveDatabaseConfig
from hive_config import HiveConfig, create_config_from_sources
from hive_logging import get_logger

logger = get_logger(__name__)


class EcoSystemiserConfig:
    """Configuration bridge: inherit platform, extend domain."""

    def __init__(self, hive_config: HiveConfig | None = None):
        # Inherit: Platform configuration with DI
        self._hive_config = hive_config or create_config_from_sources()

        # Extend: Domain-specific configuration
        self._eco_config = EcoSystemiserSettings()

    @property
    def database(self) -> HiveDatabaseConfig:
        """Platform database configuration (inherited)"""
        return self._hive_config.database

    @property
    def climate_adapters(self):
        """Domain-specific climate adapter configuration (extended)"""
        return self._eco_config.profile_loader

    @property
    def solver(self):
        """Domain-specific solver configuration (extended)"""
        return self._eco_config.solver

    # ... additional properties for domain-specific config


# Singleton pattern at app level (not global!)
_config: EcoSystemiserConfig | None = None


def get_ecosystemiser_config() -> EcoSystemiserConfig:
    """Get singleton EcoSystemiser configuration instance"""
    global _config

    if _config is None:
        _config = EcoSystemiserConfig()
        logger.info("EcoSystemiser configuration bridge initialized")

    return _config
```

### Why This Pattern is Gold Standard

1. **Inherit→Extend**: Reuses platform config, extends with domain logic
2. **Dependency Injection**: Accepts optional config for testing
3. **Sensible Default**: Falls back to `create_config_from_sources()`
4. **Clear Separation**: Platform concerns vs domain concerns
5. **Type Safe**: Full IDE support with type hints
6. **Testable**: Easy to inject mock configs

### Usage in Production

```python
# Create config at app entry point
app_config = EcoSystemiserConfig()

# Use throughout application
db_path = app_config.database.path
climate_config = app_config.climate_adapters

# Pass to services
service = DataProcessor(config=app_config)
```

### Usage in Tests

```python
# Create test config with mocked platform config
test_hive_config = HiveConfig(
    database=DatabaseConfig(path=":memory:")
)
test_app_config = EcoSystemiserConfig(hive_config=test_hive_config)

# Inject into service
service = DataProcessor(config=test_app_config)
```

---

## Migration Recipes

### Recipe 1: Simple Service Constructor

**Before**:
```python
from hive_config import get_config

class DataProcessor:
    def __init__(self):
        self.config = get_config()  # Global state
        self.db_path = self.config.database.path
```

**After**:
```python
from hive_config import HiveConfig, create_config_from_sources

class DataProcessor:
    def __init__(self, config: HiveConfig | None = None):
        # DI with sensible default
        self._config = config or create_config_from_sources()
        self.db_path = self._config.database.path
```

**Why Better**:
- ✅ Explicit dependency in signature
- ✅ Testable (inject mock config)
- ✅ Default fallback maintains compatibility

---

### Recipe 2: Module-Level Global Config

**Before**:
```python
from hive_config import get_config

# Module-level global
config = get_config()

def process_data(data):
    db_path = config.database.path  # Uses global
    # ... processing
```

**After (Option A: Function Parameter)**:
```python
from hive_config import HiveConfig

def process_data(data, config: HiveConfig):
    db_path = config.database.path  # Uses parameter
    # ... processing

# Usage
from hive_config import create_config_from_sources
config = create_config_from_sources()
process_data(data, config=config)
```

**After (Option B: Class-Based)**:
```python
from hive_config import HiveConfig, create_config_from_sources

class DataProcessor:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()

    def process_data(self, data):
        db_path = self._config.database.path
        # ... processing

# Usage
processor = DataProcessor()
processor.process_data(data)
```

**Why Better**:
- ✅ No global state
- ✅ Clear dependency flow
- ✅ Testable with different configs

---

### Recipe 3: App-Level Configuration Bridge

**Before**:
```python
from hive_config import get_config

class MyAppConfig:
    def __init__(self):
        self.hive = get_config()  # Global state
        self.app_settings = load_app_settings()
```

**After**:
```python
from hive_config import HiveConfig, create_config_from_sources
from my_app.settings import AppSettings

class MyAppConfig:
    """Configuration bridge: inherit platform, extend domain."""

    def __init__(self, hive_config: HiveConfig | None = None):
        # Inherit: Platform configuration with DI
        self._hive = hive_config or create_config_from_sources()

        # Extend: Domain-specific configuration
        self._app = AppSettings()

    @property
    def database(self):
        """Platform config (inherited)"""
        return self._hive.database

    @property
    def custom_feature(self):
        """Domain config (extended)"""
        return self._app.custom
```

**Why Better**:
- ✅ Clear inherit→extend pattern
- ✅ Testable with injected config
- ✅ Separation of concerns

---

### Recipe 4: Factory Functions

**Before**:
```python
from hive_config import get_config

def create_worker_pool():
    config = get_config()  # Global state
    return WorkerPool(
        max_workers=config.worker.max_workers,
        timeout=config.worker.timeout
    )
```

**After**:
```python
from hive_config import HiveConfig, create_config_from_sources

def create_worker_pool(config: HiveConfig | None = None) -> WorkerPool:
    """Factory function with optional config injection."""
    config = config or create_config_from_sources()

    return WorkerPool(
        max_workers=config.worker.max_workers,
        timeout=config.worker.timeout
    )
```

**Why Better**:
- ✅ Explicit config parameter
- ✅ Testable with mock config
- ✅ Backward compatible (optional param)

---

### Recipe 5: Pattern Library Examples

**Before** (guardian-agent/cross_package_analyzer.py):
```python
IntegrationPattern(
    name="Centralized Configuration",
    required_import="from hive_config import get_config",
    replacement_code="""
# Hardcoded values replaced with config
from hive_config import get_config
config = get_config()
API_KEY = config.api_key
""",
)
```

**After**:
```python
IntegrationPattern(
    name="Centralized Configuration with DI",
    required_import="from hive_config import HiveConfig, create_config_from_sources",
    replacement_code="""
# Hardcoded values replaced with DI pattern
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()
        self.api_key = self._config.api_key
        self.max_retries = self._config.max_retries
""",
)
```

**Why Better**:
- ✅ Shows best practice to developers
- ✅ Promotes DI adoption
- ✅ Example code is testable

---

## Testing Strategies

### Strategy 1: Pytest Fixtures (Recommended)

**Create Fixtures** (`conftest.py`):
```python
import pytest
from pathlib import Path
from hive_config import (
    HiveConfig,
    DatabaseConfig,
    ClaudeConfig,
    create_config_from_sources
)

@pytest.fixture
def hive_config() -> HiveConfig:
    """Production-like config for integration tests."""
    return create_config_from_sources()

@pytest.fixture
def mock_config() -> HiveConfig:
    """Isolated config for unit tests."""
    return HiveConfig(
        database=DatabaseConfig(
            path=Path(":memory:"),
            connection_pool_min=1,
            connection_pool_max=2
        ),
        claude=ClaudeConfig(
            mock_mode=True,
            timeout=1
        )
    )

@pytest.fixture
def custom_config():
    """Config factory for test-specific needs."""
    def _create_config(**overrides):
        base = HiveConfig(
            database=DatabaseConfig(path=Path(":memory:"))
        )
        for key, value in overrides.items():
            setattr(base, key, value)
        return base
    return _create_config
```

**Use in Tests**:
```python
def test_with_real_config(hive_config):
    """Integration test with production-like config."""
    service = MyService(config=hive_config)
    assert service.db_path.exists()

def test_isolated(mock_config):
    """Unit test with isolated config."""
    service = MyService(config=mock_config)
    assert service.db_path == Path(":memory:")

def test_custom(custom_config):
    """Test with custom config values."""
    config = custom_config(database__path=Path("/tmp/test.db"))
    service = MyService(config=config)
    assert service.db_path == Path("/tmp/test.db")
```

---

### Strategy 2: Test Class Setup

```python
class TestMyService:
    """Test suite with shared config setup."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test config for all tests in class."""
        self.config = HiveConfig(
            database=DatabaseConfig(path=Path(":memory:"))
        )
        self.service = MyService(config=self.config)

    def test_feature_a(self):
        """Test uses self.service with test config."""
        result = self.service.process()
        assert result is not None

    def test_feature_b(self):
        """Independent test, same setup."""
        result = self.service.validate()
        assert result is True
```

---

### Strategy 3: Parameterized Tests

```python
@pytest.mark.parametrize("db_path,expected", [
    (Path(":memory:"), True),
    (Path("/tmp/test.db"), True),
    (Path("/nonexistent/path.db"), False),
])
def test_database_paths(db_path, expected):
    """Test with different config values."""
    config = HiveConfig(
        database=DatabaseConfig(path=db_path)
    )
    service = MyService(config=config)
    assert service.is_valid() == expected
```

---

### Strategy 4: Integration Tests

```python
@pytest.mark.integration
def test_full_workflow(hive_config):
    """End-to-end test with real config."""
    # Create services with real config
    processor = DataProcessor(config=hive_config)
    validator = Validator(config=hive_config)
    exporter = Exporter(config=hive_config)

    # Test full workflow
    data = processor.load()
    validated = validator.check(data)
    result = exporter.export(validated)

    assert result.success
```

---

## Common Pitfalls

### Pitfall 1: Forgetting Default Fallback

**Problem**:
```python
class MyService:
    def __init__(self, config: HiveConfig):
        self._config = config  # Required, breaks compatibility!

# This now fails:
service = MyService()  # TypeError: missing config argument
```

**Solution**:
```python
class MyService:
    def __init__(self, config: HiveConfig | None = None):
        # Provide sensible default
        self._config = config or create_config_from_sources()

# Now works:
service = MyService()  # Uses default config
```

---

### Pitfall 2: Creating Config Multiple Times

**Problem**:
```python
class ServiceA:
    def __init__(self):
        self.config = create_config_from_sources()  # Instance 1

class ServiceB:
    def __init__(self):
        self.config = create_config_from_sources()  # Instance 2

# Each service creates its own config - inefficient!
```

**Solution**:
```python
# Create once at app root
config = create_config_from_sources()

# Pass down to services
service_a = ServiceA(config=config)
service_b = ServiceB(config=config)
```

---

### Pitfall 3: Tests Still Using Global State

**Problem**:
```python
def test_service():
    load_config()  # Still using global state!
    service = MyService()
    # ... test
```

**Solution**:
```python
def test_service(mock_config):
    service = MyService(config=mock_config)  # Inject test config
    # ... test
```

---

### Pitfall 4: Mixing Old and New Patterns

**Problem**:
```python
class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or get_config()  # Still uses global!
```

**Solution**:
```python
class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()  # Factory!
```

---

### Pitfall 5: Not Documenting Config Dependencies

**Problem**:
```python
class MyService:
    """Data processing service."""  # No mention of config!

    def __init__(self, config: HiveConfig):
        self._config = config
```

**Solution**:
```python
class MyService:
    """
    Data processing service.

    Args:
        config: Hive platform configuration.
                Requires database and claude config sections.
    """

    def __init__(self, config: HiveConfig):
        self._config = config
```

---

## FAQ

### Q: Will this break existing code?

**A**: No. The old pattern (`get_config()`) still works, it just emits deprecation warnings. Migration is backward compatible.

### Q: Can I mix old and new patterns during migration?

**A**: Yes. Both patterns work side-by-side. This allows gradual migration. However, avoid using both in the same file for clarity.

### Q: When will `get_config()` be removed?

**A**: Phase 5 (weeks 8-10) after all code is migrated and tested. You'll have plenty of warning before removal.

### Q: What about performance?

**A**: `create_config_from_sources()` is lightweight. Create once at app startup and reuse the instance. No measurable performance impact.

### Q: How do I test code that uses config?

**A**: Use pytest fixtures to inject test configs. See [Testing Strategies](#testing-strategies) section.

### Q: Can I have different configs for different components?

**A**: Yes! That's one of the benefits of DI. Each component can receive a different config instance if needed.

### Q: What if I need to change config at runtime?

**A**: Create a new config instance and pass it to new component instances. Existing components keep their config.

### Q: How do I debug config issues?

**A**: Add logging in constructors:
```python
def __init__(self, config: HiveConfig | None = None):
    self._config = config or create_config_from_sources()
    logger.debug(f"Service initialized with config: {self._config.database.path}")
```

### Q: Should I use dependency injection for everything?

**A**: For configuration: YES. For other dependencies: use judgment. DI is great for testability but can add verbosity.

---

## Quick Reference Card

### ✅ DO: Use DI Pattern

```python
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()
```

### ❌ DON'T: Use Global State

```python
from hive_config import get_config

class MyService:
    def __init__(self):
        self.config = get_config()  # DEPRECATED!
```

---

### ✅ DO: Create Config Once

```python
# main.py
config = create_config_from_sources()
service_a = ServiceA(config=config)
service_b = ServiceB(config=config)
```

### ❌ DON'T: Create Config Everywhere

```python
class ServiceA:
    def __init__(self):
        self.config = create_config_from_sources()  # Wasteful!

class ServiceB:
    def __init__(self):
        self.config = create_config_from_sources()  # Wasteful!
```

---

### ✅ DO: Use Pytest Fixtures

```python
@pytest.fixture
def mock_config():
    return HiveConfig(database=DatabaseConfig(path=":memory:"))

def test_service(mock_config):
    service = MyService(config=mock_config)
```

### ❌ DON'T: Use Global State in Tests

```python
def test_service():
    load_config()  # Global state!
    service = MyService()
```

---

### ✅ DO: Document Config Needs

```python
class MyService:
    """
    Service description.

    Args:
        config: Hive configuration (requires database, claude sections)
    """
```

### ❌ DON'T: Hide Config Dependencies

```python
class MyService:
    """Service description."""  # No mention of config!
```

---

## Resources

- **API Documentation**: `packages/hive-config/README.md`
- **Migration Tracking**: `docs/development/progress/config_di_migration_guide.md`
- **Configuration Audit**: `claudedocs/config_system_audit.md`
- **Gold Standard Code**: `apps/ecosystemiser/src/ecosystemiser/config/bridge.py`

---

## Support

**Questions?** Ask in #hive-development or open an issue

**Found a problem?** See rollback instructions in migration tracking doc

**Need help migrating?** Reference this guide or check the gold standard example

---

**Last Updated**: 2025-09-30
**Version**: 1.0
**Status**: Active - Phase 1 Complete