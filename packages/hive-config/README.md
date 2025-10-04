# hive-config

Configuration management for the Hive platform using Dependency Injection patterns.

## Overview

The `hive-config` package provides centralized configuration management for all Hive applications and packages. It follows modern Dependency Injection (DI) patterns, eliminating global state and singletons for improved testability and maintainability.

## Features

- **Dependency Injection First**: No global singletons or state
- **Environment Variable Support**: Load configuration from environment
- **Type-Safe Configuration**: Pydantic models for validation
- **Path Management**: Centralized project paths and utilities
- **Multiple Config Sources**: Files, environment variables, or code

## Installation

```bash
# Within a Hive workspace app or package
poetry add --editable ../../packages/hive-config
```

## Usage

### Unified App Loader (RECOMMENDED - Project Unify V2)

**The easiest way to load configuration** - combines all 4 layers automatically:

```python
from hive_config import load_config_for_app

# ONE function for all your configuration needs
config = load_config_for_app("my-app")

# All 4 layers merged automatically:
# 1. Package defaults (config.defaults.toml)
# 2. App .env files (.env.global → .env.shared → apps/my-app/.env)
# 3. User config files (hive_config.json)
# 4. Environment variables (HIVE_*)

# Pass config to your services
database_service = DatabaseService(config=config.database.dict())
claude_service = ClaudeService(config=config.claude.timeout)
```

**4-Layer Configuration Hierarchy:**

```
Layer 1 (lowest):  Package defaults from config.defaults.toml
Layer 2:           App .env files (.env.global → .env.shared → apps/{app}/.env)
Layer 3:           User config files (hive_config.json or app-specific config.toml)
Layer 4 (highest): Environment variables (HIVE_*)
```

Each layer overrides the previous one, providing maximum flexibility with sane defaults.

### Creating Configuration (DI Pattern)

For packages or advanced use cases:

```python
from hive_config.unified_config import create_config_from_sources
from pathlib import Path

# Create configuration instance
config = create_config_from_sources(
    config_path=Path("config/hive_config.json"),  # Optional
    use_environment=True  # Load from environment variables
)

# Pass config to your services
database_service = DatabaseService(config=config.database.dict())
claude_service = ClaudeService(config=config.claude.dict())
```

### Using in Applications

```python
# main.py or app entry point
from hive_config.unified_config import create_config_from_sources

def main():
    # Create config once at startup
    config = create_config_from_sources()

    # Pass down through dependency injection
    orchestrator = Orchestrator(config=config)
    orchestrator.run()

if __name__ == "__main__":
    main()
```

### Using in Tests

```python
# test_service.py
def test_service_with_mock_config():
    # Create test-specific configuration
    test_config = {
        'database': {
            'path': ':memory:',
            'connection_pool_max': 1
        },
        'claude': {
            'mock_mode': True,
            'timeout': 1
        }
    }

    # Inject test config
    service = MyService(config=test_config)

    # Service uses test config, not production
    assert service.is_mock_mode == True
```

## Configuration Structure

### HiveConfig Schema

```python
{
    # Database settings
    "database": {
        "path": "path/to/database.db",
        "connection_pool_min": 2,
        "connection_pool_max": 10,
        "connection_timeout": 30
    },

    # Claude API settings
    "claude": {
        "mock_mode": false,
        "timeout": 120,
        "max_retries": 3
    },

    # Orchestration settings
    "orchestration": {
        "poll_interval": 5,
        "worker_timeout": 600,
        "max_parallel_workers": 4
    },

    # Environment settings
    "environment": "development",
    "debug_mode": false
}
```

### Environment Variables (Layer 4)

Configuration can be overridden using environment variables with the `HIVE_` prefix.

**Naming Convention:** `HIVE_<CATEGORY>_<SETTING>`

**Supported Environment Variables:**

**High-Level Settings:**
- `HIVE_ENVIRONMENT`: Set environment (development/staging/production)
- `HIVE_DEBUG_MODE`: Enable debug mode (true/false)

**Database Configuration:**
- `HIVE_DATABASE_PATH`: Override database path
- `HIVE_DATABASE_POOL_MIN`: Minimum connection pool size
- `HIVE_DATABASE_POOL_MAX`: Maximum connection pool size
- `HIVE_DATABASE_TIMEOUT`: Connection timeout in seconds
- `HIVE_DATABASE_JOURNAL_MODE`: SQLite journal mode (WAL, DELETE, etc.)

