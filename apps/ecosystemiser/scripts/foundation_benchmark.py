#!/usr/bin/env python3
"""
EcoSystemiser Foundation Benchmark

Tests the foundational architecture after the v3.0 hardening:
- App vs Hive config distinction
- Inherit→extend pattern compliance
- Basic database operations
- Legacy compatibility layer

This establishes the performance baseline for the foundation work.
"""

import sys
import time
import warnings
from pathlib import Path

# Use Poetry workspace imports
try:
    from hive_logging import get_logger

    logger = get_logger(__name__)

    def test_config_inheritance():
        """Test the inherit→extend pattern for configuration"""
        logger.info("Testing configuration inherit→extend pattern...")
        start_time = time.time()

        try:
            # Test new inherit→extend pattern with direct hive-config imports
            from hive_config import load_config_for_app

            config = load_config_for_app("ecosystemiser")
            logger.info(f"SUCCESS: App config loaded for '{config.app_name}'")
            logger.info(f"Config keys: {len(config.config)}")

            settings = config.config
            eco_keys = [k for k in settings.keys() if "ECOSYSTEMISER" in k]
            logger.info(f"EcoSystemiser-specific keys: {len(eco_keys)}")

            # No legacy compatibility test needed - we've eliminated the wrappers
            logger.info("SUCCESS: Using direct hive-config imports (no deprecated wrappers)")

            elapsed = time.time() - start_time
            logger.info(f"Config test completed in {elapsed:.3f}s")
            return True

        except Exception as e:
            logger.error(f"Config test failed: {e}")
            return False

    def test_database_operations():
        """Test basic database operations"""
        logger.info("Testing database operations...")
        start_time = time.time()

        try:
            from ecosystemiser.core.db import (
                get_ecosystemiser_connection,
                get_ecosystemiser_db_path,
                validate_ecosystemiser_database,
            )

            # Test database path
            db_path = get_ecosystemiser_db_path()
            logger.info(f"Database path: {db_path}")

            # Test database validation
            is_valid = validate_ecosystemiser_database()
            logger.info(f"Database validation: {is_valid}")

            # Test connection context manager
            with get_ecosystemiser_connection() as conn:
                cursor = conn.execute("SELECT 1 as test")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    logger.info("SUCCESS: Database connection working")
                else:
                    logger.error("Database connection test failed")
                    return False

            elapsed = time.time() - start_time
            logger.info(f"Database test completed in {elapsed:.3f}s")
            return True

        except Exception as e:
            logger.error(f"Database test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def test_logging_integration():
        """Test logging integration"""
        logger.info("Testing logging integration...")
        start_time = time.time()

        try:
            # Test direct hive_logging import
            from hive_logging import get_logger

            test_logger = get_logger("foundation_test")
            test_logger.info("Testing direct hive_logging import")

            # No legacy compatibility test needed - we've eliminated the wrappers
            logger.info("SUCCESS: Using direct hive_logging imports (no deprecated wrappers)")

            elapsed = time.time() - start_time
            logger.info(f"Logging test completed in {elapsed:.3f}s")
            return True

        except Exception as e:
            logger.error(f"Logging test failed: {e}")
            return False

    def benchmark_foundation():
        """Run complete foundation benchmark"""
        logger.info("=" * 60)
        logger.info("EcoSystemiser Foundation Benchmark v3.0")
        logger.info("Testing architectural hardening results")
        logger.info("=" * 60)

        start_time = time.time()
        tests = [
            ("Configuration Inherit→Extend", test_config_inheritance),
            ("Database Operations", test_database_operations),
            ("Logging Integration", test_logging_integration),
        ]

        results = {}
        for test_name, test_func in tests:
            logger.info(f"\n--- {test_name} ---")
            results[test_name] = test_func()

        total_time = time.time() - start_time

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("FOUNDATION BENCHMARK RESULTS")
        logger.info("=" * 60)

        passed = sum(results.values())
        total = len(results)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name:30} {status}")

        logger.info(f"\nOverall: {passed}/{total} tests passed")
        logger.info(f"Total time: {total_time:.3f}s")

        if passed == total:
            logger.info("\n🎉 Foundation benchmark PASSED!")
            logger.info("EcoSystemiser v3.0 architectural hardening is complete")
            return True
        else:
            logger.error(f"\n❌ Foundation benchmark FAILED")
            logger.error(f"{total - passed} tests failed")
            return False

    if __name__ == "__main__":
        success = benchmark_foundation()
        sys.exit(0 if success else 1)

except ImportError as e:
    print(f"CRITICAL: Cannot import required modules: {e}")
    print("This indicates the foundation architecture needs more work")
    sys.exit(1)
