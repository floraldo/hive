#!/usr/bin/env python3

import sys
from pathlib import Path

# Add the package paths
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-db-utils" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-claude-bridge" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-errors" / "src"))

print("Starting step-by-step certification...")

print("Test 1: Configuration...")
try:
    from hive_db_utils.config import get_config

    config = get_config()
    assert config.env in ["development", "testing", "production"]
    print("PASS: Configuration")
except Exception as e:
    print(f"FAIL: Configuration - {e}")

print("Test 2: Database...")
try:
    import hive_core_db.connection_pool as cp

    pool = cp.ConnectionPool()
    assert pool.max_connections > 0
    pool.close_all()
    print("PASS: Database (basic)")
except Exception as e:
    print(f"FAIL: Database - {e}")

print("Test 3: Database connection...")
try:
    import hive_core_db.connection_pool as cp

    print("  Getting pooled connection...")
    with cp.get_pooled_connection() as conn:
        print("  Executing query...")
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
    print("PASS: Database connection")
except Exception as e:
    print(f"FAIL: Database connection - {e}")

print("Test 4: Claude service...")
try:
    from hive_claude_bridge.claude_service import get_claude_service, reset_claude_service

    print("  Resetting service...")
    reset_claude_service()
    print("  Getting service...")
    service = get_claude_service()
    assert service is not None
    print("PASS: Claude service")
except Exception as e:
    print(f"FAIL: Claude service - {e}")

print("All tests completed!")