**Claude AI Configuration:**
- `HIVE_CLAUDE_MOCK_MODE`: Enable Claude mock mode (true/false)
- `HIVE_CLAUDE_TIMEOUT`: API timeout in seconds
- `HIVE_CLAUDE_MAX_RETRIES`: Maximum retry attempts
- `HIVE_CLAUDE_FALLBACK_ENABLED`: Enable fallback behavior (true/false)

**Orchestration Configuration:**
- `HIVE_ORCHESTRATION_POLL_INTERVAL`: Task polling interval in seconds
- `HIVE_ORCHESTRATION_WORKER_TIMEOUT`: Worker timeout in seconds
- `HIVE_ORCHESTRATION_MAX_PARALLEL_WORKERS`: Maximum concurrent workers
- `HIVE_ORCHESTRATION_HEARTBEAT_INTERVAL`: Heartbeat interval in seconds

**Worker Configuration:**
- `HIVE_WORKER_BACKEND_ENABLED`: Enable backend worker (true/false)
- `HIVE_WORKER_FRONTEND_ENABLED`: Enable frontend worker (true/false)
- `HIVE_WORKER_INFRA_ENABLED`: Enable infrastructure worker (true/false)
- `HIVE_WORKER_MAX_RETRIES_PER_TASK`: Maximum retries per task

**Logging Configuration:**
- `HIVE_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `HIVE_LOG_FORMAT`: Log message format
- `HIVE_LOG_DIRECTORY`: Directory for log files
- `HIVE_LOG_FILE_ENABLED`: Enable file logging (true/false)
- `HIVE_LOG_CONSOLE_ENABLED`: Enable console logging (true/false)

**Type Conversion:**
Environment variables are automatically converted to the appropriate type:
- `true`, `false`, `yes`, `no`, `1`, `0` → boolean
- Numeric strings → integers
- Strings with `.` → floats
- Settings with `path` or `dir` → Path objects
- Everything else → strings

**Example:**
```bash
export HIVE_DATABASE_PATH="/custom/db.sqlite"
export HIVE_CLAUDE_TIMEOUT=300
export HIVE_WORKER_BACKEND_ENABLED=true
export HIVE_LOG_LEVEL=DEBUG
```

Then in Python:
```python
config = load_config_for_app("my-app")
assert config.database.path == Path("/custom/db.sqlite")  # Path object
assert config.claude.timeout == 300  # integer
assert config.worker.backend_enabled == True  # boolean
assert config.logging.level == "DEBUG"  # string
```

## Path Management

```python
from hive_config.paths import (
    get_project_root,
    PROJECT_ROOT,
    LOGS_DIR,
    DB_PATH,
    ensure_directory
)

# Get project root directory
root = get_project_root()

# Ensure directory exists
ensure_directory(LOGS_DIR)

# Use predefined paths
db_path = DB_PATH  # Default database location
```

## Configuration Patterns

### Gold Standard: Inherit→Extend Pattern

The **recommended pattern** for app-level configuration, demonstrated in `EcoSystemiser`:

```python
from hive_config import HiveConfig, create_config_from_sources
from my_app.settings import AppSettings

class MyAppConfig:
    """
    Configuration bridge: inherit platform, extend domain.

    Follows the inherit→extend pattern:
    - Inherits: Core platform settings from hive-config
    - Extends: Domain-specific application settings
    """

    def __init__(self, hive_config: HiveConfig | None = None):
        # Inherit: Platform configuration with DI
        self._hive_config = hive_config or create_config_from_sources()

        # Extend: Domain-specific configuration
        self._app_config = AppSettings()

    @property
    def database(self):
        """Platform database configuration (inherited)"""
        return self._hive_config.database

    @property
    def app_specific_feature(self):
        """Domain-specific configuration (extended)"""
        return self._app_config.feature_settings

# Usage
app_config = MyAppConfig()
db_path = app_config.database.path
feature_enabled = app_config.app_specific_feature.enabled
```

**Why this pattern?**
- ✅ Clear separation: platform vs domain concerns
- ✅ Testable: inject mock configs for testing
- ✅ Flexible: each component can have different configs
- ✅ Type-safe: IDE support and compile-time checks
- ✅ No global state: each instance independent

### Component-Level DI Pattern

For services, workers, and components:

```python
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    """Service with optional config injection."""

    def __init__(self, config: HiveConfig | None = None):
        # Accept injected config with sensible default
        self._config = config or create_config_from_sources()

        # Extract what you need
        self.db_path = self._config.database.path
        self.timeout = self._config.claude.timeout

    def do_work(self):
        # Use configuration
        with database_connection(self.db_path) as conn:
            # ... work
            pass

