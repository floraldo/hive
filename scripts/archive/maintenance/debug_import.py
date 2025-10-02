#!/usr/bin/env python3

import sys
from pathlib import Path

# Add the package paths
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))

try:
    import hive_core_db.connection_pool as cp

    print("Available functions and classes:")
    for name in dir(cp):
        if not name.startswith("_"):
            print(f"  {name}")
except Exception as e:
    print(f"Import error: {e}")

try:
    from hive_core_db.connection_pool import ConnectionPool, get_pooled_connection

    print("Imports successful!")
    print(f"ConnectionPool: {ConnectionPool}")
    print(f"get_pooled_connection: {get_pooled_connection}")
except Exception as e:
    print(f"Direct import error: {e}")
