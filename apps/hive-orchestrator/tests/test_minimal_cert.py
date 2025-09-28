#!/usr/bin/env python3
"""
Minimal V3.0 Platform Certification Test
"""

import sys
import time
from pathlib import Path

# Add the package paths
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports
# No sys.path manipulation needed - use Poetry workspace imports

def test_1_configuration():
    """Test configuration system"""
    print("Testing configuration...")
    try:
        from hive_db.config import get_config
        config = get_config()
        assert config.env in ["development", "testing", "production"]
        claude_config = config.get_claude_config()
        assert "mock_mode" in claude_config
        print("PASS: Configuration")
        return True
    except Exception as e:
        print(f"FAIL: Configuration - {e}")
        return False

def test_2_database():
    """Test database connection pool"""
    print("Testing database...")
    try:
        # Test connection pool class creation and basic configuration
        import hive_db as cp
        pool = cp.ConnectionPool()
        assert pool.max_connections > 0
        assert pool.connection_timeout > 0

        # Test that pool has proper structure
        stats = pool.get_stats()
        assert "pool_size" in stats

        pool.close_all()
        print("PASS: Database")
        return True
    except Exception as e:
        print(f"FAIL: Database - {e}")
        return False

def test_3_claude_service():
    """Test Claude service"""
    print("Testing Claude service...")
    try:
        from hive_claude_bridge.claude_service import get_claude_service, reset_claude_service
        reset_claude_service()
        service = get_claude_service()
        assert service is not None
        metrics = service.get_metrics()
        assert "total_calls" in metrics
        print("PASS: Claude service")
        return True
    except Exception as e:
        print(f"FAIL: Claude service - {e}")
        return False

def main():
    """Run minimal certification tests"""
    print("Starting V3.0 Platform Certification Test (Minimal)")
    print("=" * 50)

    tests = [
        ("Configuration", test_1_configuration),
        ("Database", test_2_database),
        ("Claude Service", test_3_claude_service),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"ERROR: {name} - {e}")

    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("CERTIFICATION: PASSED")
        print("V3.0 Platform ready for certification!")
    else:
        print("CERTIFICATION: FAILED")
        print("Some tests failed - check logs above")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)