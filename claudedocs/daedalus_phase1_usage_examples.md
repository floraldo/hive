# PROJECT DAEDALUS Phase 1 - Usage Examples

Quick reference guide for the new unified APIs from Phase 1 consolidation.

---

## Phase 1.1: hive-config - DI Pattern

### ✅ NEW: Dependency Injection Pattern

```python
from hive_config import create_config_from_sources, HiveConfig

class MyService:
    def __init__(self, config: HiveConfig | None = None):
        """Dependency injection with sensible default."""
        self._config = config or create_config_from_sources()
        self.db_path = self._config.database.path
        self.api_key = self._config.claude.api_key

# Usage
service = MyService()  # Uses global config
test_service = MyService(test_config)  # Uses injected config (testable!)
```

### ❌ DEPRECATED: Global State Pattern

```python
# OLD - DEPRECATED (still works via aliases but discouraged)
from hive_config import get_config, load_config

config = get_config()  # Hidden dependency, not testable
config = load_config()  # Also deprecated
```

---

## Phase 1.2: hive-errors - Unified Error Handling

### ✅ NEW: UnifiedErrorReporter

```python
from hive_errors import UnifiedErrorReporter, ErrorContext, error_context

# Create unified reporter
reporter = UnifiedErrorReporter(
    service_name="my-service",
    enable_metrics=True,
    enable_monitoring=True
)

# Async error handling with context
async def my_operation():
    async with error_context(
        reporter=reporter,
        operation_name="fetch_data",
        component="api_client",
        timeout=30.0,
        suppress_errors=False
    ) as ctx:
        # Your operation here
        result = await fetch_from_api()
        return result

# Decorator pattern
from hive_errors import handle_async_errors

@handle_async_errors(
    reporter=reporter,
    component="data_processor",
    max_retries=3,
    exponential_backoff=True
)
async def process_data(data):
    # Will retry with exponential backoff on failure
    return await process(data)

# Manual error handling
try:
    result = await risky_operation()
    await reporter.handle_success_async(context, execution_time=0.5)
except Exception as e:
    await reporter.handle_error_async(e, context, suppress=False)
```

### ❌ DEPRECATED: Separate Error Handlers

```python
# OLD - DEPRECATED (still works via aliases)
from hive_errors import AsyncErrorHandler  # Now aliases to UnifiedErrorReporter
from hive_errors import MonitoringErrorReporter  # Use UnifiedErrorReporter instead

# These still work for backward compatibility
handler = AsyncErrorHandler(...)  # Actually creates UnifiedErrorReporter
monitor = MonitoringErrorReporter(...)  # Same class now
```

---

## Phase 1.3: hive-async - Unified Resilience Management

### ✅ NEW: AsyncResilienceManager (Timeout + Circuit Breaker)

```python
from hive_async import AsyncResilienceManager, TimeoutConfig, CircuitState

# Configure unified resilience
config = TimeoutConfig(
    default_timeout=30.0,
    enable_adaptive=True,
    enable_circuit_breaker=True,
    failure_threshold=5,
    recovery_timeout=60
)

manager = AsyncResilienceManager(config=config, name="api-client")

# Execute with unified resilience (timeout + circuit breaker)
async def fetch_data():
    result = await manager.execute_with_timeout_async(
        operation=api_call,
        operation_name="fetch_users",
        timeout_type="default",
        retry_attempt=0
    )
    return result

# Context manager pattern
from hive_async import resilience_context_async

async def my_operation():
    async with resilience_context_async(
        manager=manager,
        operation_name="database_query",
        timeout=10.0
    ) as timeout:
        # Operation protected by timeout + circuit breaker
        return await db.query()

# Decorator pattern
from hive_async import with_resilience

@with_resilience(manager=manager, timeout=15.0)
async def api_call():
    # Automatically protected by timeout + circuit breaker
    return await external_api.fetch()

# Circuit breaker management
if manager.is_circuit_open("fetch_users"):
    logger.warning("Circuit breaker is open - operation blocked")

status = manager.get_circuit_status("fetch_users")
print(f"Circuit state: {status['state']}")
print(f"Failures: {status['failure_count']}/{status['failure_threshold']}")

# Manual circuit reset
await manager.reset_circuit_breaker_async("fetch_users")

# Get failure history for predictive analysis
history = manager.get_failure_history(
    operation_name="fetch_users",
    metric_type="failure_rate",
    hours=24
)
```

### ❌ DEPRECATED: Separate Resilience Classes

```python
# OLD - DEPRECATED (still works via aliases)
from hive_async import (
    AdvancedTimeoutManager,  # Now aliases to AsyncResilienceManager
    AsyncCircuitBreaker,     # Now aliases to AsyncResilienceManager
    AsyncTimeoutManager,     # Now aliases to AsyncResilienceManager
    async_timeout,           # Use with_resilience instead
    async_circuit_breaker,   # Use with_resilience instead
    async_resilient,         # Use with_resilience instead
)

# These still work for backward compatibility
timeout_mgr = AdvancedTimeoutManager()  # Actually creates AsyncResilienceManager
circuit = AsyncCircuitBreaker()         # Actually creates AsyncResilienceManager
```

---

## Migration Strategy