# Production usage
config = create_config_from_sources()
service = MyService(config=config)

# Test usage
test_config = HiveConfig(database=DatabaseConfig(path=":memory:"))
service = MyService(config=test_config)
```

**When to use:**
- Services that need platform configuration
- Workers spawned from main process
- Components shared across apps

### Test Fixture Pattern

For pytest-based testing:

```python
import pytest
from hive_config import HiveConfig, DatabaseConfig, create_config_from_sources

@pytest.fixture
def hive_config() -> HiveConfig:
    """Production-like config for integration tests."""
    return create_config_from_sources()

@pytest.fixture
def mock_config() -> HiveConfig:
    """Isolated config for unit tests."""
    return HiveConfig(
        database=DatabaseConfig(path=":memory:"),
        claude=ClaudeConfig(mock_mode=True, timeout=1),
        logging=LoggingConfig(level="DEBUG")
    )

# Usage in tests
def test_service_with_real_config(hive_config):
    service = MyService(config=hive_config)
    assert service.db_path.exists()

def test_service_isolated(mock_config):
    service = MyService(config=mock_config)
    assert service.db_path == Path(":memory:")
```

**Benefits:**
- ✅ No global state cleanup needed
- ✅ Parallel test execution works
- ✅ Each test fully isolated
- ✅ Clear what config each test uses

## Common Patterns by Use Case

### Use Case 1: Application Entry Point
```python
# main.py
from hive_config import create_config_from_sources

def main():
    # Create config once at root
    config = create_config_from_sources()

    # Inject into all components
    orchestrator = Orchestrator(config=config)
    worker_pool = WorkerPool(config=config)
    monitor = Monitor(config=config)

    orchestrator.run()
```

### Use Case 2: App-Specific Configuration Bridge
```python
# my_app/config.py
from hive_config import HiveConfig, create_config_from_sources
from my_app.settings import MyAppSettings

class MyAppConfig:
    def __init__(self, hive_config: HiveConfig | None = None):
        self._hive = hive_config or create_config_from_sources()
        self._app = MyAppSettings()

    @property
    def database(self):
        return self._hive.database  # Inherited

    @property
    def custom_feature(self):
        return self._app.custom  # Extended
```

### Use Case 3: Service with Config Dependency
```python
# my_service.py
from hive_config import HiveConfig

class DataProcessor:
    def __init__(self, config: HiveConfig):
        self._config = config
        self.batch_size = config.processing.batch_size

    def process(self, data):
        # Use config values
        pass
```

### Use Case 4: Factory Function with Config
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

## Migration from Legacy Patterns

### Anti-Pattern 1: Global Singleton (DEPRECATED)
```python
# DEPRECATED - DO NOT USE
from hive_config import get_config

class MyService:
    def __init__(self):
        self.config = get_config()  # Hidden dependency, global state!
```

**Problems:**
- Hidden dependencies (no way to know service needs config)
- Hard to test (requires global state management)
- Thread-unsafe (global state shared)
- Prevents parallel execution

### Anti-Pattern 2: Module-Level Global (DEPRECATED)
```python
# DEPRECATED - DO NOT USE
from hive_config import get_config

# Module-level global config
config = get_config()

def process_data():
    db_path = config.database.path  # Uses global!
```

**Problems:**
- Initialization order issues
- Cannot inject test config
- Tight coupling to global state

### Best Practice: Dependency Injection (RECOMMENDED)
```python
# RECOMMENDED - DO THIS
from hive_config import HiveConfig, create_config_from_sources

class MyService:
    def __init__(self, config: HiveConfig | None = None):
        # Explicit dependency with sensible default
        self._config = config or create_config_from_sources()
```

**Benefits:**
- ✅ Explicit dependencies (clear in signature)
- ✅ Easy to test (inject mock config)
- ✅ Thread-safe (no shared state)
- ✅ Parallel-friendly (each instance isolated)

## Migration Guide

### Migration Path 1: From Deprecated Singletons → Unified Loader

**For Apps** - Switch to `load_config_for_app()`:

```python
# OLD (DEPRECATED)
from hive_config import get_config

class MyApp:
    def __init__(self):
        self.config = get_config()  # Global singleton!

# NEW (RECOMMENDED)
from hive_config import load_config_for_app

class MyApp:
    def __init__(self, config: HiveConfig | None = None):
        # Unified loader with all 4 layers
        self._config = config or load_config_for_app("my-app")
