#!/usr/bin/env python3
"""Quick fix for syntax errors blocking test execution."""

import os
import re


def fix_hive_cache_client():
    """Fix the syntax error in hive-cache client file."""
    file_path = "packages/hive-cache/src/hive_cache/cache_client.py"

    with open(file_path) as f:
        content = f.read()

    # Fix the malformed conditional expression
    content = re.sub(
        r'collection_interval=self\.config\.performance_monitor_interval,\n\s+if hasattr\(self\.config, "performance_monitor_interval"\),\n\s+else 5\.0,',
        'collection_interval=self.config.performance_monitor_interval\n                if hasattr(self.config, "performance_monitor_interval")\n                else 5.0,',
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed syntax error in {file_path}")


def fix_pool_syntax():
    """Fix any syntax errors in pool.py files."""
    file_path = "packages/hive-db/src/hive_db/pool.py"

    with open(file_path) as f:
        content = f.read()

    # Fix malformed tuple in function definition line 66
    content = re.sub(
        r'def _create_connection\(self\) -> sqlite3\.Connection \| None:\n\s+\(".*",\)',
        'def _create_connection(self) -> sqlite3.Connection | None:\n        """Create a new database connection with optimal settings."""',
        content,
    )

    # Fix malformed tuple in function definition line 96
    content = re.sub(
        r'def _validate_connection\(self, conn: sqlite3\.Connection\) -> bool:\n\s+\(".*",\)',
        'def _validate_connection(self, conn: sqlite3.Connection) -> bool:\n        """Check if a connection is still valid."""',
        content,
    )

    # Fix missing __init__ method in DatabaseManager class
    if "def __init__(self)" not in content:
        content = re.sub(
            r'class DatabaseManager:\n\s+"""',
            'class DatabaseManager:\n    """\n    Manager for multiple database connection pools.\n\n    Provides a unified interface for accessing different SQLite databases\n    while maintaining connection pooling and proper resource management.\n    """\n\n    def __init__(self):\n        """Initialize the database manager."""\n        self._pools = {}\n        self._lock = threading.RLock()\n\n    """',
            content,
        )

    # Fix sqlite3 connection string syntax error
    content = re.sub(
        r"conn = sqlite3\.connect\(\n\s+str\(self\.db_path\)\n\s+check_same_thread=False,",
        "conn = sqlite3.connect(\n                str(self.db_path),\n                check_same_thread=False,",
        content,
    )

    # Fix trailing comma issues
    content = re.sub(r"conn\.row_factory = sqlite3\.Row,", "conn.row_factory = sqlite3.Row", content)

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed syntax errors in {file_path}")


def fix_postgres_connector():
    """Fix any trailing comma issues in postgres_connector.py."""
    file_path = "packages/hive-db/src/hive_db/postgres_connector.py"

    with open(file_path) as f:
        content = f.read()

    # Fix trailing commas in logger statements
    content = re.sub(r'logger\.info\(".*"\),', lambda m: m.group(0)[:-1], content)
    content = re.sub(r'logger\.error\(".*"\),', lambda m: m.group(0)[:-1], content)
    content = re.sub(r'logger\.debug\(".*"\),', lambda m: m.group(0)[:-1], content)

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed syntax errors in {file_path}")


if __name__ == "__main__":
    os.chdir("C:/git/hive")

    try:
        fix_hive_cache_client()
    except Exception as e:
        print(f"Error fixing cache client: {e}")

    try:
        fix_pool_syntax()
    except Exception as e:
        print(f"Error fixing pool: {e}")

    try:
        fix_postgres_connector()
    except Exception as e:
        print(f"Error fixing postgres connector: {e}")

    print("Syntax fixes complete!")
