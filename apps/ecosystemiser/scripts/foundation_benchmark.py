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

import time
import sys
from pathlib import Path
import warnings

# Set up path to import from the source directory
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

try:
    from hive_logging import get_logger
    logger = get_logger(__name__)

    def test_config_inheritance():
        """Test the inherit→extend pattern for configuration"""
        logger.info("Testing configuration inherit→extend pattern...")
        start_time = time.time()

        try:
            # Test new inherit→extend pattern
            from ecosystemiser.hive_env import get_ecosystemiser_config, get_ecosystemiser_settings

            config = get_ecosystemiser_config()
            logger.info(f"SUCCESS: App config loaded for '{config.app_name}'")
            logger.info(f"Config keys: {len(config.config)}")

            settings = get_ecosystemiser_settings()
            eco_keys = [k for k in settings.keys() if 'ECOSYSTEMISER' in k]
            logger.info(f"EcoSystemiser-specific keys: {len(eco_keys)}")

            # Test legacy compatibility (should show deprecation warning)
            from ecosystemiser.hive_env import get_app_config
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                legacy_config = get_app_config()
                if w and any("deprecated" in str(warning.message) for warning in w):
                    logger.info("SUCCESS: Deprecation warnings working correctly")

            logger.info(f"Legacy config keys: {len(legacy_config)}")

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
                get_ecosystemiser_db_path,
                get_ecosystemiser_connection,
                validate_ecosystemiser_database
            )

            # Test database path
            db_path = get_ecosystemiser_db_path()
            logger.info(f"Database path: {db_path}")

            # Test database validation
            is_valid = validate_ecosystemiser_database()
            logger.info(f"Database validation: {is_valid}")

            # Test connection context manager
            with get_ecosystemiser_connection() as conn:
                cursor = conn.execute('SELECT 1 as test')
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
            # Test new proper import
            from hive_logging import get_logger
            proper_logger = get_logger("foundation_test")
            proper_logger.info("Testing proper hive_logging import")

            # Test legacy import (should show deprecation warning)
            from ecosystemiser.hive_logging_adapter import get_logger as legacy_get_logger
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                legacy_logger = legacy_get_logger("legacy_test")
                if w and any("deprecated" in str(warning.message) for warning in w):
                    logger.info("SUCCESS: Legacy logging deprecation working correctly")

            legacy_logger.info("Testing legacy logging adapter")

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