```

**Benefits:**
- ✅ All 4 configuration layers automatically merged
- ✅ Package defaults loaded transparently
- ✅ .env hierarchy respected
- ✅ Environment variables auto-discovered
- ✅ Still supports dependency injection for testing

### Migration Path 2: From `create_config_from_sources()` → `load_config_for_app()`

**For Apps** - Simplify to unified loader:

```python
# OLD (Still works, but more verbose)
from hive_config import create_config_from_sources

class MyApp:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or create_config_from_sources()

# NEW (Simpler, includes all 4 layers)
from hive_config import load_config_for_app

class MyApp:
    def __init__(self, config: HiveConfig | None = None):
        self._config = config or load_config_for_app("my-app")
```

**When to migrate:**
- ✅ If you're an app (in `apps/` directory)
- ✅ If you want automatic .env file loading
- ✅ If you want package defaults
- ❌ Keep `create_config_from_sources()` for packages (in `packages/` directory)

### Migration Path 3: Legacy Patterns → Dependency Injection

For detailed migration instructions, see:
- **Comprehensive Guide**: `claudedocs/config_migration_guide_comprehensive.md`
- **Migration Tracking**: `docs/development/progress/config_di_migration_guide.md`

**Quick Migration Steps:**

1. **Update Constructor**:
   ```python
   # Before
   def __init__(self):
       self.config = get_config()

   # After (Apps)
   def __init__(self, config: HiveConfig | None = None):
       self._config = config or load_config_for_app("my-app")

   # After (Packages)
   def __init__(self, config: HiveConfig | None = None):
       self._config = config or create_config_from_sources()
   ```

2. **Update Callers**:
   ```python
   # Before
   service = MyService()

   # After
   config = load_config_for_app("my-app")
   service = MyService(config=config)
   ```

3. **Update Tests**:
   ```python
   # Before
   def test_service():
       load_config()  # Global setup
       service = MyService()
       reset_config()  # Global cleanup

   # After
   def test_service(mock_config):
       service = MyService(config=mock_config)  # Isolated!
   ```

### What About Environment Variables?

**Project Unify V2 eliminates manual `os.getenv()` calls:**

```python
# OLD (Manual, error-prone)
import os
db_path = os.getenv("DATABASE_PATH", config.database.path)
timeout = int(os.getenv("CLAUDE_TIMEOUT", config.claude.timeout))

# NEW (Automatic, type-safe)
config = load_config_for_app("my-app")
db_path = config.database.path  # HIVE_DATABASE_PATH automatically merged
timeout = config.claude.timeout  # HIVE_CLAUDE_TIMEOUT automatically merged
```

**Golden Rule 37** now enforces this - direct `os.getenv()` calls outside `hive-config` are blocked at PR time.

## Troubleshooting

### Issue: "Config is None in my service"
**Cause**: Forgot to pass config or create default
**Solution**:
```python
def __init__(self, config: HiveConfig | None = None):
    # Add default fallback
    self._config = config or create_config_from_sources()
```

### Issue: "Tests interfere with each other"
**Cause**: Using global config in tests
**Solution**: Use pytest fixtures with isolated config instances

### Issue: "Config created multiple times"
**Cause**: Calling `create_config_from_sources()` in multiple places
**Solution**: Create once at app root, pass down via DI

### Issue: "Can't mock config in tests"
**Cause**: Service creates its own config internally
**Solution**: Accept config via constructor, don't create internally

## Best Practices

1. **Create config once** at application entry point
2. **Pass config down** through constructors (Dependency Injection)
3. **Never use globals** like `get_config()` (deprecated)
4. **Test with fixtures** using isolated config instances
5. **Use type hints** for better IDE support: `config: HiveConfig`
6. **Provide defaults** with `config or create_config_from_sources()`
7. **Document config needs** in class/function docstrings
8. **Validate early** using Pydantic models for type safety

## API Reference

### `create_config_from_sources(config_path=None, use_environment=True)`
Creates a HiveConfig instance from various sources.

**Parameters:**
- `config_path`: Optional path to JSON config file
- `use_environment`: Whether to override with environment variables

**Returns:** `HiveConfig` instance

### `HiveConfig`
Main configuration class with sub-configurations for each component.

**Attributes:**
- `database`: DatabaseConfig
- `claude`: ClaudeConfig
- `orchestration`: OrchestrationConfig
- `worker`: WorkerConfig
- `ai`: AIConfig
- `logging`: LoggingConfig

## Contributing

When adding new configuration options:

1. Add to appropriate config model in `unified_config.py`
2. Document environment variable mapping
3. Update this README with new options
4. Ensure backward compatibility

## License

Part of the Hive platform - internal use only.