#!/usr/bin/env python3
"""
Basic async functionality test with proper path setup
"""

import sys
import os
from pathlib import Path

# Set up paths for local development
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "packages" / "hive-utils" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-bus" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-errors" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-db-utils" / "src"))
sys.path.insert(0, str(project_root / "apps" / "hive-orchestrator" / "src"))

# Set environment variable
os.environ['HIVE_PROJECT_ROOT'] = str(project_root)

print("=== Basic Async Import Test ===")
print(f"Project root: {project_root}")
print(f"PYTHONPATH entries: {len([p for p in sys.path if 'hive' in p])}")

try:
    # Test basic imports
    import hive_utils.paths
    print("[PASS] hive_utils.paths imported successfully")
    print(f"       PROJECT_ROOT: {hive_utils.paths.PROJECT_ROOT}")

    import hive_core_db
    print("[PASS] hive_core_db imported successfully")

    # Test async specific imports
    from hive_core_db.async_connection_pool import get_async_connection
    print("[PASS] async_connection_pool imported successfully")

    from hive_core_db.async_compat import sync_wrapper
    print("[PASS] async_compat imported successfully")

    from hive_bus.event_bus import get_event_bus
    print("[PASS] event_bus imported successfully")

    # Test Queen import
    from hive_orchestrator.queen import QueenLite
    print("[PASS] QueenLite imported successfully")

    # Check if async methods are available
    if hasattr(QueenLite, 'run_forever_async'):
        print("[PASS] QueenLite.run_forever_async method available")
    else:
        print("[FAIL] QueenLite.run_forever_async method missing")

    if hasattr(QueenLite, 'spawn_worker_async'):
        print("[PASS] QueenLite.spawn_worker_async method available")
    else:
        print("[FAIL] QueenLite.spawn_worker_async method missing")

    print("\n=== Basic Async Test PASSED ===")

except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()