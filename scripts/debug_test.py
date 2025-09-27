#!/usr/bin/env python3
"""
Quick debug test for V3.0 certification
"""

import sys
import time
from pathlib import Path

# Add the package paths
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "hive-db-utils" / "src"))

def test_config():
    """Test configuration system"""
    try:
        from hive_db_utils.config import get_config
        config = get_config()
        print(f"Environment: {config.env}")
        print(f"Debug mode: {config.get_bool('debug_mode')}")
        print(f"Max connections: {config.get_int('db_max_connections')}")
        print("Configuration test: PASSED")
        return True
    except Exception as e:
        print(f"Configuration test failed: {e}")
        return False

if __name__ == "__main__":
    print("Debug test starting...")
    result = test_config()
    print(f"Result: {'PASSED' if result else 'FAILED'}")