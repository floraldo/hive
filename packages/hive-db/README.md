# Hive DB Utils

Database connectivity utilities for the Hive ecosystem.

Provides generic database connection patterns that can be used by Hive applications for consistent data persistence.

## Features

- SQLite connector with WAL mode and foreign key support
- PostgreSQL connector with connection pooling
- Transaction context managers
- Table creation utilities
- Database information helpers

## Usage

```python
from hive_db_utils import get_sqlite_connection, sqlite_transaction

# Basic SQLite usage
conn = get_sqlite_connection("my_app.db")

# Transaction context manager
with sqlite_transaction("my_app.db") as conn:
    conn.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    conn.execute("INSERT INTO users (name) VALUES (?)", ("Bob",))
    # Transaction commits automatically on success

# Table creation
from hive_db_utils import create_table_if_not_exists

schema = '''
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
'''
create_table_if_not_exists(conn, "users", schema)
```

## Installation

```bash
pip install -e .
```