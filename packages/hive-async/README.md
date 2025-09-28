# hive-async

Async utilities and patterns for Hive platform applications.

## Features

- **Context Management**: AsyncResourceManager for proper async resource cleanup
- **Retry Logic**: Configurable async retry patterns with exponential backoff
- **Connection Pooling**: Generic connection pool with health checking
- **Task Management**: Coordinated async task execution with monitoring
- **Concurrency Control**: Utilities for managing concurrent operations

## Usage

### Context Management

```python
from hive_async import AsyncResourceManager, async_context

# Resource manager
async with AsyncResourceManager() as manager:
    manager.register_resource("db", db_connection, cleanup_callback=close_db)
    # Resources are automatically cleaned up

# Multiple context manager
async with async_context(db_connection, redis_connection) as (db, redis):
    # Use both connections
    pass
```

### Retry Logic

```python
from hive_async import async_retry, AsyncRetryConfig, retry_on_connection_error

# Basic retry
result = await async_retry(unstable_function, config=AsyncRetryConfig(max_attempts=5))

# Decorator
@retry_on_connection_error
async def connect_to_service():
    # Function will be retried on connection errors
    pass
```

### Connection Pooling

```python
from hive_async import ConnectionPool, PoolConfig

# Create pool
pool = ConnectionPool(
    create_connection=create_db_connection,
    close_connection=close_db_connection,
    config=PoolConfig(min_size=2, max_size=10)
)

async with pool:
    async with pool.connection() as conn:
        # Use connection
        pass
```

### Task Management

```python
from hive_async import TaskManager, gather_with_concurrency

# Task manager
async with TaskManager(max_concurrent=5) as manager:
    task_id = await manager.submit_task(async_operation())
    result = await manager.wait_for_task(task_id)

# Concurrency-limited gather
results = await gather_with_concurrency(
    *[async_operation(i) for i in range(100)],
    max_concurrent=10
)
```

## Integration

This package follows the Hive inherit-extend pattern, providing common async utilities that can be extended by specific applications.