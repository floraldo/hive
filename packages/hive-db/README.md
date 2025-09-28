# hive-db

Database utilities and connection management for Hive platform applications using Dependency Injection patterns.

## Features

- **Connection Pooling**: Thread-safe connection pools for SQLite databases
- **Async Support**: High-performance async connection pooling with aiosqlite
- **Database Utilities**: Common operations like migrations, backups, schema management
- **Transaction Management**: Context managers for safe database transactions
- **Health Monitoring**: Connection pool statistics and health checks
- **Multi-Database Support**: Manage multiple databases with isolated pools

## Usage

### Basic Database Connections with DI

```python
from hive_db import get_sqlite_connection, get_postgres_connection

# SQLite with configuration (Dependency Injection)
config = {
    "db_path": "path/to/db.sqlite",
    "timeout": 30.0,
    "check_same_thread": False
}

with get_sqlite_connection(config=config) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")

# PostgreSQL with configuration (Dependency Injection)
config = {
    "database_url": "postgresql://user:pass@localhost/dbname",
    "host": "localhost",
    "port": 5432,
    "database": "mydb",
    "user": "myuser",
    "password": "mypass"
}

with get_postgres_connection(config=config) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
```

### Connection Pooling with DI

```python
from hive_db import ConnectionPool
from pathlib import Path

# Create pool with configuration (Dependency Injection)
db_config = {
    "max_connections": 25,
    "min_connections": 5,
    "connection_timeout": 30.0
}

# Create pool instance with DI
pool = ConnectionPool(db_config=db_config)

# Use pooled connection
with pool.get_connection() as conn:
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

This package follows the Hive inherit-extend pattern with Dependency Injection, providing common database utilities that can be extended by specific applications. Apps can import and extend these utilities with their own database-specific logic while maintaining explicit dependency management.

### Best Practices

1. **Always pass configuration explicitly** - Never use global state or environment variables directly
2. **Create configuration once** - At application startup, then pass down through constructors
3. **Test with different configs** - Use in-memory databases and custom settings for testing
4. **Validate early** - Check configuration at startup, not during runtime operations
5. **Document dependencies** - Make configuration requirements explicit in function signatures

## Dependency Injection Patterns

### Application-Level Configuration

```python
# main.py - Application entry point
from hive_config import create_config_from_sources
from hive_db import ConnectionPool
import os

def main():
    # Create configuration with DI (production)
    config = create_config_from_sources(
        config_path=Path("config/hive.json"),
        use_environment=True
    )

    # Pass config to database layer
    db_pool = ConnectionPool(db_config=config.database.dict())

    # Pass pool to services
    user_service = UserService(db_pool=db_pool)
    task_service = TaskService(db_pool=db_pool)

    # Start application
    app = Application(user_service, task_service)
    app.run()
```

### Testing with DI

```python
# test_services.py
def test_user_service():
    # Create test configuration
    test_config = {
        "db_path": ":memory:",  # In-memory database for testing
        "max_connections": 1,
        "connection_timeout": 5.0
    }

    # Create test pool with DI
    test_pool = ConnectionPool(db_config=test_config)

    # Test service with isolated database
    service = UserService(db_pool=test_pool)

    # Service uses test database, not production
    user = service.create_user("test_user")
    assert user.name == "test_user"
```

### Migration from Global State

```python
# ❌ OLD: Anti-pattern with hidden dependencies
import os

def get_connection():
    db_url = os.getenv("DATABASE_URL")  # Hidden dependency!
    return connect(db_url)

class UserService:
    def __init__(self):
        self.conn = get_connection()  # Hidden global state!

# ✅ NEW: Explicit DI pattern
class UserService:
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool  # Explicit dependency!

    def get_user(self, user_id: str):
        with self.db_pool.get_connection() as conn:
            # Use connection
            pass
```

## Configuration Structure

```python
# Database configuration schema
db_config = {
    # Connection settings
    "db_path": "path/to/database.db",  # SQLite path
    "database_url": "postgresql://...",  # PostgreSQL URL

    # Pool settings
    "min_connections": 2,
    "max_connections": 10,
    "connection_timeout": 30.0,

    # SQLite specific
    "check_same_thread": False,
    "isolation_level": "DEFERRED",

    # PostgreSQL specific
    "host": "localhost",
    "port": 5432,
    "database": "mydb",
    "user": "myuser",
    "password": "mypass",
    "sslmode": "require"
}
```

## Performance

- **Sync Pools**: Optimized for multi-threaded applications with thread-safe operations
- **Async Pools**: High-performance async operations with aiosqlite for 3-5x throughput improvement
- **Connection Reuse**: Automatic connection validation and reuse
- **Resource Management**: Proper cleanup and lifecycle management