### Gradual Migration (No Breaking Changes)

**Phase 1: Keep using old APIs** (still works via aliases)
```python
# Your existing code continues to work unchanged
from hive_errors import AsyncErrorHandler
from hive_async import AdvancedTimeoutManager, AsyncCircuitBreaker

handler = AsyncErrorHandler()  # Works - aliases to UnifiedErrorReporter
timeout = AdvancedTimeoutManager()  # Works - aliases to AsyncResilienceManager
circuit = AsyncCircuitBreaker()  # Works - aliases to AsyncResilienceManager
```

**Phase 2: Migrate to new APIs gradually**
```python
# Update imports one at a time
from hive_errors import UnifiedErrorReporter  # New unified interface
from hive_async import AsyncResilienceManager  # New unified interface

# Use new names, same functionality
reporter = UnifiedErrorReporter()
manager = AsyncResilienceManager()
```

**Phase 3: Adopt new features**
```python
# Leverage unified capabilities (timeout + circuit breaker in one)
manager = AsyncResilienceManager(
    config=TimeoutConfig(
        enable_adaptive=True,      # Adaptive timeout
        enable_circuit_breaker=True  # + Circuit breaker
    )
)

# Single execute call gets both protections
result = await manager.execute_with_timeout_async(
    operation=risky_call,
    operation_name="external_api",
    timeout=30.0
)
# ↑ Protected by adaptive timeout AND circuit breaker
```

---

## Benefits of Consolidation

### Before Phase 1

**Config**: 3 separate patterns
- `load_config()` - deprecated
- `get_config()` - deprecated
- `create_config_from_sources()` - recommended

**Errors**: 2 separate handlers
- `MonitoringErrorReporter` - sync + monitoring
- `AsyncErrorHandler` - async + retry

**Resilience**: 3 separate managers
- `AsyncTimeoutManager` - basic timeout
- `AdvancedTimeoutManager` - adaptive timeout
- `AsyncCircuitBreaker` - circuit breaker

### After Phase 1

**Config**: 1 unified pattern
- `create_config_from_sources()` - DI pattern (only way)

**Errors**: 1 unified handler
- `UnifiedErrorReporter` - sync + async + monitoring + retry

**Resilience**: 1 unified manager
- `AsyncResilienceManager` - timeout + circuit breaker + adaptive + metrics

### Result

- **Simpler**: 1 API to learn instead of 3
- **More powerful**: Combined capabilities (timeout + circuit breaker)
- **Backward compatible**: All old code still works
- **Better metrics**: Unified monitoring across all operations
- **Easier testing**: DI pattern makes everything mockable

---

## Quick Reference

### Import Cheat Sheet

```python
# Config - DI Pattern
from hive_config import create_config_from_sources, HiveConfig

# Errors - Unified Handler
from hive_errors import (
    UnifiedErrorReporter,
    ErrorContext,
    ErrorStats,
    error_context,
    handle_async_errors,
    create_error_context,
)

# Async - Unified Resilience
from hive_async import (
    AsyncResilienceManager,
    TimeoutConfig,
    TimeoutMetrics,
    CircuitState,
    resilience_context_async,
    with_resilience,
)
```

### Common Patterns

**DI Config**:
```python
def __init__(self, config: HiveConfig | None = None):
    self._config = config or create_config_from_sources()
```

**Async Error Handling**:
```python
async with error_context(reporter, "op_name", "component") as ctx:
    result = await operation()
```

**Unified Resilience**:
```python
result = await manager.execute_with_timeout_async(
    operation, "op_name", timeout=30.0
)
```

---

## Testing Examples

### Config Testing (DI Pattern)

```python
import pytest
from hive_config import HiveConfig

@pytest.fixture
def test_config():
    return HiveConfig(
        database=DatabaseConfig(path=":memory:"),
        claude=ClaudeConfig(api_key="test-key")
    )

def test_my_service(test_config):
    # Inject test config
    service = MyService(config=test_config)
    assert service.db_path == ":memory:"
```

### Error Handling Testing

```python
import pytest
from hive_errors import UnifiedErrorReporter, ErrorContext

@pytest.fixture
def test_reporter():
    return UnifiedErrorReporter(service_name="test")

@pytest.mark.asyncio
async def test_error_handling(test_reporter):
    ctx = ErrorContext(operation_name="test_op", component="test")

    await test_reporter.handle_error_async(
        error=ValueError("test"),
        context=ctx,
        suppress=False
    )

    stats = test_reporter.get_error_stats()
    assert stats.total_errors == 1
```

### Resilience Testing

```python
import pytest
from hive_async import AsyncResilienceManager, TimeoutConfig

@pytest.fixture
def test_manager():
    config = TimeoutConfig(
        default_timeout=1.0,
        failure_threshold=2
    )
    return AsyncResilienceManager(config=config)

@pytest.mark.asyncio
async def test_circuit_breaker(test_manager):
    async def failing_op():
        raise ValueError("fail")

    # Trigger failures
    for _ in range(2):
        with pytest.raises(ValueError):
            await test_manager.execute_with_timeout_async(
                failing_op, "test_op"
            )

    # Circuit should be open now
    assert test_manager.is_circuit_open("test_op")
```

---

**End of Usage Examples**
