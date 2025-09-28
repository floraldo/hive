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

### Creating Configuration (DI Pattern)

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

### Environment Variables

Configuration can be overridden using environment variables:

- `HIVE_ENVIRONMENT`: Set environment (development/staging/production)
- `HIVE_DEBUG_MODE`: Enable debug mode
- `HIVE_DATABASE_PATH`: Override database path
- `HIVE_CLAUDE_MOCK_MODE`: Enable Claude mock mode
- `HIVE_WORKER_TIMEOUT`: Set worker timeout

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

## Migration from Legacy Patterns

### Before (Anti-pattern with Global State)
```python
# DON'T DO THIS - Global singleton
from hive_config import get_config

class MyService:
    def __init__(self):
        self.config = get_config()  # Hidden dependency!
```

### After (Best Practice with DI)
```python
# DO THIS - Explicit dependency injection
class MyService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config  # Explicit dependency!
```

## Best Practices

1. **Create config once** at application entry point
2. **Pass config down** through constructors (Dependency Injection)
3. **Never use globals** or singletons for configuration
4. **Test with different configs** by injecting test configurations
5. **Validate early** using Pydantic models

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