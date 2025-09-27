#!/usr/bin/env python3
"""
Test to understand why ASYNC_ENABLED is False
"""

import sys
import os
from pathlib import Path

# Set up paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "packages" / "hive-utils" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-core-db" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-bus" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-errors" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-config" / "src"))
sys.path.insert(0, str(project_root / "packages" / "hive-db-utils" / "src"))
sys.path.insert(0, str(project_root / "apps" / "hive-orchestrator" / "src"))

os.environ['HIVE_PROJECT_ROOT'] = str(project_root)

print("=== Testing ASYNC_ENABLED Status ===")

try:
    # Test individual imports step by step
    print("1. Testing hive_core_db import...")
    import hive_core_db
    print("   [PASS] hive_core_db imported")

    print("2. Testing async functions import...")
    try:
        from hive_core_db import (
            get_queued_tasks_async, update_task_status_async, get_task_async,
            get_tasks_by_status_async, create_run_async, ASYNC_AVAILABLE
        )
        print(f"   [PASS] hive_core_db async functions imported, ASYNC_AVAILABLE={ASYNC_AVAILABLE}")
    except ImportError as e:
        print(f"   [FAIL] hive_core_db async functions import failed: {e}")

    print("3. Testing hive_bus async functions import...")
    try:
        from hive_bus import get_async_event_bus, publish_event_async
        print("   [PASS] hive_bus async functions imported")
    except ImportError as e:
        print(f"   [FAIL] hive_bus async functions import failed: {e}")

    print("4. Testing Queen import with ASYNC_ENABLED status...")
    from hive_orchestrator.queen import QueenLite, ASYNC_ENABLED
    print(f"   [INFO] ASYNC_ENABLED in Queen: {ASYNC_ENABLED}")

    if hasattr(QueenLite, 'run_forever_async'):
        print("   [PASS] Queen has run_forever_async")
    else:
        print("   [FAIL] Queen missing run_forever_async")

    if hasattr(QueenLite, 'spawn_worker_async'):
        print("   [PASS] Queen has spawn_worker_async")
    else:
        print("   [FAIL] Queen missing spawn_worker_async")

except Exception as e:
    print(f"[FAIL] Test failed: {e}")
    import traceback
    traceback.print_exc()