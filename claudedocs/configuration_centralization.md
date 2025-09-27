# Configuration Centralization - V3.0 Platform Certification

## Overview

Configuration centralization has been implemented to ensure consistent behavior across all Hive components. All configuration is now managed through the centralized `hive_db_utils.config` module.

## Key Benefits

1. **Consistency**: All components use the same configuration source
2. **Environment Management**: Proper development/testing/production configurations
3. **Maintainability**: Single source of truth for configuration values
4. **Flexibility**: Easy to override defaults via environment variables

## Configuration Hierarchy

1. **Environment Variables** (highest priority)
2. **Environment-specific defaults** (production/testing/development)
3. **Global defaults** (lowest priority)

## Environment Configuration

### Development Environment
- Mock mode enabled for external services
- Debug logging enabled
- Lower rate limits for testing

### Testing Environment
- Mock mode forced on
- Higher rate limits for test execution
- Debug logging enabled
- Shorter timeouts for faster tests

### Production Environment
- All external services enabled
- Warning-level logging
- Secure connections enforced
- Production rate limits

## Component Integration

### Database (hive-core-db)
Now uses centralized configuration for:
- Connection pool sizes
- Connection timeouts
- Database operation timeouts

**Migration**:
```python
# Before
pool = ConnectionPool(min_connections=2, max_connections=10)

# After (uses centralized config)
pool = ConnectionPool()  # Uses config defaults

# Or with overrides
pool = ConnectionPool(max_connections=20)  # Override just what you need
```

### Claude Service (hive-claude-bridge)
Now uses centralized configuration for:
- Rate limiting settings
- Cache TTL
- Mock mode
- Timeouts and retries

**Migration**:
```python
# Before
service = ClaudeService(
    rate_config=RateLimitConfig(max_calls_per_minute=30),
    cache_ttl=300
)

# After (uses centralized config)
service = ClaudeService()  # Uses config defaults

# Or with overrides
service = ClaudeService(cache_ttl=600)  # Override just what you need
```

### Orchestrator (hive-orchestrator)
Continues to use centralized configuration but now integrated with global config system.

## Configuration Keys

### Database Configuration
- `db_timeout`: Database operation timeout (default: 30)
- `db_max_connections`: Maximum database connections (default: 10)
- `db_connection_timeout`: Connection acquisition timeout (default: 5.0)

### Claude Service Configuration
- `claude_rate_limit_per_minute`: API calls per minute (default: 30)
- `claude_rate_limit_per_hour`: API calls per hour (default: 1000)
- `claude_burst_size`: Burst request allowance (default: 5)
- `claude_cache_ttl`: Cache time-to-live seconds (default: 300)
- `claude_timeout`: Request timeout seconds (default: 120)
- `claude_max_retries`: Maximum retry attempts (default: 3)
- `claude_mock_mode`: Enable mock mode (default: false)

### Orchestrator Configuration
- `worker_spawn_timeout`: Worker spawn timeout (default: 30)
- `worker_init_timeout`: Worker initialization timeout (default: 10)
- `worker_graceful_shutdown`: Graceful shutdown timeout (default: 5)
- `max_parallel_tasks`: Maximum parallel tasks (default: 5)
- `max_parallel_backend`: Max backend workers (default: 2)
- `max_parallel_frontend`: Max frontend workers (default: 2)
- `max_parallel_infra`: Max infrastructure workers (default: 1)

### General Configuration
- `log_level`: Logging level (default: INFO)
- `debug_mode`: Enable debug mode (default: false)
- `verbose_logging`: Enable verbose logging (default: false)
- `enable_caching`: Enable application caching (default: true)

## Environment Variable Usage

Set any configuration key as an environment variable:

```bash
# Override Claude service settings
export claude_rate_limit_per_minute=60
export claude_mock_mode=true

# Override database settings
export db_max_connections=20
export db_timeout=60

# Override orchestrator settings
export max_parallel_tasks=10
export debug_mode=true
```

## Code Examples

### Using Centralized Configuration

```python
from hive_db_utils.config import get_config

# Get global config instance
config = get_config()

# Get specific configuration sections
claude_config = config.get_claude_config()
db_config = config.get_database_config()
orchestrator_config = config.get_orchestrator_config()

# Get individual values
debug_mode = config.get_bool("debug_mode")
max_connections = config.get_int("db_max_connections", default=5)
api_timeout = config.get_float("claude_timeout", default=120.0)

# Check environment
if config.is_production():
    # Production-specific logic
    pass
elif config.is_testing():
    # Test-specific logic
    pass
```

### Component Configuration

```python
# Database connection pool
from hive_core_db.connection_pool import ConnectionPool

# Uses centralized config automatically
pool = ConnectionPool()

# Override specific settings
pool = ConnectionPool(max_connections=50)


# Claude service
from hive_claude_bridge import get_claude_service

# Uses centralized config automatically
service = get_claude_service()

# Custom configuration
from hive_claude_bridge import ClaudeService, RateLimitConfig

service = ClaudeService(
    rate_config=RateLimitConfig(max_calls_per_minute=100)
)
```

## Testing Configuration

For testing, set the environment:

```python
import os
os.environ['ENVIRONMENT'] = 'testing'

# This automatically enables:
# - Mock mode for Claude service
# - Higher rate limits
# - Debug logging
# - Shorter timeouts
```

## Verification

### Configuration Loading Test
```python
from hive_db_utils.config import get_config

config = get_config()
print("Environment:", config.env)
print("Claude config:", config.get_claude_config())
print("Database config:", config.get_database_config())
```

### Component Integration Test
```python
# Test database uses config
from hive_core_db.connection_pool import get_pooled_connection

with get_pooled_connection() as conn:
    print("Database connection successful with centralized config")

# Test Claude service uses config
from hive_claude_bridge import get_claude_service

service = get_claude_service()
print("Claude service configured with:", service.config.__dict__)
```

## Migration Checklist

- [x] Enhanced centralized configuration in `hive_db_utils.config`
- [x] Updated database connection pool to use centralized config
- [x] Updated Claude service to use centralized config
- [x] Environment-specific configuration defaults
- [x] Configuration getter methods for each component
- [ ] Update any remaining components to use centralized config
- [ ] Add configuration validation
- [ ] Add configuration documentation generation

## Best Practices

1. **Always use `get_config()` to access configuration**
2. **Provide sensible defaults for all configuration values**
3. **Use environment variables for deployment-specific overrides**
4. **Test configuration in all environments (dev/test/prod)**
5. **Document any new configuration keys**
6. **Use typed configuration getters (`get_int`, `get_bool`, etc.)**

## Impact Assessment

- **Database**: ✅ Migrated to centralized config, backward compatible
- **Claude Service**: ✅ Migrated to centralized config, backward compatible
- **Orchestrator**: ✅ Already uses centralized approach, integrated
- **Other Components**: 🔄 May need migration to use centralized config

Configuration centralization provides a solid foundation for V3.0 platform certification with consistent, maintainable, and environment-aware configuration management.