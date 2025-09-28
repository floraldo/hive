# hive-db

Database utilities and connection management for Hive platform applications.

## Features

- **Connection Pooling**: Thread-safe connection pools for SQLite databases
- **Async Support**: High-performance async connection pooling with aiosqlite
- **Database Utilities**: Common operations like migrations, backups, schema management
- **Transaction Management**: Context managers for safe database transactions
- **Health Monitoring**: Connection pool statistics and health checks
- **Multi-Database Support**: Manage multiple databases with isolated pools

## Usage

### Basic Database Connections

```python
from hive_db import get_sqlite_connection, get_postgres_connection

# SQLite
with get_sqlite_connection("path/to/db.sqlite") as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")

# PostgreSQL
with get_postgres_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
```

### Connection Pooling

```python
from hive_db import get_pooled_connection
from pathlib import Path

# Automatic connection pooling
with get_pooled_connection("app_db", Path("./app.db")) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    # Connection automatically returned to pool
```

### Async Connection Pooling

```python
from hive_db import get_async_connection
from pathlib import Path

# High-performance async operations
async with get_async_connection("app_db", Path("./app.db")) as conn:
    cursor = await conn.execute("SELECT * FROM users")
    rows = await cursor.fetchall()
```

### Database Utilities

```python
from hive_db import (
    table_exists, backup_database, migrate_database,
    database_transaction, batch_insert
)

# Check if table exists
if table_exists(conn, "users"):
    print("Users table exists")

# Safe transactions
with database_transaction(conn) as cursor:
    cursor.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    cursor.execute("UPDATE users SET active = 1 WHERE name = ?", ("Alice",))
    # Automatically commits or rolls back on error

# Batch operations
users = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]
batch_insert(conn, "users", users)

# Database migrations
migrate_database(conn, Path("./migrations"))

# Backup database
backup_database(Path("./app.db"), Path("./backups/app_backup.db"))
```

### Pool Management and Monitoring

```python
from hive_db import get_pool_stats, pool_health_check, close_all_pools

# Get pool statistics
stats = get_pool_stats()
print(f"Active pools: {len(stats)}")

# Health check
health = pool_health_check()
for db_name, status in health.items():
    print(f"{db_name}: {status['status']}")

# Cleanup (usually in app shutdown)
close_all_pools()
```

### Async Pool Management

```python
from hive_db import get_async_pool_stats, async_pool_health_check, close_all_async_pools

# Async pool statistics
stats = await get_async_pool_stats()

# Async health check
health = await async_pool_health_check()

# Async cleanup
await close_all_async_pools()
```

## Integration

This package follows the Hive inherit-extend pattern, providing common database utilities that can be extended by specific applications. Apps can import and extend these utilities with their own database-specific logic.

## Configuration

Connection pools can be configured when creating connections:

```python
# Custom pool configuration
with get_pooled_connection(
    "app_db",
    Path("./app.db"),
    min_connections=5,
    max_connections=20,
    connection_timeout=60.0
) as conn:
    # Use connection
    pass
```

## Performance

- **Sync Pools**: Optimized for multi-threaded applications with thread-safe operations
- **Async Pools**: High-performance async operations with aiosqlite for 3-5x throughput improvement
- **Connection Reuse**: Automatic connection validation and reuse
- **Resource Management**: Proper cleanup and lifecycle management
